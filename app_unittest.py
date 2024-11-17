#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, ANY
from flask import Flask
import os
import sys
import sqlite3
import openai
import anthropic
import json
from datetime import datetime

TEST_QUESTION = 'Test question'

class TestApp(unittest.TestCase):
    def setUp(self):
        # Save original environment variables
        self.original_openai = os.environ.get('OPENAI_API_KEY')
        self.original_claude = os.environ.get('CLAUDE_API_KEY')
        
        # Ensure test database doesn't interfere with production
        self.test_db = 'test_chat_history.db'
        self.original_db_name = 'chat_history.db'
        
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
            
        # Clean up test database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        # Clear any imported modules to ensure fresh import
        if 'app' in sys.modules:
            del sys.modules['app']

    def test_no_api_keys(self):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        
        with self.assertRaises(SystemExit) as cm:
            import app
        self.assertEqual(cm.exception.code, 1)

    @patch('anthropic.Anthropic')
    def test_claude_api_key_only(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Test response")]
        mock_client.messages.create.return_value = mock_response
        
        import app
        self.assertIsNotNone(app.CLAUDE_API_KEY)
        self.assertIsNone(app.OPENAI_API_KEY)

    @patch('anthropic.Anthropic')
    def test_claude_api_generic_error(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Generic Claude API Error")
        
        with self.assertRaises(SystemExit) as cm:
            import app
        self.assertEqual(cm.exception.code, 1)

    @patch('anthropic.Anthropic')
    def test_claude_get_response(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Claude response")]
        mock_client.messages.create.return_value = mock_response
        
        import app
        response = app.get_claude_response("Test question")
        self.assertEqual(response, "Claude response")
        
        # Test rate limit handling
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit exceeded"}}
        )
        with self.assertRaises(anthropic.RateLimitError):
            app.get_claude_response("Test question")

    def test_insert_question_answer(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Test normal insertion
        app.insert_question_answer("Test Q", "Test A")
        
        # Verify insertion
        conn = sqlite3.connect(app.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM chat_history")
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result[0], "Test Q")
        self.assertEqual(result[1], "Test A")

    @patch('openai.chat.completions.create')
    def test_openai_get_response(self, mock_chat_create):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='OpenAI response'))]
        mock_chat_create.return_value = mock_response
        
        response = app.get_openai_response("Test question")
        self.assertEqual(response, "OpenAI response")
        
        # Test error handling
        mock_chat_create.side_effect = Exception("OpenAI API Error")
        with self.assertRaises(Exception):
            app.get_openai_response("Test question")

    def test_chat_history_formatting(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Insert test data with bold formatting
        app.insert_question_answer(
            "Test Question",
            "This is a **bold** response"
        )
        
        response = app.app.test_client().get('/chat_history')
        self.assertIn(b'<strong>bold</strong>', response.data)

    @patch('time.sleep')  # Patch sleep to speed up tests
    def test_ask_route_retries(self, mock_sleep):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        with patch('app.get_openai_response') as mock_get_response:
            # Simulate rate limit error then success
            mock_get_response.side_effect = [
                openai.RateLimitError(
                    response=MagicMock(status_code=429),
                    body={"error": {"message": "Rate limit exceeded"}}
                ),
                "Success response"
            ]
            
            response = app.app.test_client().post(
                '/ask',
                json={'question': TEST_QUESTION}
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['answer'], "Success response")
            mock_sleep.assert_called_once()

    def test_ask_route_alternative_endpoint(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        with patch('app.get_openai_response', return_value="Test response"):
            response = app.app.test_client().post(
                '/chat/ask',
                json={'question': TEST_QUESTION}
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['question'], TEST_QUESTION)

    def test_debug_mode(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ['USE_DEBUG'] = 'true'
        
        with patch('flask.Flask.run') as mock_run:
            import app
            app.main()
            mock_run.assert_called_once_with(
                host='0.0.0.0',
                port=48080,
                debug=True
            )

if __name__ == '__main__':
    unittest.main()
