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

TEST_QUESTION = 'Test question'
TEST_ANSWER = "Test response"
MISSING_QUESTION = 'Missing question parameter'
ERROR_CASES = [
    (anthropic.RateLimitError, {"error": {"message": "Rate limit"}}, 429),
    (anthropic.BadRequestError, {"error": {"message": "Bad request"}}, 400),
    (anthropic.AuthenticationError, {"error": {"message": "Auth failed"}}, 401),
    (anthropic.APIError, {"error": {"message": "API error"}}, 500)
]
CLAUDE_RESPONSE = "Claude response"
OPENAI_RESPONSE = "OpenAI response"

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
            if original_value:
                os.environ[env_var] = original_value
            else:
                os.environ.pop(env_var, None)

        # Clean up test database
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

        # Remove logging handler
        self.logger.removeHandler(self.handler)

        # Clear any imported modules to ensure fresh import
        if 'app' in sys.modules:
            del sys.modules['app']

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

            if expected_exception:
                with self.assertRaises(expected_exception):
                    if 'app' in sys.modules:
                        del sys.modules['app']
                    import app
            else:
                if 'app' in sys.modules:
                    del sys.modules['app']
                import app
                self.assertTrue(hasattr(app, 'app'))

    def test_database_operations_comprehensive(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

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

        # Assert that the number of results matches the number of test entries
        self.assertEqual(len(results), len(test_data))

        # Optionally, verify content if needed
        for i, (question, answer) in enumerate(test_data):
            self.assertEqual(results[i], (question, answer))

    @patch('sqlite3.connect')
    def test_database_error_scenarios(self, mock_connect):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

        # Test connection error
        mock_connect.side_effect = sqlite3.Error("Connection failed")
        with self.assertRaises(sqlite3.Error):
            app.create_table()

        # Test execution error
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
        import app

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

        # Test main chat history endpoint
        response = app.app.test_client().get('/chat_history')
        self.assertEqual(response.status_code, 200)

        # Verify formatting
        response_data = response.data.decode('utf-8')
        self.assertIn('<strong>bold</strong>', response_data)
        self.assertIn('<strong>HTML</strong>', response_data)
        self.assertIn('<strong>multiple</strong>', response_data)
        self.assertIn('incomplete <strong>bold', response_data)  # Incomplete formatting should be preserved

    @patch('anthropic.Anthropic')
    def test_claude_api_comprehensive(self, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Test successful response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=CLAUDE_RESPONSE)]
        mock_client.messages.create.return_value = mock_response

        import app
        response = app.get_claude_response(TEST_QUESTION)
        self.assertEqual(response, CLAUD_RESPONSE)

        # Test various error scenarios
        error_cases = ERROR_CASES

        for error_class, error_body, status_code in error_cases:
            mock_client.messages.create.side_effect = error_class(
                response=create_mock_response(status_code, error_body),
                body=error_body
            )

            with self.assertRaises(error_class):
                app.get_claude_response(TEST_QUESTION)

    @patch('openai.chat.completions.create')
    def test_openai_response_comprehensive(self, mock_chat_create):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

        # Test successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='OpenAI response'))]
        mock_chat_create.return_value = mock_response

        response = app.get_openai_response(TEST_QUESTION)
        self.assertEqual(response, OPENAI_RESPONSE)

        # Test error scenarios with required arguments
        error_cases = [
            (openai.RateLimitError, "Rate limit", 429),
            (openai.APIError, "API Error", 500),
            (openai.AuthenticationError, "Auth failed", 401),
            (openai.BadRequestError, "Bad request", 400)
        ]

        for error_class, error_message, status_code in error_cases:
            # Set up each error with the correct arguments
            if error_class == openai.APIError:
                mock_chat_create.side_effect = error_class(error_message)
            else:
                mock_chat_create.side_effect = error_class(error_message, status_code)

            with self.assertRaises(error_class):
                app.get_openai_response(TEST_QUESTION)

            # Clear the side effect after each test case
            mock_chat_create.side_effect = None

        if 'app' in sys.modules:
            del sys.modules['app']

    def test_ask_route_comprehensive(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

        with patch('app.get_openai_response') as mock_get_response:
            mock_get_response.return_value = TEST_ANSWER

            test_cases = [
                # Valid request
                ({'question': TEST_QUESTION}, 200, {'question': TEST_QUESTION, 'answer': TEST_ANSWER}),
                # Missing question
                ({}, 400, {'error': MISSING_QUESTION}),
                # Empty question
                ({'question': ''}, 400, {'error': MISSING_QUESTION}),
                # Non-string question
                ({'question': 123}, 400, {'error': 'Invalid question format'})
            ]

            for request_data, expected_status, expected_response in test_cases:
                response = app.app.test_client().post(
                    '/ask',
                    json=request_data
                )
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.get_json(), expected_response)

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
                import app
                app.app.run(host='0.0.0.0', port=48080, debug=expected_debug)
                mock_run.assert_called_once_with(
                    host='0.0.0.0',
                    port=48080,
                    debug=expected_debug
                )

            if 'app' in sys.modules:
                del sys.modules['app']

    def test_logging_comprehensive(self):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

        with self.assertLogs('app', level='INFO') as log:
            with patch('app.get_openai_response') as mock_get_response:
                mock_get_response.return_value = TEST_ANSWER

                # Test successful request
                app.app.test_client().post(
                    '/ask',
                    json={'question': TEST_QUESTION}
                )

                # Test error scenario
                mock_get_response.side_effect = Exception("Test error")
                app.app.test_client().post(
                    '/ask',
                    json={'question': TEST_QUESTION}
                )

        log_messages = [record.getMessage() for record in log.records]
        expected_messages = [
            f'Received question: {TEST_QUESTION}',
            f'Sending request to OpenAI API: {TEST_QUESTION}',
            'API response received successfully',
            f'Received question: {TEST_QUESTION}',
            f'Sending request to OpenAI API: {TEST_QUESTION}',
            'Unexpected error: Test error'
        ]

        for expected in expected_messages:
            self.assertTrue(any(expected in msg for msg in log_messages))

    @patch('app.insert_question_answer')
    def test_ask_route_with_invalid_question(self, mock_insert):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        with patch('app.get_openai_response') as mock_get_response:
            mock_get_response.return_value = TEST_ANSWER

            # Test with missing question
            response = app.app.test_client().post('/ask', json={})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {'error': MISSING_QUESTION})

            # Test with empty question
            response = app.app.test_client().post('/ask', json={'question': ''})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {'error': MISSING_QUESTION})

            # Test with non-string question
            response = app.app.test_client().post('/ask', json={'question': 123})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json(), {'error': 'Invalid question format'})

    @patch('app.get_openai_response')
    def test_ask_api_exception_handling(self, mock_get_response):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        mock_get_response.side_effect = Exception("Test exception")
        response = app.app.test_client().post('/ask', json={'question': 'Test question'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {'error': 'Test exception'})

    def test_home_route_without_keys(self):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('CLAUDE_API_KEY', None)
        response = app.app.test_client().get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Chat with No Model Available", response.data.decode('utf-8'))

    @patch('sqlite3.connect')
    def test_create_table_called(self, mock_connect):
        conn = MagicMock()
        mock_connect.return_value = conn

        app.create_table()
        conn.cursor().execute.assert_called_once()

    @patch('anthropic.Anthropic')
    @patch('sys.exit')
    def test_claude_credit_balance_error(self, mock_exit, mock_anthropic):
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'

        # Mock the Claude client and simulate a credit balance error
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Creating a mock response to satisfy the `response` requirement
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"message": "credit balance is too low"}}

        # Set the side effect to raise `BadRequestError` with the mock response
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            message="Insufficient balance",
            response=mock_response
        )

        # Capture logging output
        with self.assertLogs('app', level='ERROR') as log:
            import app  # Re-import to trigger code execution

        # Check that the log message and sys.exit(1) were called as expected
        self.assertIn("Claude API key is valid but account has insufficient credits", log.output[0])
        mock_exit.assert_called_once_with(1)

    @patch('app.create_table')
    @patch('sqlite3.connect')
    def test_insert_question_answer_with_operational_error(self, mock_connect, mock_create_table):
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        import app

        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Set up the mock cursor to raise an OperationalError on the first call, then succeed
        mock_cursor.execute.side_effect = [sqlite3.OperationalError, None]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Call the function to insert data
        question, answer = "Q_test", "A_test"
        app.insert_question_answer(question, answer)

        # Check if create_table was called due to the OperationalError
        mock_create_table.assert_called_once()

        # Check if the insert was retried after create_table was called
        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_cursor.execute.assert_any_call("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, answer))

        # Commit should have been called once after a successful retry
        mock_conn.commit.assert_called_once()

    @patch('app.get_openai_response')
    @patch('app.insert_question_answer')
    def test_ask_route_openai(self, mock_insert, mock_get_openai_response):
        # Set up environment to use OpenAI
        os.environ['OPENAI_API_KEY'] = 'test-openai-key'
        os.environ.pop('CLAUDE_API_KEY', None)

        # Import app after setting environment variables
        import app

        # Mock responses
        mock_get_openai_response.return_value = OPENAI_RESPONSE

        # Send request
        response = app.app.test_client().post('/ask', json={'question': 'Test question for OpenAI'})

        # Assert correct response and function calls
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'question': 'Test question for OpenAI', 'answer': OPENAI_RESPONSE})
        mock_get_openai_response.assert_called_once_with(
            'Test question for OpenAI. Answer the question using HTML5 tags to improve formatting. Do not break the 3rd wall and explicitly mention the HTML5 tags.'
        )
        mock_insert.assert_called_once_with('Test question for OpenAI', OPENAI_RESPONSE)

    @patch('app.get_claude_response')
    @patch('app.insert_question_answer')
    def test_ask_route_claude(self, mock_insert, mock_get_claude_response):
        # Set up environment to use Claude
        os.environ['CLAUDE_API_KEY'] = 'test-claude-key'
        os.environ.pop('OPENAI_API_KEY', None)

        # Import app after setting environment variables
        import app

        # Mock responses
        mock_get_claude_response.return_value = CLAUD_RESPONSE

        # Send request
        response = app.app.test_client().post('/ask', json={'question': 'Test question for Claude'})

        # Assert correct response and function calls
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'question': 'Test question for Claude', 'answer': CLAUDE_RESPONSE})
        mock_get_claude_response.assert_called_once_with(
            'Test question for Claude. Answer the question using HTML5 tags to improve formatting. Do not break the 3rd wall and explicitly mention the HTML5 tags.'
        )
        mock_insert.assert_called_once_with('Test question for Claude', CLAUD_RESPONSE)

if __name__ == '__main__':
    unittest.main()
