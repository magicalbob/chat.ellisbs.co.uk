#!/usr/bin/env python3
import unittest
import sqlite3
from unittest.mock import patch, MagicMock

# Import your app from app.py
from app import app, create_table, insert_question_answer

TEST_QUESTION = 'Test question'

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        create_table()  # Ensure the database is set up

    def test_home_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        # Expecting index.html to render but actual content check will depend on the HTML template
        self.assertIn(b'Welcome', response.data)  # Update with actual expected content

    @patch('app.openai.ChatCompletion.create')
    @patch('app.insert_question_answer')
    def test_ask_route(self, mock_insert_question_answer, mock_chat_completion_create):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = {'content': 'Answer'}
        mock_chat_completion_create.return_value = mock_response
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Answer', response.data)
        mock_insert_question_answer.assert_called_once_with(TEST_QUESTION, 'Answer')

    def test_ask_route_failure_handling(self):
        with patch('app.openai.ChatCompletion.create', side_effect=openai.error.RateLimitError("Rate limit exceeded")):
            response = self.app.post('/ask', json={'question': TEST_QUESTION})
            self.assertEqual(response.status_code, 503)
            self.assertIn(b'API is overloaded, please try again later.', response.data)

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route(self, mock_sqlite3_connect):
        mock_db = MagicMock()
        mock_db.cursor.return_value.fetchall.return_value = [(TEST_QUESTION, 'Answer with <strong>bold</strong>', '2023-06-03 12:34:56')]
        mock_sqlite3_connect.return_value = mock_db
        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<strong>bold</strong>', response.data)
        self.assertIn(b'<hr>', response.data)

    @patch('app.sqlite3.connect')  # Stub the database connection
    def test_chat_history_route_db_error(self, mock_sqlite3_connect):
        mock_sqlite3_connect.side_effect = sqlite3.OperationalError
        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()

