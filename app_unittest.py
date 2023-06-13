#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()

    def test_home_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Chat with GPT-3</h1>', response.data)  # Update the expected HTML content
        self.assertIn(b'<input id="question-input" type="text" placeholder="Ask a question...">', response.data)  # Update other expected HTML elements

    @patch('app.openai.ChatCompletion.create')
    @patch('app.insert_question_answer')
    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_ask_route(self, mock_sqlite3_connect, mock_insert_question_answer, mock_chat_completion_create):
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

        # Check if the function for inserting the question and answer into the database was called with correct parameters
        mock_insert_question_answer.assert_called_with('Test question', 'Answer')

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route(self, mock_sqlite3_connect):
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchall.return_value = [('Test question', 'Answer', '2023-06-03 12:34:56')]
        mock_sqlite3_connect.return_value = mock_db

        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test question', response.data)
        self.assertIn(b'Answer', response.data)
        self.assertIn(b'2023-06-03 12:34:56', response.data)

    def test_ask_route_without_question(self):
        response = self.app.post('/ask', json={})
        self.assertEqual(response.status_code, 400)  # Should return 400 Bad Request

if __name__ == '__main__':
    unittest.main()
