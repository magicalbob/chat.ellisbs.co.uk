#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, ANY, call
from flask import Flask
import os
import sys
import sqlite3
import openai
import anthropic
import json
from datetime import datetime
import logging

TEST_QUESTION = 'Test question'

class TestApp(unittest.TestCase):
    def setUp(self):
        # Save original environment variables
        self.original_openai = os.environ.get('OPENAI_API_KEY')
        self.original_claude = os.environ.get('CLAUDE_API_KEY')
        self.original_debug = os.environ.get('USE_DEBUG')
        
        # Ensure test database doesn't interfere with production
        self.test_db = 'test_chat_history.db'
        self.original_db_name = 'chat_history.db'
        
        # Set up logging capture
        self.log_capture = []
        self.logger = logging.getLogger('app')
        self.handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        
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
            
        if self.original_debug:
            os.environ['USE_DEBUG'] = self.original_debug
        else:
            os.environ.pop('USE_DEBUG', None)
            
        # Clean up test database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        # Remove logging handler
        self.logger.removeHandler(self.handler)
            
        # Clear any imported modules to ensure fresh import
        if 'app' in sys.modules:
            del sys.modules['app']

    def test_no_api_keys(self):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        
        with self.assertRaises(SystemExit) as cm:
            with self.assertLogs('app', level='ERROR') as log:
                import app
        self.assertEqual(cm.exception.code, 1)
        self.assertIn('Neither OPENAI_API_KEY nor CLAUDE_API_KEY environment variables are set', log.output[0])

    @patch('anthropic.Anthropic')
    def test_claude_api_validation_failure(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'invalid-claude-key'
        
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            response=MagicMock(status_code=401),
            body={"error": {"message": "Invalid API key"}}
        )
        
        with self.assertRaises(SystemExit) as cm:
            with self.assertLogs('app', level='ERROR') as log:
                import app
        self.assertEqual(cm.exception.code, 1)
        self.assertIn('Error validating Claude API key', log.output[0])

    def test_database_initialization(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Test database creation
        app.create_table()
        
        # Verify table schema
        conn = sqlite3.connect(app.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = cursor.fetchall()
        conn.close()
        
        expected_columns = {
            'id': 'INTEGER',
            'question': 'TEXT',
            'answer': 'TEXT',
            'timestamp': 'TIMESTAMP'
        }
        
        for col in columns:
            name, type_ = col[1], col[2]
            self.assertIn(name, expected_columns)
            self.assertEqual(type_, expected_columns[name])

    def test_database_error_handling(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Test database connection error
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Database error")
            with self.assertRaises(sqlite3.Error):
                app.create_table()
        
        # Test insert with non-existent table
        if os.path.exists(app.DB_NAME):
            os.remove(app.DB_NAME)
            
        app.insert_question_answer("Test Q", "Test A")
        
        # Verify table was created and data inserted
        conn = sqlite3.connect(app.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM chat_history")
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result[0], "Test Q")
        self.assertEqual(result[1], "Test A")

    @patch('anthropic.Anthropic')
    def test_claude_response_formatting(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="<p>Formatted response</p>")]
        mock_client.messages.create.return_value = mock_response
        
        import app
        response = app.get_claude_response("Format this")
        self.assertEqual(response, "<p>Formatted response</p>")
        
        # Verify API call parameters
        mock_client.messages.create.assert_called_with(
            model="claude-3-sonnet-20240229",
            messages=[{
                "role": "user",
                "content": "Format this"
            }],
            max_tokens=1024
        )

    def test_home_route_titles(self):
        test_cases = [
            ('OPENAI_API_KEY', 'test-key', None, "Chat with ChatGPT"),
            ('CLAUDE_API_KEY', 'test-key', None, "Chat with Claude"),
            (None, None, None, "Chat with No Model Available")
        ]
        
        for env_var, value, other_value, expected_title in test_cases:
            os.environ.pop('OPENAI_API_KEY', None)
            os.environ.pop('CLAUDE_API_KEY', None)
            
            if env_var:
                os.environ[env_var] = value
            
            import app
            response = app.app.test_client().get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(bytes(expected_title, 'utf-8'), response.data)
            
            if 'app' in sys.modules:
                del sys.modules['app']

    def test_chat_history_empty(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Test empty history
        response = app.app.test_client().get('/chat_history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html><body>', response.data)
        self.assertIn(b'</body></html>', response.data)
        
        # Test alternate endpoint
        response = app.app.test_client().get('/chat/chat_history')
        self.assertEqual(response.status_code, 200)

    def test_chat_history_database_error(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Database error")
            response = app.app.test_client().get('/chat_history')
            self.assertEqual(response.status_code, 500)

    @patch('time.sleep')
    def test_ask_route_multiple_retries(self, mock_sleep):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        with patch('app.get_openai_response') as mock_get_response:
            # Simulate multiple rate limit errors then success
            mock_get_response.side_effect = [
                openai.RateLimitError(
                    response=MagicMock(status_code=429),
                    body={"error": {"message": "Rate limit exceeded"}}
                ),
                openai.RateLimitError(
                    response=MagicMock(status_code=429),
                    body={"error": {"message": "Rate limit exceeded"}}
                ),
                "Final success"
            ]
            
            response = app.app.test_client().post(
                '/ask',
                json={'question': TEST_QUESTION}
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['answer'], "Final success")
            self.assertEqual(mock_sleep.call_count, 2)
            mock_sleep.assert_has_calls([call(10), call(10)])

    def test_ask_route_invalid_json(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        # Test missing question field
        response = app.app.test_client().post(
            '/ask',
            json={}
        )
        self.assertEqual(response.status_code, 400)
        
        # Test invalid JSON
        response = app.app.test_client().post(
            '/ask',
            data='invalid json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_logging_setup(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app
        
        with self.assertLogs('app', level='INFO') as log:
            app.app.test_client().post(
                '/ask',
                json={'question': TEST_QUESTION}
            )
        
        log_messages = [record.getMessage() for record in log.records]
        self.assertIn(f'Received question: {TEST_QUESTION}', log_messages)
        self.assertIn(f'Sending request to OpenAI API: {TEST_QUESTION}', log_messages)

    @patch('app.create_table')
    def test_main_function(self, mock_create_table):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ['USE_DEBUG'] = 'true'
        import app
        
        with patch('flask.Flask.run') as mock_run:
            app.main()
            mock_create_table.assert_called_once()
            mock_run.assert_called_once_with(
                host='0.0.0.0',
                port=48080,
                debug=True
            )

if __name__ == '__main__':
    unittest.main()
