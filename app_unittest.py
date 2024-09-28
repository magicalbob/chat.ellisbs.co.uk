#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

# Import your app from app.py
from app import app, create_table, insert_question_answer

TEST_QUESTION = 'Test question'

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()

    def test_home_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Chat with ChatGPT</h1>', response.data)  # Update the expected HTML content
        self.assertIn(b'<input id="question-input" type="text" placeholder="Ask a question...">', response.data)  # Update other expected HTML elements

    @patch('app.openai.ChatCompletion.create')
    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_ask_route(self, mock_chat_completion_create, mock_sqlite3_connect):
        mock_db = MagicMock()
        mock_sqlite3_connect.return_value = mock_db
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = {'content': 'Answer'}  # Update the message structure
        mock_chat_completion_create.return_value = mock_response
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes(TEST_QUESTION, 'utf-8'), response.data)
        self.assertIn(b'Answer', response.data)
        mock_db.commit.assert_called_once()

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_ask_route_db_error(self, mock_sqlite3_connect):
        mock_sqlite3_connect.side_effect = sqlite3.OperationalError
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 500)

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route(self, mock_sqlite3_connect):
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchall.return_value = [(TEST_QUESTION, 'Answer', '2023-06-03 12:34:56')]
        mock_sqlite3_connect.return_value = mock_db
        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<p><strong>', response.data)
        self.assertIn(b'<p>', response.data)
        self.assertIn(b'<hr>', response.data)

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route_db_error(self, mock_sqlite3_connect):
        mock_sqlite3_connect.side_effect = sqlite3.OperationalError

        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()

