#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask

import app
import sqlite3

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()

    def test_home_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Chat with GPT-3</h1>', response.data)  # Update the expected HTML content
        self.assertIn(b'<input id="question-input" type="text" placeholder="Ask a question...">', response.data)  # Update other expected HTML elements

    @patch('app.openai.ChatCompletion.create')
    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_ask_route(self, mock_sqlite3_connect, mock_chat_completion_create):
        mock_db = MagicMock()
        mock_db.cursor.return_value.execute.return_value = None
        mock_sqlite3_connect.return_value = mock_db

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = {'content': 'Answer'}  # Update the message structure
        mock_chat_completion_create.return_value = mock_response

        response = self.app.post('/ask', json={'question': 'Test question'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test question', response.data)
        self.assertIn(b'Answer', response.data)

        mock_db.commit.assert_called_once()

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_ask_route_db_error(self, mock_sqlite3_connect):
        mock_sqlite3_connect.side_effect = sqlite3.OperationalError

        response = self.app.post('/ask', json={'question': 'Test question'})
        self.assertEqual(response.status_code, 500)

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route(self, mock_sqlite3_connect):
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchall.return_value = [('Test question', 'Answer', '2023-06-03 12:34:56')]

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

