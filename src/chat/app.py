#!/usr/bin/env python3
"""
Chat web app for interacting with ChatGPT or Claude APIs.
Stores question/answer history in a local SQLite database.

This version:
- Uses a stable system prompt that requests a JSON "response contract"
  with keys: format (markdown|html|text), content, brief.
- Leaves the user question untouched (no HTML meta-prompt).
- Robustly parses the model's JSON; falls back to treating output as Markdown.
- Returns {format, content, brief} to the client for client-side rendering.
- Keeps the original SQLite schema (no 'format' column).
- Enhances /chat_history to render stored content nicely using markdown-it.
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


# System prompt for Markdown-first contract
SYSTEM_PROMPT_MD = """\
You are a concise, helpful assistant.

Formatting rules:
- Write answers in GitHub-flavored Markdown (GFM).
- Use headings, short paragraphs, bullet lists, and code fences where helpful.
- Prefer Markdown tables over HTML tables.
- Do NOT mention that you are using Markdown or that you are following formatting rules.
- If the user asks for raw HTML, you may use HTML; otherwise stick to Markdown.
- When including code, use fenced blocks with an accurate language tag.
- Keep links as plain Markdown links; do not auto-embed scripts.

Response contract (important):
Return a JSON object with these keys:
- "format": one of ["markdown", "html", "text"]  (default: "markdown")
- "content": the answer body in that format
- "brief": a ≤100-character plain-text summary/title of the answer (optional)

