# chat.ellisbs.co.uk

A Flask-based web application that serves as a relay for asking questions using OpenAI's API (chat.openai.com) or Claude's API. This project provides a simple interface where users can enter a question, and it will fetch the answer using either the OpenAI API or Claude API. Additionally, it stores chat history in a local SQLite database, allowing users to review previously asked questions and answers.

## Features

- **Question and Answer Interface**: 
  Users can input a question in the provided text box, and upon clicking the "Ask" button, the question is sent to the selected API, which returns a response.

- **Chat History Storage**:
  Each question and its corresponding answer are stored in an SQLite database, along with a timestamp. The stored chat history can be viewed in the browser.

- **HTML-formatted Responses**:
  AI-generated answers include HTML tags for enhanced formatting, making responses more readable.

- **AJAX-based Interaction**:
  The application uses JavaScript and AJAX (via jQuery) to send questions asynchronously and update the chat history dynamically without requiring a page reload.

- **Markdown Support**:
  The application leverages the showdown library to convert Markdown-style text into HTML, ensuring that text formatting from AI responses is properly rendered.

- **Retry Logic for Rate Limiting**:
  In case of rate-limiting errors from the API, the application implements a retry mechanism, with exponential backoff, to handle temporary API overloads gracefully.

## Tech Stack

- **Flask**:
  A lightweight Python web framework used to build the backend and handle routing and API interactions.

- **OpenAI API & Claude API**:
  The application can communicate with either OpenAI's GPT model or Claude's API to retrieve answers to user queries.

- **SQLite**:
  The chat history (questions and answers) is stored locally in an SQLite database.

- **HTML/CSS/JavaScript**:
  The frontend is implemented with standard HTML and CSS, enhanced using jQuery for AJAX requests.

- **Showdown.js**:
  A JavaScript library used to convert Markdown syntax to HTML to ensure proper formatting of the answers.

## Project Structure

```bash
├── app.py                   # Main Flask application
├── templates
│   ├── index.html            # Main frontend HTML template
│   ├── chat_history.html     # Template for displaying stored chat history
├── static
│   ├── script.js             # JavaScript file containing client-side logic
├── chat_history.db           # SQLite database (created at runtime)
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies
```

### app.py

- **Flask App**:
  Handles HTTP requests and serves the frontend templates (index.html). It includes routes for asking questions and retrieving chat history.
SQLite Integration: Stores all questions and answers in a local database (chat_history.db). The create_table function ensures that the database schema is initialized when the app starts.

- **OpenAI and Claude API**: 
  The `/ask` route handles communication with either OpenAI’s API or Claude’s API, sending the user's question and receiving the answer. The question and response are saved to the database.

### Frontend (index.html)

- **Question Input**:
  A textarea where users can type their questions.

- **Ask Button**:
  A button that triggers the question submission, which uses AJAX to communicate with the Flask backend.
Chat History: A dynamic section where past questions and answers are displayed. The chat history is updated in real time without requiring a page reload.

### Script.js

- **AJAX Handling**:
  Manages the interaction between the frontend and the Flask backend. It sends user questions as JSON to the server and updates the answer dynamically on the webpage.
Markdown Parsing: Uses the showdown library to convert Markdown-formatted answers from either API into HTML for display.

## Installation and Setup

### Prerequisites

- **Python 3.6+**
- **A valid OpenAI API key** (if using OpenAI API)
- **A valid Claude API key** (if using Claude API)

### Setup Instructions

- **Clone the repository**:

```bash
git clone https://github.com/yourusername/chat.ellisbs.co.uk.git
cd chat.ellisbs.co.uk
```

- **Install the required dependencies**:

```bash
pip install -r requirements.txt
```

- **Set up your OpenAI or Claude API key as an environment variable**:

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

(Optional) or 

```bash
export CLAUDE_API_KEY="your_claude_api_key_here"
```

- **Run the Flask application**:

```bash
python app.py
```

- **Open a browser and go to http://localhost:8080 to interact with the application.**

## Environment Variables

- **OPENAI_API_KEY**:
  Your OpenAI API key to access the GPT-3.5 API.

- **CLAUDE_API_KEY**:
  Your Claude API key to access Claude's API.

- **USE_DEBUG**:
  Set this to True to run the Flask app in debug mode.

## Usage

- **Open the application in your browser.**

- **Type a question in the input box.**

- **Click the "Ask" button, and the answer from the selected API will be displayed below the question.**

- **You can view your previous questions and answers by scrolling through the chat history.**

## Running in Kubernetes

