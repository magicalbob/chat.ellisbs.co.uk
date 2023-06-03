#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for
import requests

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        question = request.form.get('question')
        response = requests.get('https://chat.openai.com', params={'question': question})
        return render_template('home.html', response=response.text)
    return render_template('home.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

