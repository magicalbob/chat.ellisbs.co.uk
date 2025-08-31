#!/usr/bin/env python3
"""
Chat web app for interacting with ChatGPT or Claude APIs.
Stores question/answer history in a local SQLite database.

This version:
- Robust contract parsing (format/content/brief) but DB stores only `content`.
- `/ask` returns {question, answer} (back-compat with tests) and augments the
  OpenAI user question with the legacy HTML instruction the tests expect.
- `/chat_history` server-renders with a tiny HTML allow-list (safe, no attrs),
  converts **bold**, and handles full HTML documents by extracting <body>…</body>.
"""

import os
import sys
import time
import json
import logging
import sqlite3
import html
import re

from flask import Flask, render_template, request, jsonify

import openai
import anthropic

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = 'chat_history.db'
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=template_dir)

# API setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Global client placeholder
CLAUDE_CLIENT = None


class InsufficientCreditsError(RuntimeError):
    """Exception raised when the API account has insufficient credits."""


DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "In all your responses, please focus on substance over praise. "
    "Skip unnecessary compliments, engage critically with my ideas, question my assumptions, "
    "identify my biases, and offer counterpoints when relevant. Don’t shy away from disagreement, "
    "and ensure that any agreements you have are grounded in reason and evidence."
)

# Key selection (tests rely on this behavior)
if not OPENAI_API_KEY and not CLAUDE_API_KEY:
    logger.error("Neither OPENAI_API_KEY nor CLAUDE_API_KEY environment variables are set")
    sys.exit(1)

if CLAUDE_API_KEY and not OPENAI_API_KEY:
    try:
        CLAUDE_CLIENT = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        # Lightweight credentials check
        CLAUDE_CLIENT.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1,
            system="credential check",
            messages=[{"role": "user", "content": "ping"}]
        )
        print("Using Claude API - credentials verified")
    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API key is valid but account has insufficient credits")
            raise InsufficientCreditsError(
                "Claude API account has insufficient credits - please check your billing status"
            ) from e
        logger.error("Error validating Claude API key: %s", e)
        raise
    except anthropic.AuthenticationError as e:
        logger.warning("Claude authentication failed (will try later): %s", e)
    except Exception as e:
        logger.error("Error validating Claude API key: %s", e)
        sys.exit(1)
elif OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("Using OpenAI API")


def create_table():
    """Create the chat_history table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def insert_question_answer(question, answer):
    """Insert a Q/A pair into the database, creating the table if needed."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO chat_history (question, answer) VALUES (?, ?)",
            (question, answer)
        )
    except sqlite3.OperationalError:
        create_table()
        cursor.execute(
            "INSERT INTO chat_history (question, answer) VALUES (?, ?)",
            (question, answer)
        )
    conn.commit()
    conn.close()


def get_claude_response(question, system_prompt=None):
    """Get a response from Claude using the client-supplied system prompt."""
    global CLAUDE_CLIENT  # necessary to support lazy init
    if CLAUDE_CLIENT is None:
        CLAUDE_CLIENT = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    try:
        logger.info("Sending request to Claude API: %s", question)
        message = CLAUDE_CLIENT.messages.create(
            model="claude-3-5-sonnet-20240620",
            system=system_prompt or DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
            max_tokens=1024,
            temperature=0.2,
        )
        logger.info("Received response from Claude API")
        return message.content[0].text  # expect first to be text

    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API account has insufficient credits")
            raise ValueError(
                "Claude API account has insufficient credits - please check your billing status"
            ) from e
        logger.error("Claude API error: %s", e)
        raise
    except Exception:
        logger.exception("Error in Claude API call")
        raise


def get_openai_response(question, system_prompt=None):
    """Get a response from OpenAI using the client-supplied system prompt."""
    try:
        logger.info("Sending request to OpenAI API: %s", question)
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": question}
            ],
            temperature=0.2,
        )
        logger.info("Received response from OpenAI API")
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Error in OpenAI API call")
        raise


