#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import openai
import anthropic
import os
import sqlite3
import sys
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = 'chat_history.db'

app = Flask(__name__)

# API setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

if not OPENAI_API_KEY and not CLAUDE_API_KEY:
    logger.error("Neither OPENAI_API_KEY nor CLAUDE_API_KEY environment variables are set")
    sys.exit(1)

# Validate Claude API key if it's being used
if CLAUDE_API_KEY and not OPENAI_API_KEY:
    try:
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        # Test the API key with a minimal request
        test_message = claude_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}]
        )
        print("Using Claude API - credentials verified")
    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API key is valid but account has insufficient credits")
            sys.exit(1)
        else:
            logger.error(f"Error validating Claude API key: {str(e)}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error validating Claude API key: {str(e)}")
        sys.exit(1)
elif OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("Using OpenAI API")

def create_table():
    conn = sqlite3.connect(DB_NAME)
    db_cursor = conn.cursor()
    db_cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
    conn.commit()
    conn.close()

def insert_question_answer(question, answer):
    conn = sqlite3.connect(DB_NAME)
    db_cursor = conn.cursor()
    try:
        db_cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer))
    except sqlite3.OperationalError:
        create_table()
        db_cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()

def get_claude_response(question):
    try:
        logger.info(f"Sending request to Claude API: {question}")
        message = claude_client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=[{
                "role": "user",
                "content": question
            }],
            max_tokens=1024
        )
        logger.info("Received response from Claude API")
        return message.content[0].text
    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API account has insufficient credits")
            raise Exception("Claude API account has insufficient credits - please check your billing status")
        else:
            logger.error(f"Claude API error: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Error in Claude API call: {str(e)}", exc_info=True)
        raise

def get_openai_response(question):
    try:
        logger.info(f"Sending request to OpenAI API: {question}")
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
        )
        logger.info("Received response from OpenAI API")
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in OpenAI API call: {str(e)}", exc_info=True)
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
@app.route('/chat/ask', methods=['POST'])
def ask():
    question = request.json['question']
    logger.info(f"Received question: {question}")
    actual_question = f"{question}. Answer the question using HTML5 tags to improve formatting. Do not break the 3rd wall and explicitly mention the HTML5 tags."
    
    retries = 5
    for i in range(retries):
        try:
            if OPENAI_API_KEY:
                answer = get_openai_response(actual_question)
            else:
                answer = get_claude_response(actual_question)
            
            logger.info(f"API response received successfully")
            insert_question_answer(question, answer)
            return jsonify(question=question, answer=answer)
            
        except (openai.RateLimitError, anthropic.RateLimitError) as e:
            logger.warning(f"Rate limit error (attempt {i+1}/{retries}): {str(e)}")
            if i < retries - 1:
                time.sleep(10)
            else:
                return jsonify(error="API is overloaded, please try again later."), 503
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return jsonify(error=str(e)), 500

@app.route('/chat_history')
@app.route('/chat/chat_history')
def chat_history():
    conn = sqlite3.connect(DB_NAME)
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
    records = db_cursor.fetchall()
    conn.close()

    chat_history_html = "<html><body>"

    for record in records:
        question, answer, timestamp = record
        chat_history_html += "<p><strong>Question:</strong></p>"
        chat_history_html += f"<p>{question}</p>"
        chat_history_html += "<p><strong>Answer:</strong></p>"

        # Replace "**" with <strong> tags for bold formatting
        while "**" in answer:
            answer = answer.replace("**", "<strong>", 1)
            answer = answer.replace("**", "</strong>", 1)

        chat_history_html += f"<p>{answer}</p>"
        chat_history_html += f"<p><strong>Timestamp:</strong> {timestamp}</p>"
        chat_history_html += "<hr>"

    chat_history_html += "</body></html>"

    return chat_history_html

if __name__ == "__main__":
    create_table()
    USE_DEBUG = os.getenv("USE_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=48080, debug=USE_DEBUG)
