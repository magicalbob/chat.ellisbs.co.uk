#!/usr/bin/env python3
"""
Chat web app for interacting with Google Gemini.
Stores question/answer history in a local SQLite database.

- Provider: Gemini only (google-generativeai)
- `/ask` returns {question, answer} for backward compatibility with your UI/tests
- Robust contract parsing (format/content/brief) but DB stores only `content`
- `/chat_history` server-renders with a small HTML allow-list (attributes stripped)
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

# --- Gemini client ---
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = 'chat_history.db'
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=template_dir)

# Configuration / defaults
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "In all your responses, please focus on substance over praise. "
    "Skip unnecessary compliments, engage critically with my ideas, question my assumptions, "
    "identify my biases, and offer counterpoints when relevant. Don’t shy away from disagreement, "
    "and ensure that any agreements you have are grounded in reason and evidence."
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Require a Gemini key at startup
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY is not set")
    sys.exit(1)

# Configure client (one-time)
genai.configure(api_key=GEMINI_API_KEY)
print("Using Gemini API")


# ------------------- DB helpers -------------------

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


# ------------------- Provider call -------------------

def get_gemini_response(question: str, system_prompt: str | None = None) -> str:
    """
    Query Gemini and return plain text.
    - Uses fast default model; set GEMINI_MODEL env to override (e.g. gemini-1.5-pro, gemini-2.0-flash).
    - If a system prompt is provided, send it as system_instruction.
    """
    try:
        if system_prompt:
            model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system_prompt)
        else:
            # If no explicit system prompt was given, you may choose to apply the default here.
            # Using DEFAULT_SYSTEM_PROMPT as system_instruction keeps behavior consistent.
            model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=DEFAULT_SYSTEM_PROMPT)

        logger.info("Sending request to Gemini: %s", question)
        resp = model.generate_content(question)

        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            # Try to surface reason if blocked
            reason = getattr(resp, "prompt_feedback", None)
            raise RuntimeError(f"Empty response from Gemini. Feedback: {reason}")
        logger.info("Received response from Gemini")
        return text
    except Exception:
        logger.exception("Error in Gemini API call")
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


# ------------------- Rendering helpers -------------------

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
        # Drop <html>…</html> wrapper if present
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

    # 4) Any remaining '**' (unmatched) become an opening <strong> (quirky legacy expectation)
    s = s.replace("**", "<strong>")

    # 5) Preserve newlines with <br>
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s


# ------------------- Routes -------------------

@app.route('/')
def home():
    """Render the homepage with model title."""
    title = "Chat with Gemini"
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
            # For Gemini we do not force HTML instructions; your renderer handles Markdown/HTML safely.
            raw = get_gemini_response(question, system_prompt)
            _, content, brief = parse_response_contract(raw)

            # Store only the content (keeps schema unchanged)
            insert_question_answer(question, content)

            # Back-compat return shape
            return jsonify(question=question, answer=content), 200

        except Exception as e:
            # Coarse rate-limit/backoff detection by message
            msg = str(e)
            is_rate = ("429" in msg) or ("ResourceExhausted" in msg) or ("rate" in msg.lower()) or ("quota" in msg.lower())
            if is_rate and attempt < 4:
                logger.warning("Rate/quota error (attempt %d/5): %s", attempt + 1, e)
                time.sleep(2 ** attempt)  # simple exponential backoff
                continue
            logger.exception("Unexpected error during response fetch")
            return jsonify(error=str(e)), (503 if is_rate else 500)


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


@app.route('/health', methods=['GET'])
def health():
    status = {"status": "ok", "checks": {}}
    http_status = 200

    # Check DB connectivity
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {e}"
        http_status = 500

    # Check API key presence
    if os.getenv("GEMINI_API_KEY"):
        status["checks"]["api_key"] = "present"
    else:
        status["checks"]["api_key"] = "missing"
        http_status = 500

    return jsonify(status), http_status


if __name__ == "__main__":
    create_table()
    USE_DEBUG = os.getenv("USE_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=48080, debug=USE_DEBUG)