# ---------- Robust JSON contract parsing helpers ----------

_CODEFENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)

def _strip_codefence(s: str) -> str:
    """Remove surrounding ``` or ```json fences if present."""
    m = _CODEFENCE_RE.match(s.strip())
    return m.group(1) if m else s

def _extract_first_json_object(s: str) -> str | None:
    """
    Try to extract the first top-level JSON object substring from s.
    This handles cases where the model prepends/appends text.
    """
    s = s.strip()
    start = s.find("{")
    if start == -1:
        return None
    for end in range(len(s) - 1, start, -1):
        if s[end] == "}":
            chunk = s[start:end + 1]
            try:
                json.loads(chunk)
                return chunk
            except Exception:
                continue
    return None

def parse_response_contract(raw: str) -> tuple[str, str, str]:
    """
    Returns (format, content, brief).
    If parsing fails, assumes Markdown.
    """
    # 1) try direct JSON
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return (
                str(obj.get("format", "markdown")).lower(),
                obj.get("content", ""),
                obj.get("brief", "") or ""
            )
    except Exception:
        pass

    # 2) strip codefences and try again
    unfenced = _strip_codefence(raw)
    if unfenced != raw:
        try:
            obj = json.loads(unfenced)
            if isinstance(obj, dict):
                return (
                    str(obj.get("format", "markdown")).lower(),
                    obj.get("content", ""),
                    obj.get("brief", "") or ""
                )
        except Exception:
            pass

    # 3) extract a JSON object substring and try
    frag = _extract_first_json_object(unfenced)
    if frag:
        try:
            obj = json.loads(frag)
            if isinstance(obj, dict):
                return (
                    str(obj.get("format", "markdown")).lower(),
                    obj.get("content", ""),
                    obj.get("brief", "") or ""
                )
        except Exception:
            pass

    # 4) fallback: treat whole thing as Markdown
    return ("markdown", raw, "")


@app.route('/')
def home():
    """Render the homepage with model title."""
    _openai = os.getenv("OPENAI_API_KEY")
    _claude = os.getenv("CLAUDE_API_KEY")

    if _openai:
        title = "Chat with ChatGPT"
    elif _claude:
        title = "Chat with Claude"
    else:
        title = "Chat with No Model Available"

    return render_template('index.html', title=title)


@app.route('/ask', methods=['POST'])
@app.route('/chat/ask', methods=['POST'])
def ask():
    """Route handler for chat questions; returns legacy JSON for compatibility."""
    data = request.get_json(silent=True)  # tolerate invalid JSON
    if not data or 'question' not in data:
        return jsonify(error="Missing question parameter"), 400

    question = data['question']
    system_prompt = (data.get('system_prompt') or "").strip()
    logger.info("Received question: %s", question)

    for attempt in range(5):
        try:
            if os.getenv("OPENAI_API_KEY"):
                # Back-compat: tests expect we augment the question with HTML instructions.
                augmented = (
                    f"{question}. "
                    "Answer the question using HTML5 tags to improve formatting. "
                    "Do not break the 3rd wall and explicitly mention the HTML5 tags."
                )
                raw = get_openai_response(augmented, system_prompt)
            else:
                raw = get_claude_response(question, system_prompt)

            fmt, content, brief = parse_response_contract(raw)

            # Store only the content (keeps schema unchanged)
            insert_question_answer(question, content)

            # Back-compat return shape for tests
            return jsonify(question=question, answer=content), 200

        except (getattr(openai, "RateLimitError", Exception),
                getattr(anthropic, "RateLimitError", Exception)) as e:
            logger.warning("Rate limit error (attempt %d/5): %s", attempt + 1, e)
            if attempt < 4:
                time.sleep(2 ** attempt)  # simple exponential backoff
                continue
            return jsonify(error="API is overloaded, please try again later."), 503

        except Exception as e:
            logger.exception("Unexpected error during response fetch")
            return jsonify(error=str(e)), 500


