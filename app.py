from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

# Database connection
def get_db_connection():
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    return conn

# Home route
@app.route('/')
def home():
    return render_template('index.html')

# Chat history route
@app.route('/chat_history')
def chat_history():
    # Retrieve chat history from the database
    conn = get_db_connection()
    db_cursor = conn.cursor()
    db_cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id")
    chat_history = db_cursor.fetchall()
    conn.close()

    return render_template('chat_history.html', chat_history=chat_history)

# Ask route
@app.route('/ask', methods=['POST'])
def ask():
    question = request.json['question']

    # Call OpenAI API and get the answer
    answer = "Sample answer"

    # Store the question, answer, and timestamp in the database
    conn = get_db_connection()
    db_cursor = conn.cursor()
    db_cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()

    return jsonify(question=question, answer=answer)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)

