#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
import os
import sys
import sqlite3
import openai
import anthropic

TEST_QUESTION = 'Test question'

class TestApp(unittest.TestCase):
    def setUp(self):
        # Save original environment variables
        self.original_openai = os.environ.get('OPENAI_API_KEY')
        self.original_claude = os.environ.get('CLAUDE_API_KEY')
        
    def tearDown(self):
        # Restore original environment variables
        if self.original_openai:
            os.environ['OPENAI_API_KEY'] = self.original_openai
        else:
            os.environ.pop('OPENAI_API_KEY', None)
            
        if self.original_claude:
            os.environ['CLAUDE_API_KEY'] = self.original_claude
        else:
            os.environ.pop('CLAUDE_API_KEY', None)
            
        # Clear any imported modules to ensure fresh import
        if 'app' in sys.modules:
            del sys.modules['app']

    def test_no_api_keys(self):
        # Remove both API keys
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        
        with self.assertRaises(SystemExit) as cm:
            import app
        self.assertEqual(cm.exception.code, 1)

    @patch('anthropic.Anthropic')
    def test_claude_api_key_only(self, mock_anthropic):
        # Set up only Claude API key
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        # Mock Claude API test call
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response")]
        mock_client.messages.create.return_value = mock_response
        
        import app
        self.assertIsNotNone(app.CLAUDE_API_KEY)
        self.assertIsNone(app.OPENAI_API_KEY)
        
    def test_openai_api_key_only(self):
        # Set up only OpenAI API key
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ.pop('CLAUDE_API_KEY', None)
        
        import app
        self.assertIsNotNone(app.OPENAI_API_KEY)
        self.assertIsNone(app.CLAUDE_API_KEY)

    @patch('anthropic.Anthropic')
    def test_claude_api_insufficient_credits(self, mock_anthropic):
        # Set up only Claude API key
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        # Mock Claude API raising credit balance error
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.BadRequestError("credit balance is too low")
        
        with self.assertRaises(SystemExit) as cm:
            import app
        self.assertEqual(cm.exception.code, 1)

    def test_home_route(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'  # Ensure we have a key set
        from app import app
        self.app = app.test_client()
        
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<h1>Chat with ChatGPT</h1>', response.data)
        self.assertIn(b'<textarea id="question-input"', response.data)

    @patch('openai.chat.completions.create')
    @patch('sqlite3.connect')
    def test_ask_route(self, mock_sqlite_connect, mock_chat_create):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ.pop('CLAUDE_API_KEY', None)
        
        from app import app
        self.app = app.test_client()
        
        mock_db = MagicMock()
        mock_sqlite_connect.return_value = mock_db
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='Answer'))]
        mock_chat_create.return_value = mock_response
        
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertIn(bytes(TEST_QUESTION, 'utf-8'), response.data)
        mock_db.commit.assert_called_once()

    @patch('sqlite3.connect')
    def test_ask_route_db_error(self, mock_sqlite_connect):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from app import app
        self.app = app.test_client()
        
        mock_sqlite_connect.side_effect = sqlite3.OperationalError("DB Error")
        
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 500)

    @patch('sqlite3.connect')
    def test_chat_history_route(self, mock_sqlite_connect):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from app import app
        self.app = app.test_client()
        
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.cursor.return_value = mock_cursor
        mock_sqlite_connect.return_value = mock_db
        
        # Set up mock data
        mock_cursor.fetchall.return_value = [(TEST_QUESTION, 'Answer', '2023-06-03 12:34:56')]
        
        response = self.app.get('/chat_history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<strong>Question:</strong>', response.data)

    @patch('openai.chat.completions.create')
    def test_rate_limit_handling(self, mock_chat_create):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from app import app
        self.app = app.test_client()
        
        # Simulate rate limit error
        mock_chat_create.side_effect = openai.RateLimitError("Rate limit exceeded")
        
        response = self.app.post('/ask', json={'question': TEST_QUESTION})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'API is overloaded', response.data)

    def test_create_table(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from app import create_table, DB_NAME
        import os
        
        # Remove test database if it exists
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
            
        create_table()
        
        # Verify table was created
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

if __name__ == '__main__':
    unittest.main()
