#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import openai

import os

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    question = request.json['question']
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
            return jsonify(answer=response.choices[0].message['content'])
        except openai.error.RateLimitError:
            if i < retries - 1:  # if it's not the last try
                time.sleep(10)  # wait for 10 seconds before trying again
            else:
                return jsonify(error="API is overloaded, please try again later."), 503

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)

