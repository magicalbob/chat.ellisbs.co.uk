#!/usr/bin/env python3
"""
Chat web app for interacting with ChatGPT or Claude APIs.
Stores question/answer history in a local SQLite database.
"""

import os
import sys
import time
import logging
import sqlite3

from flask import Flask, render_template, request, jsonify
import openai
import anthropic

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = 'chat_history.db'
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=template_dir)

# API setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Global client placeholder
CLAUDE_CLIENT = None

class InsufficientCreditsError(RuntimeError):
    """Exception raised when the API account has insufficient credits."""


if not OPENAI_API_KEY and not CLAUDE_API_KEY:
    logger.error("Neither OPENAI_API_KEY nor CLAUDE_API_KEY environment variables are set")
    sys.exit(1)

if CLAUDE_API_KEY and not OPENAI_API_KEY:
    try:
        CLAUDE_CLIENT = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        CLAUDE_CLIENT.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}]
        )
        print("Using Claude API - credentials verified")
    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API key is valid but account has insufficient credits")
            raise InsufficientCreditsError(
                "Claude API account has insufficient credits - please check your billing status"
            ) from e
        logger.error("Error validating Claude API key: %s", e)
        raise
    except anthropic.AuthenticationError as e:
        logger.warning("Claude authentication failed (will try later): %s", e)
    except Exception as e:
        logger.error("Error validating Claude API key: %s", e)
        sys.exit(1)

elif OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("Using OpenAI API")


def create_table():
    """Create the chat_history table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def insert_question_answer(question, answer):
    """Insert a Q/A pair into the database, creating the table if needed."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO chat_history (question, answer) VALUES (?, ?)",
            (question, answer)
        )
    except sqlite3.OperationalError:
        create_table()
        cursor.execute(
            "INSERT INTO chat_history (question, answer) VALUES (?, ?)",
            (question, answer)
        )
    conn.commit()
    conn.close()


def get_claude_response(question):
    """Get a response from Claude, lazy-initializing the client if needed."""
    global CLAUDE_CLIENT  # necessary to support lazy init
    if CLAUDE_CLIENT is None:
        CLAUDE_CLIENT = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    try:
        logger.info("Sending request to Claude API: %s", question)
        message = CLAUDE_CLIENT.messages.create(
            model="claude-3-5-sonnet-20240620",
            messages=[{"role": "user", "content": question}],
            max_tokens=1024
        )
        logger.info("Received response from Claude API")
        return message.content[0].text

    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API account has insufficient credits")
            raise ValueError(
                "Claude API account has insufficient credits - please check your billing status"
            ) from e
        logger.error("Claude API error: %s", e)
        raise
    except Exception as e:
        logger.exception("Error in Claude API call")
        raise


def get_openai_response(question, system_prompt):
    """Get a response from OpenAI with a given system prompt."""
    try:
        logger.info("Sending request to OpenAI API: %s", question)
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
        )
        logger.info("Received response from OpenAI API")
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Error in OpenAI API call")
        raise


@app.route('/')
def home():
    """Render the homepage with model title."""
    _openai = os.getenv("OPENAI_API_KEY")
    _claude = os.getenv("CLAUDE_API_KEY")

    if _openai:
        title = "Chat with ChatGPT"
    elif _claude:
        title = "Chat with Claude"
    else:
        title = "Chat with No Model Available"

    return render_template('index.html', title=title)


@app.route('/ask', methods=['POST'])
@app.route('/chat/ask', methods=['POST'])
def ask():
    """Route handler for chat questions."""
    data = request.json
    if not data or 'question' not in data:
        return jsonify(error="Missing question parameter"), 400

    question = data['question']
    system_prompt = data.get('system_prompt', "You are a helpful assistant.")

    logger.info("Received question: %s", question)
    actual_question = (
        f"{question}. Answer the question using HTML5 tags to improve formatting. "
        "Do not break the 3rd wall and explicitly mention the HTML5 tags."
    )

    for attempt in range(5):
        try:
            if os.getenv("OPENAI_API_KEY"):
                answer = get_openai_response(actual_question, system_prompt)
            else:
                answer = get_claude_response(actual_question)

            logger.info("API response received successfully")
            insert_question_answer(question, answer)
            return jsonify(question=question, answer=answer)

        except (openai.RateLimitError, anthropic.RateLimitError) as e:
            logger.warning("Rate limit error (attempt %d/5): %s", attempt + 1, e)
            if attempt < 4:
                time.sleep(10)
            else:
                return jsonify(error="API is overloaded, please try again later."), 503

        except Exception as e:
            logger.exception("Unexpected error during response fetch")
            return jsonify(error=str(e)), 500


@app.route('/chat_history')
@app.route('/chat/chat_history')
def chat_history():
    """Render the full chat history from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
    records = cursor.fetchall()
    conn.close()

    html = ["<html><body>"]
    for question, answer, timestamp in records:
        html.append("<p><strong>Question:</strong></p>")
        html.append(f"<p>{question}</p>")
        html.append("<p><strong>Answer:</strong></p>")

        while "**" in answer:
            answer = answer.replace("**", "<strong>", 1)
            answer = answer.replace("**", "</strong>", 1)

        html.append(f"<p>{answer}</p>")
        html.append(f"<p><strong>Timestamp:</strong> {timestamp}</p>")
        html.append("<hr>")
    html.append("</body></html>")
    return "".join(html)


if __name__ == "__main__":
    create_table()
    USE_DEBUG = os.getenv("USE_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=48080, debug=USE_DEBUG)
