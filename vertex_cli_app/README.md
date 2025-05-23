# Vertex AI CLI Application

## Description

The Vertex AI CLI Application is a modular, command-line interface designed to interact with Google Cloud's Vertex AI Gemini models. It provides a suite of tools for generative AI tasks, including an interactive chat mode, robust conversation history management, prompt template organization, and the ability to define and switch between different AI persona/role profiles. The application also integrates search capabilities to augment AI responses with up-to-date information.

## Features

*   **Interactive Chat:** Engage in conversations with Vertex AI's Gemini models.
*   **Conversation History:** Automatically log conversations and load them for review or continuation.
*   **Prompt Template Management:** Save frequently used prompts, list them, and load them for use.
*   **System Instruction/Role Profile Management:** Create, save, list, and switch between different system instruction profiles to guide AI behavior.
*   **Search Capabilities:**
    *   Utilize Google Custom Search for targeted web searches.
    *   Leverage Vertex AI Search (Grounding) for AI responses augmented with search results.
*   **Multiline Input Mode:** A dedicated textbox mode for composing longer, structured prompts or messages.
*   **Command-Line Interface:** A rich CLI with a built-in help system for easy discoverability of commands.
*   **AI-Generated Descriptions:** Automatic generation of concise descriptions for conversation logs and saved prompt templates.

## Prerequisites

*   Python 3.10 or higher.
*   A Google Cloud Project with the Vertex AI API enabled.
*   `gcloud` command-line tool installed and authenticated with Google Cloud: [Install gcloud](https://cloud.google.com/sdk/docs/install). Application Default Credentials (ADC) are used for authentication.
*   **(Optional)** For the Google Custom Search feature:
    *   A Google Custom Search Engine ID (CX ID).
    *   A Google Cloud API Key enabled for the Custom Search API.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url> 
    # Replace <repository_url> with the actual URL of the repository
    ```
2.  **Navigate to the application directory:**
    ```bash
    cd vertex_cli_app 
    # Or the root directory containing vertex_cli_app
    ```
3.  **Install dependencies:**
    A `requirements.txt` file is provided. Install the necessary packages using pip:
    ```bash
    pip install -r requirements.txt 
    # If requirements.txt is inside vertex_cli_app, adjust path accordingly:
    # pip install -r vertex_cli_app/requirements.txt
    ```

## Configuration

### Environment Variables

The application requires the following environment variables to be set:

*   `GCP_PROJECT_ID`: Your Google Cloud Project ID.
*   `GCP_LOCATION`: The Google Cloud region where you want to run Vertex AI tasks (e.g., `us-central1`).
*   `GOOGLE_SEARCH_API_KEY` (Optional): Your API key for Google Custom Search. Required if using the `use cs` (custom search) feature.
*   `GOOGLE_SEARCH_CX` (Optional): Your Google Custom Search Engine ID (CX ID). Required if using the `use cs` feature.

You can set these in your shell environment or using a `.env` file (though `.env` handling is not built into this version and would require additional libraries like `python-dotenv`).

### Authentication

This application uses Application Default Credentials (ADC) for authenticating with Google Cloud services. Ensure you have authenticated via the `gcloud` CLI:

```bash
gcloud auth application-default login
```

## Usage

Run the application from the root directory of the cloned repository:

```bash
python vertex_cli_app/app.py [options]
```

### Options

*   `--session-name <NAME>`: Specify a custom name for the current chat session. This name will be used as a prefix for the log filename.
*   `--load-log [FILENAME|latest]`: Load a conversation from a log file.
    *   If `FILENAME` is provided, it attempts to load that specific file from the log directory.
    *   If `latest` is provided (or the option is used without a value), it loads the most recent log file.
*   `--custom-search`: Start the application with Google Custom Search enabled as the default search method. Requires `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_CX` to be set.
*   `--vertex-ai-search`: Start the application with Vertex AI Search (Grounding) enabled. This is the default search method if no search flag is specified.

### Interactive Commands

Once the application is running, you can use various commands. Type `help` to see the full list. Some key commands include:

*   `help [command]`: Display help for all commands or a specific command.
*   `search <query>`: Perform a search using the currently active search method (if not disabled) and use the results to inform the AI's response to the query.
*   `lookup <query>`: Perform a quick web search using Vertex AI Search without affecting conversation history.
*   `ask <query>`: Ask a quick question using the standard Vertex model without affecting conversation history.
*   `use role <name|index>`: Switch to a saved system instruction/role profile.
*   `load <log_filename|index|latest>`: Load a previous conversation log.
*   `logs`: List all saved conversation logs.
*   `prompts`: List all saved prompt templates.
*   `instructions`: List all saved instruction profiles.
*   `textbox` or `wm`: Open a multiline editor for complex input.
*   `exit` or `quit`: Exit the application.

Any input not recognized as a command is treated as a prompt to the AI.

## Directory Structure

```
vertex_cli_app/
├── ai_core/                  # Core Vertex AI interaction logic (VertexAIHandler)
├── cli/                      # Command line parsing (CLIParser)
├── conversation/             # Conversation history management (ConversationManager)
├── database/                 # SQLite database management for logs (LogDatabase)
├── instructions/             # Management of instruction/role profiles (InstructionManager)
├── prompts/                  # Management of prompt templates (PromptManager)
├── search/                   # Search functionalities (SearchHandler, tools)
├── tests/                    # Unit tests for the application modules
│   ├── __init__.py
│   └── test_*.py
├── ui/                       # User interface rendering (UIRenderer, command_help)
├── utils/                    # Common utilities and type definitions
├── app.py                    # Main application entry point and core logic
├── README.md                 # This file
├── requirements.txt          # Python package dependencies
└── run_tests.py              # Script to discover and run unit tests
```

## Testing

To run the unit tests for the application:

```bash
python vertex_cli_app/run_tests.py
```

Make sure you are in the root directory of the cloned repository when running the test script.
