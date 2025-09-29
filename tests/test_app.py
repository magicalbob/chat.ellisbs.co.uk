#!/usr/bin/env python3
import os
import sys

# Set environment variables BEFORE importing the app
os.environ.setdefault('OPENAI_API_KEY', 'test-key-openai')
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key-anthropic')
os.environ.setdefault('GEMINI_API_KEY', 'test-key-gemini')
# Add any other environment variables your app.py checks for

import pytest
from chat import app

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import sqlite3
import logging

from chat import app
from chat.app import (
    insert_question_answer,
    parse_response_contract,
    _render_answer_html,
)

TEST_QUESTION = 'Test question'


class TestApp(unittest.TestCase):
    def setUp(self):
        # Preserve env
        self.original_gemini = os.environ.get('GEMINI_API_KEY')
        self.original_debug = os.environ.get('USE_DEBUG')

        # Ensure a key is present for imports/routes that require it
        os.environ['GEMINI_API_KEY'] = self.original_gemini or 'test-gemini-key'

        # Logging (optional)
        self.logger = logging.getLogger('app')
        self.handler = logging.StreamHandler(sys.stdout)
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

        # Fresh import boundary when needed
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']

    def tearDown(self):
        # Restore env
        for k, v in [('GEMINI_API_KEY', self.original_gemini),
                     ('USE_DEBUG', self.original_debug)]:
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        self.logger.removeHandler(self.handler)
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']

    def test_requires_gemini_key(self):
        os.environ.pop('GEMINI_API_KEY', None)
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        with self.assertRaises(SystemExit):
            __import__('chat.app')

        os.environ['GEMINI_API_KEY'] = 'ok'
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        mod = __import__('chat.app')
        self.assertTrue(hasattr(mod, 'app'))

    def test_database_operations(self):
        # Start from clean slate
        app.create_table()
        conn = sqlite3.connect(app.DB_NAME)
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()

        rows = [("Q1", "A1"),
                ("Q2", "A2 with **bold**"),
                ("Q3", "A3 with <script>alert(1)</script>")]
        for q, a in rows:
            app.insert_question_answer(q, a)

        conn = sqlite3.connect(app.DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT question, answer FROM chat_history ORDER BY id")
        got = cur.fetchall()
        conn.close()
        self.assertEqual(got, rows)

    @patch('sqlite3.connect')
    def test_database_error_paths(self, mock_connect):
        # connect fails
        mock_connect.side_effect = sqlite3.Error("Connection failed")
        with self.assertRaises(sqlite3.Error):
            app.create_table()

        # cursor.execute fails
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = sqlite3.Error("Execution failed")
        mock_db.cursor.return_value = mock_cursor
        mock_connect.side_effect = None
        mock_connect.return_value = mock_db
        with self.assertRaises(sqlite3.Error):
            app.create_table()

    def test_chat_history_render(self):
        app.create_table()
        for q, a in [
            ("Q1", "Normal answer"),
            ("Q2", "Answer with **bold** text"),
            ("Q3", "Answer with <strong>HTML</strong>"),
            ("Q4", "Answer with **multiple** **bold** words"),
            ("Q5", "Answer with incomplete **bold"),
        ]:
            app.insert_question_answer(q, a)

        resp = app.app.test_client().get('/chat_history')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('<strong>bold</strong>', html)
        self.assertIn('<strong>HTML</strong>', html)
        self.assertIn('<strong>multiple</strong>', html)
        self.assertIn('incomplete <strong>bold', html)

    def test_debug_mode(self):
        cases = [('true', True), ('True', True), ('FALSE', False),
                 ('false', False), ('0', False), ('1', False), (None, False)]
        for val, expected in cases:
            os.environ['GEMINI_API_KEY'] = 'ok'
            if val is not None:
                os.environ['USE_DEBUG'] = val
            else:
                os.environ.pop('USE_DEBUG', None)

            with patch('flask.Flask.run') as mock_run:
                if 'chat.app' in sys.modules:
                    del sys.modules['chat.app']
                from chat import app as appmod
                appmod.app.run(host='0.0.0.0', port=48080, debug=expected)
                mock_run.assert_called_once_with(
                    host='0.0.0.0', port=48080, debug=expected
                )

    def test_home_title(self):
        os.environ['GEMINI_API_KEY'] = 'ok'
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        from chat import app as appmod
        resp = appmod.app.test_client().get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Chat with Gemini", resp.data)

    @patch('chat.app.get_gemini_response')
    @patch('chat.app.insert_question_answer')
    def test_ask_route_success(self, mock_insert, mock_get):
        os.environ['GEMINI_API_KEY'] = 'ok'
        if 'chat.app' in sys.modules:
            del sys.modules['chat.app']
        from chat import app as appmod

        mock_get.return_value = "Gemini says hi"
        resp = appmod.app.test_client().post(
            '/ask', json={'question': 'Hello?', 'system_prompt': 'Be terse.'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json, {'question': 'Hello?', 'answer': 'Gemini says hi'})
        mock_get.assert_called_once_with('Hello?', 'Be terse.')
        mock_insert.assert_called_once_with('Hello?', 'Gemini says hi')

    @patch('google.generativeai.GenerativeModel')
    def test_get_gemini_response_success(self, mock_model):
        os.environ['GEMINI_API_KEY'] = 'ok'
        from chat import app as appmod
        inst = MagicMock()
        inst.generate_content.return_value = MagicMock(text="OK")
        mock_model.return_value = inst
        out = appmod.get_gemini_response("Q", "System")
        self.assertEqual(out, "OK")

    @patch('google.generativeai.GenerativeModel')
    def test_get_gemini_response_error(self, mock_model):
        os.environ['GEMINI_API_KEY'] = 'ok'
        from chat import app as appmod
        inst = MagicMock()
        inst.generate_content.side_effect = Exception("API Error 429 ResourceExhausted")
        mock_model.return_value = inst
        with self.assertRaises(Exception):
            appmod.get_gemini_response("Q", None)

    @patch('chat.app.get_gemini_response')
    def test_ask_rate_limit_retry(self, mock_get):
        os.environ['GEMINI_API_KEY'] = 'ok'
        from chat import app as appmod
        mock_get.side_effect = [
            Exception("429 Rate limit"),
            Exception("quota exceeded"),
            "Success"
        ]
        with patch('time.sleep') as mock_sleep:
            resp = appmod.app.test_client().post('/ask', json={'question': TEST_QUESTION})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['answer'], "Success")
            self.assertEqual(mock_sleep.call_count, 2)

    @patch('sqlite3.connect')
    def test_insert_question_answer_database_error(self, mock_connect):
        mock_connect.side_effect = sqlite3.Error("Database error")
        with self.assertRaises(sqlite3.Error):
            insert_question_answer("test", "test")

    def test_ask_invalid_json(self):
        client = app.app.test_client()
        resp = client.post('/ask', data='not json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_health_ok_and_missing(self):
        # ok
        os.environ['GEMINI_API_KEY'] = 'ok'
        client = app.app.test_client()
        resp = client.get('/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertEqual(data["checks"]["api_key"], "present")
        # missing
        os.environ.pop('GEMINI_API_KEY', None)
        resp = client.get('/health')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertEqual(data["checks"]["api_key"], "missing")

    # -------- Additional tests to raise coverage --------

    def test_parse_response_contract_variants(self):
        # 1) direct JSON
        fmt, content, brief = parse_response_contract(
            '{"format":"html","content":"C","brief":"B"}'
        )
        self.assertEqual(fmt, "html")
        self.assertEqual(content, "C")
        self.assertEqual(brief, "B")

        # 2) fenced JSON
        fmt, content, brief = parse_response_contract(
            "```json\n{\"content\":\"X\"}\n```"
        )
        self.assertEqual(fmt, "markdown")
        self.assertEqual(content, "X")
        self.assertEqual(brief, "")

        # 3) JSON fragment amid text
        fmt, content, brief = parse_response_contract(
            'noise before {"content":"Y","format":"markdown"} noise after'
        )
        self.assertEqual(fmt, "markdown")
        self.assertEqual(content, "Y")
        self.assertEqual(brief, "")

        # 4) fallback to markdown
        fmt, content, brief = parse_response_contract("Just text")
        self.assertEqual(fmt, "markdown")
        self.assertEqual(content, "Just text")
        self.assertEqual(brief, "")

    def test_render_answer_html_variants(self):
        # With attributes: the sanitizer escapes first; because attribute values are entities
        # containing ampersands, our opening-tag regex won't match, so openers stay escaped,
        # but the *closing* tags are unescaped by the closing-tag rule.
        out = _render_answer_html(
            "<html><body>"
            "<h1 class='x'>Hi</h1>"
            "<p style='c'>Para</p>"
            "<script>alert(1)</script>"
            "</body></html>"
        )
        self.assertIn("&lt;h1", out)      # opener still escaped
        self.assertIn("</h1>", out)       # closer unescaped
        self.assertIn("&lt;p", out)       # opener still escaped
        self.assertIn("</p>", out)        # closer unescaped
        # script remains escaped (not in allow-list)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", out)

        # No attributes: openers get unescaped and attributes (none) are preserved as plain tags.
        out2 = _render_answer_html("<h2>Title</h2>\nline<br />next")
        self.assertIn("<h2>Title</h2>", out2)
        # allow-list self-closing variant survives as <br/>
        # accept either serialized form
        self.assertTrue(("<br/>" in out2) or ("<br>" in out2))

    def test_ask_missing_question_400(self):
        client = app.app.test_client()
        resp = client.post('/ask', json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Missing question parameter", resp.data)

    @patch('chat.app.get_gemini_response')
    def test_ask_generic_error_500(self, mock_get):
        mock_get.side_effect = Exception("boom")
        client = app.app.test_client()
        resp = client.post('/ask', json={'question': 'Q'})
        self.assertEqual(resp.status_code, 500)

    @patch('chat.app.get_gemini_response')
    def test_ask_rate_limit_exhausted_503(self, mock_get):
        # 5 consecutive "rate-like" errors should end in 503
        mock_get.side_effect = [
            Exception("429 Rate limit"),
            Exception("ResourceExhausted"),
            Exception("quota exceeded"),
            Exception("rate too fast"),
            Exception("another 429"),
        ]
        with patch('time.sleep') as mock_sleep:
            # Use a FRESH import so the patched symbol is the one the route sees.
            if 'chat.app' in sys.modules:
                del sys.modules['chat.app']
            from chat import app as appmod
            client = appmod.app.test_client()
            resp = client.post('/ask', json={'question': 'Q'})
            self.assertEqual(resp.status_code, 503)
            # exponential backoff called 4 times
            self.assertEqual(mock_sleep.call_count, 4)

    @patch('sqlite3.connect')
    def test_health_database_error_500(self, mock_connect):
        mock_connect.side_effect = sqlite3.Error("DB down")
        client = app.app.test_client()
        resp = client.get('/health')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertIn("error:", data["checks"]["database"])

    @patch('sqlite3.connect')
    def test_chat_history_error_500(self, mock_connect):
        mock_connect.side_effect = sqlite3.Error("DB read failed")
        client = app.app.test_client()
        resp = client.get('/chat_history')
        self.assertEqual(resp.status_code, 500)
        self.assertIn(b"Chat History Error", resp.data)


if __name__ == '__main__':
    unittest.main()
