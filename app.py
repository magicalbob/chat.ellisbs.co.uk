#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import openai
import os
import sqlite3

DB_NAME = 'chat_history.db'

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

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


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
@app.route('/chat/ask', methods=['POST'])
def ask():
    question = request.json['question']
    print(f"Received question: {question}")
    actual_question=f"{question}. Answer the question including HTML tags to improve formatting."
    retries = 5
    for i in range(retries):
        try:
            response = openai.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": actual_question}
                ],
            )
            answer = response.choices[0].message.content
            print(f"API response: {answer}")

            # Insert the question and answer into the chat history
            insert_question_answer(question, answer)

            return jsonify(question=question, answer=answer)
        except openai.error.RateLimitError:
            if i < retries - 1:  # if it's not the last try
                time.sleep(10)  # wait for 10 seconds before trying again
            else:
                return jsonify(error="API is overloaded, please try again later."), 503

@app.route('/chat_history')
@app.route('/chat/chat_history')
def chat_history():
    conn = sqlite3.connect(DB_NAME)
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
    records = db_cursor.fetchall()
    conn.close()

    chat_history_html = "<html><body>"  # Start the HTML document

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

    chat_history_html += "</body></html>"  # End the HTML document

    return chat_history_html

if __name__ == "__main__":
    create_table()
    if os.getenv("USE_DEBUG", False) == "True":
        USE_DEBUG = True
    else:
        USE_DEBUG = False
    app.run(host = '0.0.0.0', port = 8080, debug = USE_DEBUG)
