from flask import Flask, render_template, request, session
from groq import Groq
import os
from dotenv import load_dotenv
import secrets
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Generate a secure secret key
app.secret_key = secrets.token_hex(32)

# Load the CSV data
# def load_data(file_path):
#     """Load CSV data into a dictionary."""
#     df = pd.read_csv(file_path)
#     return df.set_index('question')['answer'].to_dict() 

# csv_data = load_data('data.csv')  # Update with your CSV file path

# def chat_with_groq(user_input, user_name):
#     # Check if the user input matches any question in the CSV data
#     if user_input in csv_data:
#         return csv_data[user_input]
#     else:
#         return f"I'm sorry, I don't have an answer for that."

# Configure logging
if not os.path.exists('logs'):
    os.makedirs('logs')
    
file_handler = RotatingFileHandler('logs/chatbot.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Chatbot startup')

# Initialize Groq client
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not GROQ_API_KEY:
            app.logger.error('No API key found')
            return "Server configuration error", 500
        return f(*args, **kwargs)
    return decorated_function

def sanitize_input(text):
    """Basic input sanitization"""
    if not isinstance(text, str):
        return ""
    return text.strip()[:1000]  # Limit input length

def draft_message(content, role='user'):
    return {
        "role": role,
        "content": sanitize_input(content)
    }

@app.route("/", methods=["GET", "POST"])
@require_api_key
def index():
    # Initialize chat history in the session if it doesn't exist
    if 'chat_history' not in session:
        session['chat_history'] = []

    if request.method == "POST":
        user_input = sanitize_input(request.form.get("user_input", ""))
        user_name = sanitize_input(request.form.get("user_name", ""))
        
        # if not user_input or not user_name:
        #     return render_template("index.html", 
        #                            error="Please provide both name and message",
        #                            user_name=user_name,
        #                            chat_history=session['chat_history'])

        try:
            messages = [
                {
                    "role": "system",
                    "content": f"You are having a conversation with {user_name}."
                },
                draft_message(user_input)
            ]

            chat_completion = client.chat.completions.create(
                messages=messages,
                model="llama3-8b-8192",
                temperature=0.7,
                # max_tokens=100,
            )

            response = chat_completion.choices[0].message.content
            app.logger.info(f'Successful response for user: {user_name}')

            # Store the conversation in session
            session['chat_history'].append({'user': user_input, 'bot': response})
            session.modified = True  # Mark session as modified
            
            return render_template("index.html",
                                   chatbot_response=response,
                                   user_input=user_input,
                                   user_name=user_name,
                                   chat_history=session['chat_history'])

        except Exception as e:
            app.logger.error(f'Error processing request: {str(e)}')
            return render_template("index.html",
                                   error="An error occurred while processing your request",
                                   user_name=user_name,
                                   chat_history=session['chat_history'])

    return render_template("index.html", chat_history=session['chat_history'])

if __name__ == "__main__":
    # Do not run with debug=True in production
    app.run(host="127.0.0.1", port=8080)

