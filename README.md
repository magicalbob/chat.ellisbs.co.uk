chat.ellisbs.co.uk
==================

A Flask-based web application that provides a conversational interface to Google Gemini. Users can ask questions through a web interface, and the application fetches responses from the Gemini API. All interactions are stored in a local SQLite database for chat history review.

Features
--------

-   **Question and Answer Interface**: Users input questions in a text box, click "Ask", and receive responses from Google Gemini.

-   **Chat History Storage**: Each question and answer is stored in an SQLite database with timestamps. Chat history can be viewed in the browser.

-   **HTML-formatted Responses**: Responses support HTML formatting with a security-conscious sanitization approach that allows safe tags while stripping attributes and blocking scripts.

-   **AJAX-based Interaction**: The application uses JavaScript and AJAX (via jQuery) to send questions asynchronously and update chat history dynamically without page reloads.

-   **Markdown Support**: The application leverages the showdown library on the frontend to convert Markdown-formatted responses into HTML.

-   **Retry Logic for Rate Limiting**: Implements exponential backoff retry mechanism (up to 5 attempts) to handle API rate limits and quota exhaustion gracefully.

-   **Robust Response Parsing**: Handles responses in multiple formats including plain text, JSON contracts with format/content/brief fields, and JSON wrapped in code fences.

Tech Stack
----------

-   **Flask**: Lightweight Python web framework handling routing and backend logic.

-   **Google Gemini API**: Uses the `google-generativeai` Python library to communicate with Gemini models (default: `gemini-1.5-flash`).

-   **SQLite**: Local database for storing chat history.

-   **HTML/CSS/JavaScript**: Frontend implemented with standard web technologies, enhanced with jQuery for AJAX requests.

-   **Showdown.js**: JavaScript library for Markdown to HTML conversion on the client side.

Project Structure
-----------------

```
├── src/
│   └── chat/
│       ├── app.py              # Main Flask application
│       └── templates/
│           └── index.html       # Frontend template
├── tests/
│   ├── conftest.py             # Test configuration
│   └── test_app.py             # Comprehensive test suite
├── Dockerfile                   # Container definition
├── pyproject.toml              # Python package configuration
├── package.json                # JavaScript dependencies and test config
└── README.md                   # This file

```

### app.py

-   **Flask Application**: Serves the web interface and handles API routes.
-   **SQLite Integration**: Stores all Q&A pairs with timestamps in `chat_history.db`.
-   **Gemini Integration**: The `/ask` route sends questions to Gemini and returns answers in a backward-compatible JSON format `{question, answer}`.
-   **Security**: HTML rendering includes comprehensive sanitization with an allow-list approach that strips all attributes from permitted tags.
-   **Health Check**: `/health` endpoint verifies database connectivity and API key presence.

### Frontend (index.html)

-   **Question Input**: Textarea for typing questions.
-   **Ask Button**: Triggers AJAX submission to the Flask backend.
-   **Chat History**: Dynamically updated section displaying previous Q&A pairs.

Installation and Setup
----------------------

### Prerequisites

-   Python 3.12 or 3.13
-   A valid Google Gemini API key

### Setup Instructions

1.  **Clone the repository**:

```
git clone https://github.com/yourusername/chat.ellisbs.co.uk.git
cd chat.ellisbs.co.uk

```

1.  **Install the package**:

```
pip install -e .

```

1.  **Set up your Gemini API key as an environment variable**:

```
export GEMINI_API_KEY="your_gemini_api_key_here"

```

1.  **Optionally configure the model** (default is `gemini-1.5-flash`):

```
export GEMINI_MODEL="gemini-1.5-pro"  # or gemini-2.0-flash

```

1.  **Run the Flask application**:

```
python src/chat/app.py

```

1.  **Open a browser and navigate to** `http://localhost:48080`

Environment Variables
---------------------

-   **GEMINI_API_KEY** (required): Your Google Gemini API key.

-   **GEMINI_MODEL** (optional): Gemini model to use (default: `gemini-1.5-flash`). Other options include `gemini-1.5-pro` or `gemini-2.0-flash`.

-   **DEFAULT_SYSTEM_PROMPT** (optional): Custom system instruction for the model. Defaults to a prompt encouraging critical, substantive responses.

-   **USE_DEBUG** (optional): Set to `True` to run Flask in debug mode.

Usage
-----

1.  Open the application in your browser at `http://localhost:48080`
2.  Type your question in the input box
3.  Optionally provide a custom system prompt
4.  Click "Ask" and the Gemini response will display below
5.  View chat history at `/chat_history`

Running in Docker/Kubernetes
----------------------------

### Docker

Build and run the Docker image:

```
docker build -t chat-app:latest .
docker run -p 48080:48080 -e GEMINI_API_KEY="your_key" chat-app:latest

```

### Kubernetes

1.  **Build and push the image**:

```
docker build -t chat-app:latest .
docker tag chat-app:latest docker.ellisbs.co.uk:5190/chat-app:latest
docker push docker.ellisbs.co.uk:5190/chat-app:latest

```

1.  **Create a secret for your API key**:

```
kubectl create secret generic gemini-secret --from-literal=api_key='your_gemini_api_key' -n chat

```

1.  **Apply your Kubernetes manifests**:

```
kubectl apply -f k8s/chat-app-deployment.yaml

```

1.  **Check the service**:

```
kubectl get svc -n chat

```

API Endpoints
-------------

-   `GET /` - Main chat interface
-   `POST /ask` - Submit a question (JSON: `{question, system_prompt?}`)
-   `GET /chat_history` - View all stored Q&A pairs
-   `GET /health` - Health check endpoint

Testing
-------

The project includes comprehensive unit tests covering:

-   Database operations and error handling
-   API integration and retry logic
-   Response parsing and HTML sanitization
-   Route handlers and error responses

Run tests with:

```
pytest

```

For JavaScript tests:

```
npm test

```

Retry Mechanism
---------------

When the Gemini API returns rate limit or quota errors (429, ResourceExhausted), the application automatically retries up to 5 times with exponential backoff (1s, 2s, 4s, 8s delays). After exhausting retries, it returns a 503 status.

Database Schema
---------------

SQLite table `chat_history`:

-   `id` - Auto-incrementing primary key
-   `question` - User's question (TEXT)
-   `answer` - Gemini's response content (TEXT)
-   `timestamp` - When the interaction occurred (TIMESTAMP)

Security Considerations
-----------------------

-   HTML responses are sanitized with an allow-list approach
-   All content is HTML-escaped first, then only safe tags are selectively unescaped
-   Tag attributes are stripped to prevent XSS attacks
-   Script tags and other dangerous elements remain escaped

Known Limitations
-----------------

-   **Rate Limiting**: Google Gemini API has usage quotas; requests may fail if limits are exceeded despite retry logic.
-   **Model Context**: Context is not maintained between requests; each question is independent.
-   **Local Storage Only**: Chat history is stored in a local SQLite file, not suitable for distributed deployments without shared storage.

Future Enhancements
-------------------

-   **Multi-Provider Support**: Reintroduce OpenAI and Claude as alternative providers with dynamic selection
-   **Conversation Context**: Maintain multi-turn conversations with context history
-   **User Authentication**: Store separate chat histories per user
-   **Database Backend**: Migrate to PostgreSQL for production scalability
-   **Streaming Responses**: Implement server-sent events for real-time response streaming
-   **Cost Tracking**: Monitor API usage and estimated costs
-   **Re-asking Questions**: Allow re-selection of previous questions from history

License
-------

This project is licensed under the MIT License.
