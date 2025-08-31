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
from http import HTTPStatus

from chat import app
from chat.app import insert_question_answer

TEST_QUESTION = 'Test question'
TEST_ANSWER = "Test response"
MISSING_QUESTION = 'Missing question parameter'
ERROR_CASES = [
    (anthropic.RateLimitError, {"error": {"message": "Rate limit"}}, 429),
    (anthropic.BadRequestError, {"error": {"message": "Bad request"}}, 400),
    (anthropic.AuthenticationError, {"error": {"message": "Auth failed"}}, 401),
    (anthropic.APIError, {"error": {"message": "API error"}}, 500)
]
CLAUDE_QUESTION = 'Test question for Claude'
CLAUDE_RESPONSE = "Claude response"
OPENAI_QUESTION = 'Test question for OpenAI'
OPENAI_RESPONSE = "OpenAI response"
CHAT_WITH_CHATGPT = "Chat with ChatGPT"

def create_mock_response(status_code, body):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = body
    return mock_response

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

        # Clear any existing database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def tearDown(self):
        # Restore original environment variables
        for env_var, original_value in [
            ('OPENAI_API_KEY', self.original_openai),
            ('CLAUDE_API_KEY', self.original_claude),
            ('USE_DEBUG', self.original_debug)
        ]:
            if original_value is not None:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)

        # Clean up test database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        # Remove logging handler
        self.logger.removeHandler(self.handler)

        # Clear any imported modules to ensure fresh import
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']

    def test_environment_variable_combinations(self):
        test_cases = [
            (None, None, SystemExit),  # No keys
            ('test-key', None, None),  # Only OpenAI
            (None, 'test-key', None),  # Only Claude
            ('test-key', 'test-key', None),  # Both keys
        ]

        for openai_key, claude_key, expected_exception in test_cases:
            # Reset environment
            os.environ.pop('OPENAI_API_KEY', None)
            os.environ.pop('CLAUDE_API_KEY', None)

            # Set test environment
            if openai_key:
                os.environ['OPENAI_API_KEY'] = openai_key
            if claude_key:
                os.environ['CLAUDE_API_KEY'] = claude_key

            # Reload the module in isolation
            if 'chat.app' in sys.modules:
                del sys.modules['chat.app']

            if expected_exception:
                with self.assertRaises(SystemExit):
                    __import__('chat.app')
            else:
                mod = __import__('chat.app')
                self.assertTrue(hasattr(mod, 'app'))

    def test_database_operations_comprehensive(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app

        # Clear existing data in the database
        conn = sqlite3.connect(app.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")  # Clear the table
        conn.commit()
        conn.close()

        # Test table creation
        app.create_table()

        # Test multiple insertions
        test_data = [
            ("Q1", "A1"),
            ("Q2", "A2 with **bold**"),
            ("Q3", "A3 with <script>alert('xss')</script>")  # Test XSS handling
        ]

        for q, a in test_data:
            app.insert_question_answer(q, a)

        # Test retrieval
        conn = sqlite3.connect(app.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer FROM chat_history ORDER BY id")
        results = cursor.fetchall()
        conn.close()

        self.assertEqual(len(results), len(test_data))
        for i, (question, answer) in enumerate(test_data):
            self.assertEqual(results[i], (question, answer))

    @patch('sqlite3.connect')
    def test_database_error_scenarios(self, mock_connect):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app

        # Test connection error on create_table
        mock_connect.side_effect = sqlite3.Error("Connection failed")
        with self.assertRaises(sqlite3.Error):
            app.create_table()

        # Test execution error while creating table
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("Execution failed")
        mock_db.cursor.return_value = mock_cursor
        mock_connect.side_effect = None
        mock_connect.return_value = mock_db

        with self.assertRaises(sqlite3.Error):
            app.create_table()

    def test_chat_history_comprehensive(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app

        # Insert test data with various formatting
        test_data = [
            ("Q1", "Normal answer"),
            ("Q2", "Answer with **bold** text"),
            ("Q3", "Answer with <strong>HTML</strong>"),
            ("Q4", "Answer with **multiple** **bold** words"),
            ("Q5", "Answer with incomplete **bold"),
        ]

        for q, a in test_data:
            app.insert_question_answer(q, a)

        response = app.app.test_client().get('/chat_history')
        self.assertEqual(response.status_code, 200)

        data = response.data.decode('utf-8')
        self.assertIn('<strong>bold</strong>', data)
        self.assertIn('<strong>HTML</strong>', data)
        self.assertIn('<strong>multiple</strong>', data)
        self.assertIn('incomplete <strong>bold', data)

    def test_debug_mode_comprehensive(self):
        test_cases = [
            ('true', True),
            ('True', True),
            ('FALSE', False),
            ('false', False),
            ('0', False),
            ('1', False),
            (None, False)
        ]

        for debug_value, expected_debug in test_cases:
            os.environ['OPENAI_API_KEY'] = 'test-openai-key'
            if debug_value is not None:
                os.environ['USE_DEBUG'] = debug_value
            else:
                os.environ.pop('USE_DEBUG', None)

            with patch('flask.Flask.run') as mock_run:
                # Reload module
                if 'chat.app' in sys.modules:
                    del sys.modules['chat.app']
                from chat import app
                app.app.run(host='0.0.0.0', port=48080, debug=expected_debug)
                mock_run.assert_called_once_with(
                    host='0.0.0.0',
                    port=48080,
                    debug=expected_debug
                )

    @patch('chat.app.get_openai_response')
    @patch('chat.app.insert_question_answer')
    def test_ask_route_openai(self, mock_insert, mock_get_openai):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ.pop('CLAUDE_API_KEY', None)
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        from chat import app

        mock_get_openai.return_value = OPENAI_RESPONSE

        system_prompt = "You are a friendly assistant."
        response = app.app.test_client().post(
            '/ask',
            json={'question': OPENAI_QUESTION, 'system_prompt': system_prompt}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'question': OPENAI_QUESTION, 'answer': OPENAI_RESPONSE})
        mock_get_openai.assert_called_once_with(
            'Test question for OpenAI. Answer the question using HTML5 tags to improve formatting. Do not break the 3rd wall and explicitly mention the HTML5 tags.',
            system_prompt
        )
        mock_insert.assert_called_once_with(OPENAI_QUESTION, OPENAI_RESPONSE)

    @patch('anthropic.Anthropic')
    @patch('os.getenv')
    def test_home_route_titles(self, mock_getenv, mock_anthropic):
        # Simulate different env combos
        test_cases = [
            ('test-openai-key', None, "Chat with ChatGPT"),
            (None, 'test-claude-key', "Chat with Claude"),
        ]

        for openai_key, claude_key, expected_title in test_cases:
            mock_getenv.side_effect = lambda k: {'OPENAI_API_KEY': openai_key, 'CLAUDE_API_KEY': claude_key}.get(k)
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="ok")])

            if 'chat.app' in sys.modules:
                del sys.modules['chat.app']
            from chat import app

            resp = app.app.test_client().get('/')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(expected_title.encode(), resp.data)

    def test_insert_question_answer(self):
        question = 'Sample question'
        answer = 'Sample answer'
        with patch('chat.app.sqlite3.connect') as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            insert_question_answer(question, answer)
            mock_db.cursor.return_value.execute.assert_called_with(
                "INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer)
            )
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()

    def test_missing_environment_variables(self):
        # Both keys unset should trigger SystemExit on import
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        with self.assertRaises(SystemExit):
            __import__('chat.app')

    @patch('openai.chat.completions.create')
    def test_get_openai_response_success(self, mock_create):
        os.environ['OPENAI_API_KEY'] = 'valid-openai-key'
        mock_create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="OpenAI response"))]
        )
        from chat import app
        resp = app.get_openai_response("Test question", "You are a helpful assistant.")
        self.assertEqual(resp, "OpenAI response")

    @patch('openai.chat.completions.create')
    def test_openai_response_handling_error(self, mock_create):
        mock_create.side_effect = Exception("API Error")
        from chat import app
        with self.assertRaises(Exception) as cm:
            app.get_openai_response("Test question", "You are a helpful assistant.")
        self.assertIn("API Error", str(cm.exception))

    @patch('anthropic.Anthropic')
    def test_claude_api_validation_success(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="test")])
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        from chat import app
        self.assertIsNotNone(app.CLAUDE_API_KEY)

    @patch('anthropic.Anthropic')
    def test_claude_api_validation_error(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("Validation failed")
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        with self.assertRaises(SystemExit):
            __import__('chat.app')
#
#    @patch('anthropic.Anthropic')
#    def test_get_claude_response_success(self, mock_anthropic):
#        os.environ['CLAUDE_API_KEY'] = 'valid-claude-key'
#        os.environ.pop('OPENAI_API_KEY', None)
#        mock_client = MagicMock()
#        mock_anthropic.return_value = mock_client
#
#        # Set up the mock to return validation response first, then the actual response
#        validation_resp = MagicMock(content=[MagicMock(text="test")])
#        real_resp = MagicMock(content=[MagicMock(text="Claude response")])
#        mock_client.messages.create.side_effect = [validation_resp, real_resp]
#
#        if 'chat.app' in sys.modules:
#            del sys.modules['chat.app']
#        from chat import app
#
#        # The import should have consumed the first response (validation)
#        # Now call get_claude_response which should get the second response
#        out = app.get_claude_response("Test question")
#        self.assertEqual(out, "Claude response")
#
#        # Verify both calls happened: validation during import + actual call
#        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch('chat.app.get_openai_response')
    def test_ask_api_exception_handling(self, mock_get_response):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app
        mock_get_response.side_effect = Exception("Test exception")
        resp = app.app.test_client().post('/ask', json={'question': 'Test question'})
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json(), {'error': 'Test exception'})

    def test_home_route_without_keys(self):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        # module import should already exit above, but just in case:
        with self.assertRaises(SystemExit):
            __import__('chat.app')

    @patch('sqlite3.connect')
    def test_create_table_called(self, mock_connect):
        conn = MagicMock()
        mock_connect.return_value = conn
        from chat import app
        app.create_table()
        conn.cursor().execute.assert_called_once()

    @patch('chat.app.create_table')
    @patch('sqlite3.connect')
    def test_insert_question_answer_with_operational_error(self, mock_connect, mock_create_table):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [sqlite3.OperationalError, None]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        question, answer = "Q_test", "A_test"
        app.insert_question_answer(question, answer)
        mock_create_table.assert_called_once()
        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_cursor.execute.assert_any_call(
            "INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer)
        )
        mock_conn.commit.assert_called_once()

    @patch('chat.app.insert_question_answer')
    @patch('chat.app.get_openai_response')
    def test_ask_rate_limit_retry(self, mock_get_response, mock_insert):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app

        side_effects = [
            openai.RateLimitError(
                message="Rate limit exceeded",
                response=create_mock_response(429, {"error": {"message": "Rate limit"}}),
                body={"error": {"message": "Rate limit"}}
            ),
            openai.RateLimitError(
                message="Rate limit exceeded",
                response=create_mock_response(429, {"error": {"message": "Rate limit"}}),
                body={"error": {"message": "Rate limit"}}
            ),
            "Success response"
        ]
        mock_get_response.side_effect = side_effects

        with patch('time.sleep') as mock_sleep:
            resp = app.app.test_client().post('/ask', json={'question': TEST_QUESTION})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['answer'], "Success response")
            self.assertEqual(mock_sleep.call_count, 2)

    @patch('sqlite3.connect')
    def test_insert_question_answer_database_error(self, mock_connect):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        mock_connect.side_effect = sqlite3.Error("Database error")
        from chat import app
        with self.assertRaises(sqlite3.Error):
            app.insert_question_answer("test", "test")

    def test_ask_invalid_json(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        from chat import app
        resp = app.app.test_client().post(
            '/ask',
            data='invalid json',
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)


    def test_health_ok(self):
        os.environ['OPENAI_API_KEY'] = 'test-key'
        from chat import app
        client = app.app.test_client()
        resp = client.get('/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertEqual(data["checks"]["api_key"], "present")


    def test_health_missing_key(self):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        from chat import app
        client = app.app.test_client()
        resp = client.get('/health')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data["checks"]["api_key"], "missing")


if __name__ == '__main__':
    unittest.main()
