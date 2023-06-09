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

            # Insert the question and answer into the chat history
            insert_question_answer(question, answer)

            return jsonify(question=question, answer=answer)
        except openai.error.RateLimitError:
            if i < retries - 1:  # if it's not the last try
                time.sleep(10)  # wait for 10 seconds before trying again
            else:
                return jsonify(error="API is overloaded, please try again later."), 503

@app.route('/chat_history', methods=['GET'])
def chat_history():
    conn = sqlite3.connect(DB_NAME)
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
    records = db_cursor.fetchall()
    conn.close()

    chat_history_html = ""
    for record in records:
        question, answer, timestamp = record
        chat_history_html += f"<p><strong>{question}</strong></p>"
        chat_history_html += f"<p>{answer}</p>"
        chat_history_html += f"<p>{timestamp}</p>"
        chat_history_html += "<hr>"

    return chat_history_html

if __name__ == "__main__":
    create_table()
    app.run(host='0.0.0.0', port=8080, debug=True)