Do not include any additional keys. Do not wrap the JSON in backticks.
"""

# Basic API key validation / selection
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


def get_claude_response(question, system_prompt=SYSTEM_PROMPT_MD):
    """Get a response from Claude using the Markdown contract."""
    global CLAUDE_CLIENT  # necessary to support lazy init
    if CLAUDE_CLIENT is None:
        CLAUDE_CLIENT = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    try:
        logger.info("Sending request to Claude API: %s", question)
        message = CLAUDE_CLIENT.messages.create(
            model="claude-3-5-sonnet-20240620",
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
            max_tokens=1024,
            temperature=0.2,
        )
        logger.info("Received response from Claude API")
        # Anthropic returns a list of content blocks; we expect first to be text
        return message.content[0].text

    except anthropic.BadRequestError as e:
        if "credit balance is too low" in str(e):
            logger.error("Claude API account has insufficient credits")
            raise ValueError(
                "Claude API account has insufficient credits - please check your billing status"
            ) from e
        logger.error("Claude API error: %s", e)
        raise
    except Exception as e:
        logger.exception("Error in Claude API call")
        raise


def get_openai_response(question, system_prompt=SYSTEM_PROMPT_MD):
    """Get a response from OpenAI using the Markdown contract."""
    try:
        logger.info("Sending request to OpenAI API: %s", question)
        response = openai.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.2,
        )
        logger.info("Received response from OpenAI API")
        return response.choices[0].message.content.strip()
    except Exception as e:
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
    # Greedy from the end; attempt progressively shorter tails
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
    """Route handler for chat questions; returns JSON contract for client rendering."""
    data = request.json
    if not data or 'question' not in data:
        return jsonify(error="Missing question parameter"), 400

    question = data['question']
    logger.info("Received question: %s", question)

    for attempt in range(5):
        try:
            if os.getenv("OPENAI_API_KEY"):
                raw = get_openai_response(question, SYSTEM_PROMPT_MD)
            else:
                raw = get_claude_response(question, SYSTEM_PROMPT_MD)

            fmt, content, brief = parse_response_contract(raw)

            # Store only the content (keeps schema unchanged)
            insert_question_answer(question, content)

            return jsonify(question=question, format=fmt, content=content, brief=brief)

        except (getattr(openai, "RateLimitError", Exception), getattr(anthropic, "RateLimitError", Exception)) as e:
            logger.warning("Rate limit error (attempt %d/5): %s", attempt + 1, e)
            if attempt < 4:
                time.sleep(2 ** attempt)  # simple exponential backoff
                continue
            return jsonify(error="API is overloaded, please try again later."), 503

        except Exception as e:
            logger.exception("Unexpected error during response fetch")
            return jsonify(error=str(e)), 500


@app.route('/chat_history')
@app.route('/chat/chat_history')
def chat_history():
    """
    Render the full chat history from the database.

    This now ships a tiny page that:
    - embeds each answer in a data-* attribute,
    - uses markdown-it client-side to render,
    - treats the stored text as Markdown by default.
    (No schema change; we don't know/need the original "format" here.)
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT question, answer, timestamp FROM chat_history ORDER BY id ASC")
    records = cursor.fetchall()
    conn.close()

    # Build lightweight HTML with client-side Markdown rendering
    # We will HTML-escape the data-content so it’s safe to inject,
    # then decode and render via markdown-it on the client.
    parts = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append("<title>Chat History</title>")
    # markdown-it CDN
    parts.append("<script src='https://cdn.jsdelivr.net/npm/markdown-it/dist/markdown-it.min.js'></script>")
    parts.append("</head><body style='font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; line-height:1.45; padding: 1rem;'>")
    parts.append("<h1>Chat History</h1>")

    for i, (question, answer, timestamp) in enumerate(records, start=1):
        # Escape content for safe embedding in data attribute
        esc_q = html.escape(question or "")
        esc_a = html.escape(answer or "")
        esc_t = html.escape(str(timestamp))

        parts.append("<section style='margin:1rem 0; padding:1rem; border:1px solid #ddd; border-radius:8px;'>")
        parts.append(f"<div><strong>Question {i}:</strong></div>")
        parts.append(f"<div style='white-space:pre-wrap; margin:.25rem 0 1rem 0'>{esc_q}</div>")
        # We'll render the answer in this container
        parts.append(f"<div class='answer' data-content='{esc_a}'></div>")
        parts.append(f"<div style='color:#666; margin-top:.5rem'><strong>Timestamp:</strong> {esc_t}</div>")
        parts.append("</section>")

    # Client-side renderer: treat data-content as either JSON contract or raw markdown
    parts.append("""
<script>
(function(){
  var md = window.markdownit({html: false, linkify: true, breaks: true});
  function renderBlock(el){
    var raw = el.getAttribute('data-content') || '';
    // Unescape HTML entities we stored in the attribute
    var txt = raw
      .replace(/&lt;/g,'<')
      .replace(/&gt;/g,'>')
      .replace(/&amp;/g,'&')
      .replace(/&quot;/g,'"')
      .replace(/&#39;/g,"'");

    function tryParseContract(s){
      // Try direct JSON
      try { return JSON.parse(s); } catch(e){}
      // Try to strip ```json fences
      var m = s.trim().match(/^```(?:json)?\\s*([\\s\\S]*?)\\s*```$/i);
      if (m) {
        try { return JSON.parse(m[1]); } catch(e){}
      }
      // Try to extract first {...}
      var start = s.indexOf('{');
      if (start >= 0) {
        for (var end = s.length - 1; end > start; end--) {
          if (s[end] === '}') {
            var frag = s.slice(start, end+1);
            try { return JSON.parse(frag); } catch(e){}
          }
        }
      }
      return null;
    }

    var obj = tryParseContract(txt);
    var fmt = 'markdown';
    var content = txt;

    if (obj && typeof obj === 'object') {
      if ('content' in obj) content = String(obj.content ?? '');
      if ('format' in obj) fmt = String(obj.format || 'markdown').toLowerCase();
    }

    if (fmt === 'html') {
      // If you want to sanitize, do it here before assigning innerHTML.
      el.innerHTML = content;
    } else if (fmt === 'text') {
      el.textContent = content;
    } else {
      el.innerHTML = md.render(content);
    }
  }

  document.querySelectorAll('.answer').forEach(renderBlock);
})();
</script>
    """)

    parts.append("</body></html>")
    return "".join(parts)


if __name__ == "__main__":
    create_table()
    USE_DEBUG = os.getenv("USE_DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=48080, debug=USE_DEBUG)
