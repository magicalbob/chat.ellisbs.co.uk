#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, ANY, call
from flask import Flask
import os
import sqlite3
import openai
import anthropic
import app
from app import insert_question_answer

TEST_QUESTION = "Test question"
TEST_ANSWER = "Test response"
MISSING_QUESTION = "Missing question parameter"
CLAUDE_QUESTION = "Test question for Claude"
CLAUDE_RESPONSE = "Claude response"
OPENAI_QUESTION = "Test question for OpenAI"
OPENAI_RESPONSE = "OpenAI response"
GET_OPENAI_RESPONSE = "app.get_openai_response"

ERROR_CASES = [
    (anthropic.RateLimitError, {"error": {"message": "Rate limit"}}, 429),
    (anthropic.BadRequestError, {"error": {"message": "Bad request"}}, 400),
    (anthropic.AuthenticationError, {"error": {"message": "Auth failed"}}, 401),
    (anthropic.APIError, {"error": {"message": "API error"}}, 500),
]


def create_mock_response(status_code, body):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = body
    return mock_response


class TestApp(unittest.TestCase):
    def setUp(self):
        self.original_openai = os.environ.get("OPENAI_API_KEY")
        self.original_claude = os.environ.get("CLAUDE_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-openai-key"

    def tearDown(self):
        if self.original_openai:
            os.environ["OPENAI_API_KEY"] = self.original_openai
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        if self.original_claude:
            os.environ["CLAUDE_API_KEY"] = self.original_claude
        else:
            os.environ.pop("CLAUDE_API_KEY", None)

    @patch("app.get_openai_response")
    def test_ask_route_comprehensive(self, mock_get_response):
        mock_get_response.return_value = TEST_ANSWER

        test_cases = [
            ({"question": TEST_QUESTION}, 200, {"question": TEST_QUESTION, "answer": TEST_ANSWER}),
            ({}, 400, {"error": MISSING_QUESTION}),
            ({"question": ""}, 400, {"error": MISSING_QUESTION}),
        ]

        for input_data, expected_status, expected_response in test_cases:
            response = app.app.test_client().post("/ask", json=input_data)
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.get_json(), expected_response)

    @patch("anthropic.Anthropic")
    def test_claude_api_comprehensive(self, mock_anthropic):
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ["CLAUDE_API_KEY"] = "test-claude-key"

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock a successful response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=CLAUDE_RESPONSE)]
        mock_client.messages.create.return_value = mock_response

        response = app.get_claude_response(CLAUDE_QUESTION)
        self.assertEqual(response, CLAUDE_RESPONSE)

        # Test error scenarios
        for error_class, error_body, _ in ERROR_CASES:
            mock_client.messages.create.side_effect = error_class(
                message=error_body["error"]["message"]
            )
            with self.assertRaises(error_class):
                app.get_claude_response(CLAUDE_QUESTION)

    @patch("openai.chat.completions.create")
    def test_openai_response_comprehensive(self, mock_chat_create):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=OPENAI_RESPONSE))]
        mock_chat_create.return_value = mock_response

        response = app.get_openai_response(OPENAI_QUESTION)
        self.assertEqual(response, OPENAI_RESPONSE)

        for error_class, error_message, _ in ERROR_CASES:
            mock_chat_create.side_effect = error_class(message=error_message)
            with self.assertRaises(error_class):
                app.get_openai_response(OPENAI_QUESTION)

    @patch("app.get_openai_response")
    @patch("app.insert_question_answer")
    def test_ask_route_openai(self, mock_insert, mock_get_openai_response):
        mock_get_openai_response.return_value = OPENAI_RESPONSE

        response = app.app.test_client().post("/ask", json={"question": OPENAI_QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"question": OPENAI_QUESTION, "answer": OPENAI_RESPONSE})

    def test_logging_comprehensive(self):
        with self.assertLogs("app", level="INFO") as log:
            with patch(GET_OPENAI_RESPONSE) as mock_get_response:
                mock_get_response.return_value = TEST_ANSWER
                app.app.test_client().post("/ask", json={"question": TEST_QUESTION})

        log_messages = [record.getMessage() for record in log.records]
        self.assertIn(f"Received question: {TEST_QUESTION}", log_messages)
        self.assertIn("API response received successfully", log_messages)

    @patch("sqlite3.connect")
    def test_database_error_handling(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.execute.side_effect = [sqlite3.OperationalError, None]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        insert_question_answer("Q_test", "A_test")
        self.assertEqual(mock_cursor.execute.call_count, 2)

    def test_home_route(self):
        response = app.app.test_client().get("/")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
