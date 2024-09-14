chat.ellisbs.co.uk
==================

A Flask-based web application that serves as a relay for asking questions using OpenAI's API (chat.openai.com). This project provides a simple interface where users can enter a question, and it will fetch the answer using the OpenAI API. Additionally, it stores chat history in a local SQLite database, allowing users to review previously asked questions and answers.

Features
Question and Answer Interface: Users can input a question in the provided text box, and upon clicking the "Ask" button, the question is sent to OpenAI's API, which returns a response.

Chat History Storage: Each question and its corresponding answer are stored in an SQLite database, along with a timestamp. The stored chat history can be viewed in the browser.

HTML-formatted Responses: OpenAI's answers include HTML tags for enhanced formatting, such as bold text, making responses more readable.

AJAX-based Interaction: The application uses JavaScript and AJAX (via jQuery) to send questions asynchronously and update the chat history dynamically without requiring a page reload.

Markdown Support: The application leverages the showdown library to convert Markdown-style text into HTML, ensuring that text formatting from OpenAI responses is properly rendered.

Retry Logic for Rate Limiting: In case of rate-limiting errors from OpenAI, the application implements a retry mechanism, with exponential backoff, to handle temporary API overloads gracefully.

Tech Stack
Flask: A lightweight Python web framework used to build the backend and handle routing and API interactions.

OpenAI API: The application communicates with OpenAI's GPT model (gpt-3.5-turbo) to retrieve answers to user queries.

SQLite: The chat history (questions and answers) is stored locally in an SQLite database.

HTML/CSS/JavaScript: The frontend is implemented with standard HTML and CSS, and enhanced using jQuery for AJAX requests.

Showdown.js: A JavaScript library used to convert Markdown syntax to HTML to ensure proper formatting of the answers from OpenAI.

Project Structure
graphql
Copy code
├── app.py                   # Main Flask application
├── templates
│   ├── index.html            # Main frontend HTML template
│   ├── chat_history.html     # Template for displaying stored chat history
├── static
│   ├── script.js             # JavaScript file containing client-side logic
├── chat_history.db           # SQLite database (created at runtime)
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies
app.py
Flask App: Handles HTTP requests and serves the frontend templates (index.html). It includes routes for asking questions and retrieving chat history.
SQLite Integration: Stores all questions and answers in a local database (chat_history.db). The create_table function ensures that the database schema is initialized when the app starts.
OpenAI API: The /ask route handles communication with OpenAI’s API, sending the user's question and receiving the answer. The question and response are saved to the database.
Frontend (index.html)
Question Input: A textarea where users can type their questions.
Ask Button: A button that triggers the question submission, which uses AJAX to communicate with the Flask backend.
Chat History: A dynamic section where past questions and answers are displayed. The chat history is updated in real time without requiring a page reload.
Script.js
AJAX Handling: Manages the interaction between the frontend and the Flask backend. It sends user questions as JSON to the server and updates the answer dynamically on the webpage.
Markdown Parsing: Uses the showdown library to convert Markdown-formatted answers from OpenAI into HTML for display.
Installation and Setup
Prerequisites
Python 3.6+
A valid OpenAI API key
Setup Instructions
Clone the repository:

bash
Copy code
git clone https://github.com/yourusername/chat.ellisbs.co.uk.git
cd chat.ellisbs.co.uk
Install the required dependencies:

bash
Copy code
pip install -r requirements.txt
Set up your OpenAI API key as an environment variable:

bash
Copy code
export OPENAI_API_KEY="your_openai_api_key_here"
Run the Flask application:

bash
Copy code
python app.py
Open a browser and go to http://localhost:8080 to interact with the application.

Environment Variables
OPENAI_API_KEY: Your OpenAI API key to access the GPT-3.5 API.
USE_DEBUG: Set this to True to run the Flask app in debug mode.
Usage
Open the application in your browser.
Type a question in the input box.
Click the "Ask" button, and the answer from OpenAI will be displayed below the question.
You can view your previous questions and answers by scrolling through the chat history.
Retry Mechanism
If the OpenAI API hits its rate limit, the application retries up to 5 times, with an increasing delay between attempts, to give the API time to recover from overloads.

Database (SQLite)
The chat history is stored in an SQLite database (chat_history.db). It records:

The question asked by the user
The response from OpenAI
A timestamp indicating when the interaction occurred
Customization
You can easily modify the application to use different models from OpenAI or adjust the user interface. For instance:

Changing the OpenAI Model: In app.py, change the model argument in the API request to use a different GPT model.
Customizing the HTML: Modify templates/index.html to change the layout or styling of the input and output areas.
Known Limitations
Rate Limiting: The OpenAI API has usage limits, and requests may fail if those limits are exceeded.
Limited Formatting: The app relies on Markdown parsing for formatting, but complex HTML or CSS styling is not supported directly.
License
This project is licensed under the MIT License.

Future Enhancements
Add user authentication to store chat history per user.
Implement a more sophisticated retry mechanism with better error handling.
Use a different database backend (e.g., PostgreSQL) for scalability.
Add support for rich text formatting and images in OpenAI responses.