This application can also be deployed in a Kubernetes environment. Please follow these steps for deployment:

1. **Build the Docker image** with the following command:

   ```bash
   docker build -t chat-app:latest .
   ```

2. **Push the Docker image** to a container registry that your Kubernetes cluster can access. For example:
   
   ```bash
   docker tag chat-app:latest docker.ellisbs.co.uk:5190/chat-app:latest
   docker push docker.ellisbs.co.uk:5190/chat-app:latest
   ```

3. **Apply the Kubernetes configuration** by running:

   ```bash
   kubectl apply -f k8s/chat-app-deployment.yaml
   ```

4. **Access the application via the LoadBalancer service**. Determine the service's external IP by running:

   ```bash
   kubectl get svc -n chat
   ```

5. **Set environment variables** for your OpenAI or Claude API key in your Kubernetes secrets. An example of the secret creation command:

   ```bash
   kubectl create secret generic openai-secret --from-literal=api_key='your_openai_api_key_here' -n chat
   ```

   (Optional) for Claude:

   ```bash
   kubectl create secret generic claude-secret --from-literal=api_key='your_claude_api_key_here' -n chat
   ```

## Retry Mechanism

If the selected API hits its rate limit, the application retries up to 5 times, with an increasing delay between attempts, to give the API time to recover from overloads.

## Database (SQLite)

The chat history is stored in an SQLite database (chat_history.db). It records:

- **The question asked by the user**
- **The response from OpenAI or Claude**
- **A timestamp indicating when the interaction occurred**

## Customization

You can easily modify the application to use different models from OpenAI or Claude or adjust the user interface. For instance:

- **Changing the AI Model**:
  In app.py, change the model argument in the API request to use a different model from OpenAI or Claude.

- **Customizing the HTML**:
  Modify templates/index.html to change the layout or styling of the input and output areas.

## Known Limitations

- **Rate Limiting**:
  Both OpenAI and Claude API have usage limits, and requests may fail if those limits are exceeded.

- **Limited Formatting**:
  The app relies on Markdown parsing for formatting, but complex HTML or CSS styling may not be supported directly.

## License

This project is licensed under the MIT License.

## Future Enhancements

* **Dynamic API Provider and Model Selection:**
    * **Objective:** Allow users to dynamically switch between different API providers (ChatGPT, Claude, Gemini) and specific models (e.g., `gpt-4o`, `gemini-1.5-flash`) before sending a message. This will enable users to choose based on performance, cost, and desired capabilities.
    * **Tasks:**
        * Integrate the Gemini API into the backend.
        * Add a UI component (e.g., dropdowns or radio buttons) for selecting the provider and model.
        * Implement backend logic to route requests to the correct API based on user selection.
        * **(Stretch Goal):** Implement a real-time cost estimation feature that calculates the expected cost of a query as the user types, based on the selected model and its token pricing.
* **Exploratory: Integration with GitHub Copilot:**
    * **Objective:** Investigate the feasibility of integrating GitHub Copilot's chat capabilities into the application, despite the lack of a public conversational API.
    * **Exploration Strategies:**
        * **Leverage the `gh` CLI:** Explore if it's possible to interface with the `gh copilot` commands programmatically from the backend to send prompts and capture responses. This would be a non-standard, potentially brittle approach, but it could serve as a proof-of-concept.
        * **Investigate Enterprise APIs:** Research the GitHub Copilot Enterprise APIs. While these are primarily for monitoring usage and managing seats, there might be endpoints or future plans for more conversational features.
        * **Analyze Third-Party Proxies/Tools:** Look into community-built proxy servers or tools that have reverse-engineered the Copilot API (as seen in some developer community discussions). This is a high-risk, non-supported approach but is a key part of an exploratory phase.
        * **Explore VS Code Integration:** Consider if a local service running alongside a VS Code instance could be used to send prompts to Copilot Chat and pipe the responses back to the web app, though this would be highly complex and not scalable.
    * **Expected Outcome:** A detailed report on the feasibility and potential implementation paths, even if a full integration isn't practical. This could lead to a future feature to assist with code-related questions.
* **User Authentication:** Add user authentication to store chat history per user.
* **Advanced Retry Mechanism:** Implement a more sophisticated retry mechanism with better error handling.
* **Database Backend:** Use a different database backend (e.g., PostgreSQL) for scalability.
* **Rich Text Formatting:** Add support for rich text formatting and images in API responses.
* **Re-asking Questions:** Add a feature to allow the re-selection of previous questions for asking.

---