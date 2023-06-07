from flask import Flask, render_template, request, jsonify
import sqlite3
import openai
from datetime import datetime

import os

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

# Database connection
def get_db_connection():
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create chat_history table if it doesn't exist
def create_chat_history_table():
    conn = get_db_connection()
    db_cursor = conn.cursor()
    db_cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

create_chat_history_table()

# Home route
@app.route('/')
def home():
    # Retrieve chat history from the database
    conn = get_db_connection()
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id")
    chat_history = db_cursor.fetchall()
    conn.close()

    return render_template('index.html', chat_history=chat_history)

# Ask route
@app.route('/ask', methods=['POST'])
def ask():
    question = request.json['question']
    print(f"Received question: {question}")
    retries = 5
    for i in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": question}
                ],
            )
            answer = response.choices[0].message['content']
            print(f"API response: {answer}")

            # Store the question, answer, and timestamp in the database
            conn = get_db_connection()
            db_cursor = conn.cursor()
            db_cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)",
                              (question, answer))
            conn.commit()
            conn.close()

            return jsonify(question=question, answer=answer)
        except openai.error.RateLimitError:
            if i < retries - 1:  # if it's not the last try
                time.sleep(10)  # wait for 10 seconds before trying again
            else:
                return jsonify(error="API is overloaded, please try again later."), 503


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)