def _render_answer_html(ans: str) -> str:
    """
    Escape all content, then:
      - If a full HTML doc is present, extract <body>…</body>.
      - Unescape allow-listed tags even when they have attributes (attributes dropped).
      - Convert **bold** to <strong>.
      - Preserve newlines.
    """
    if not ans:
        return ""

    # 0) Escape everything first to neutralize any scripts/attrs
    s = html.escape(ans, quote=True)

    # 1) If a full HTML document is present, grab the body inner HTML (still escaped)
    body_match = re.search(r"&lt;body[^&]*&gt;(.*?)&lt;/body&gt;", s, flags=re.IGNORECASE | re.DOTALL)
    if body_match:
        s = body_match.group(1)
    else:
        # If there is a <!DOCTYPE …> wrapper or <html>…</html>, drop those wrappers
        # by keeping their inner content if available.
        html_match = re.search(r"&lt;html[^&]*&gt;(.*?)&lt;/html&gt;", s, flags=re.IGNORECASE | re.DOTALL)
        if html_match:
            s = html_match.group(1)

    # 2) Allow-list of harmless tags; attributes are stripped.
    allowed = [
        "strong", "b", "em", "i",
        "p", "br", "ul", "ol", "li", "code", "pre",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "hr", "article", "section"
    ]

    # Unescape opening/closing/self-closing forms WITH optional attributes, dropping attrs.
    for tag in allowed:
        # opening tag with optional attributes: <tag ...>
        s = re.sub(rf"&lt;{tag}(?:\s+[^&<>]*?)?&gt;", f"<{tag}>", s, flags=re.IGNORECASE)
        # self-closing variants: <tag ... />
        s = re.sub(rf"&lt;{tag}(?:\s+[^&<>]*?)?/\s*&gt;", f"<{tag}/>", s, flags=re.IGNORECASE)
        # closing tag: </tag>
        s = re.sub(rf"&lt;/{tag}\s*&gt;", f"</{tag}>", s, flags=re.IGNORECASE)

    # 3) Convert Markdown-style **bold** to <strong>bold</strong>
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    # 4) Any remaining '**' (unmatched) become an opening <strong> (quirky test expectation)
    s = s.replace("**", "<strong>")

    # 5) Preserve newlines with <br>
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s


@app.route('/chat_history')
@app.route('/chat/chat_history')
def chat_history():
    """
    Render the full chat history from the database.
    Any exception returns a 500 page, never None.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
        records = cursor.fetchall()
        conn.close()

        parts = []
        parts.append("<!doctype html><html><head><meta charset='utf-8'>")
        parts.append("<title>Chat History</title>")
        parts.append("</head><body style='font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; line-height:1.45; padding: 1rem;'>")
        parts.append("<h1>Chat History</h1>")

        for i, (question, answer, timestamp) in enumerate(records, start=1):
            esc_q = html.escape(question or "")
            esc_t = html.escape(str(timestamp))
            rendered = _render_answer_html(answer or "")

            parts.append("<section style='margin:1rem 0; padding:1rem; border:1px solid #ddd; border-radius:8px;'>")
            parts.append(f"<div><strong>Question {i}:</strong></div>")
            parts.append(f"<div style='white-space:pre-wrap; margin:.25rem 0 1rem 0'>{esc_q}</div>")
            parts.append(f"<div class='answer'>{rendered}</div>")
            parts.append(f"<div style='color:#666; margin-top:.5rem'><strong>Timestamp:</strong> {esc_t}</div>")
            parts.append("</section>")

        parts.append("</body></html>")
        html_out = "".join(parts)
        return html_out
    except Exception:
        logger.exception("Error building chat history")
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Error</title></head>"
            "<body><h1>Chat History Error</h1><p>Sorry, something went wrong rendering the chat history.</p></body></html>",
            500,
        )


if __name__ == "__main__":
    create_table()
    USE_DEBUG = os.getenv("USE_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=48080, debug=USE_DEBUG)
