"""
Vertex AI CLI - Enhanced command-line interface for Google's Vertex AI with:
- Conversation history management
- Prompt templates
- Web search integration (disabled by default)
- System instructions
- Context-aware search results
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import textwrap
import time
import atexit
from enum import Enum
from pathlib import Path

import requests
from colorama import init, Fore, Style as ColoramaStyle
# Replace Gemini imports with Vertex AI imports
from vertexai import generative_models
from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part
from vertexai.preview.generative_models import Tool, FunctionDeclaration, GenerationConfig
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PromptStyle
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from utils.common_types import SearchMethod, get_formatted_datetime_info
from rich.theme import Theme

from system_instructions import InstructionManager, update_log_tags

# Initialize colorama
init(autoreset=True)

# Get terminal width for proper text wrapping
terminal_width = shutil.get_terminal_size().columns
console = Console(width=terminal_width, highlight=False)

# --- Helper function to detect queries that don't need web searches ---
def is_simple_query(query):
    """
    Check if the query appears to be a simple calculation or non-search operation.
    Returns True if the query seems like it doesn't need a web search.
    """
    # Check for arithmetic operations/calculations
    calc_patterns = [
        r'\d+\s*[\+\-\*\/\%\^]\s*\d+',  # Basic arithmetic (3*3, 5+2, etc)
        r'calculate\s+',                 # Explicit calculation request
        r'compute\s+',                   # Explicit computation request
        r'solve\s+\d+',                  # Simple solve requests with numbers
        r'convert\s+\d+',                # Unit conversions
        r'factorial\s+of\s+\d+',         # Factorial calculations
        r'square\s+root\s+of\s+\d+',     # Square roots
    ]

    # Check for common question types that don't need search
    nonsearch_patterns = [
        r'^when\s+was\s+\d+',            # Simple historical questions like "when was 1999"
        r'^tell\s+me\s+a\s+joke',        # Joke requests
        r'^write\s+(a|me)\s+',           # Creative writing prompts
        r'^what\s+is\s+\d+\s*[\+\-\*\/]\s*\d+', # "What is 3*3" type questions
    ]

    # If any pattern matches, it's likely a simple query
    for pattern in calc_patterns + nonsearch_patterns:
        if re.search(pattern, query.lower()):
            return True

    return False

# Add Google Custom Search API Key and Search Engine ID
GOOGLE_SEARCH_API_KEY = "AIzaSyAEf8rdzlL1ssMrEsspBm1tHtGhqKriWzQ"
GOOGLE_SEARCH_CX = "c610e96c90d3a4eae"

# Initialize Vertex AI
try:
    # Vertex AI uses application default credentials or explicit credentials
    # No API key needed as it uses Google Cloud authentication
    import vertexai
    vertexai.init(project="your-project-id", location="us-central1")

    # Create a client variable for compatibility with existing code
    client = None  # Not directly used in Vertex AI, but kept for compatibility
except Exception as e:
    print(f"{Fore.RED}Fatal Error: Could not initialize Vertex AI.{ColoramaStyle.RESET_ALL}")
    print(f"{Fore.RED}Error details: {e}{ColoramaStyle.RESET_ALL}")
    print(f"{Fore.YELLOW}Please ensure you have proper authentication set up and the 'vertexai' package is installed correctly.{ColoramaStyle.RESET_ALL}")
    exit(1)  # Exit if initialization fails

# Model names for Vertex AI
DEFAULT_MODEL_NAME = "gemini-2.0-flash"
GROUNDING_MODEL_NAME = "gemini-2.0-flash"

# Define the folder structure
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
instruction_manager = InstructionManager(BASE_DIR)
LOG_FOLDER = BASE_DIR / "logs"
PROMPT_FOLDER = BASE_DIR / "prompts"
SEARCH_FOLDER = BASE_DIR / "searches"

# Create necessary folders
LOG_FOLDER.mkdir(exist_ok=True)
PROMPT_FOLDER.mkdir(exist_ok=True)
SEARCH_FOLDER.mkdir(exist_ok=True)

# Define a custom style for the prompt input
prompt_style = PromptStyle.from_dict({
    'prompt': 'ansicyan bold',
})

# Define colors for console output
COLOR_USER = "\033[94m"  # Blue for user input
COLOR_CYAN = "\033[96m"  # Cyan for system messages
COLOR_WHITE = "\033[97m"  # White for AI responses
COLOR_RESET = "\033[0m"  # Reset color

# Initialize global variables
chat = None  # Will hold the chat session
model = None  # Will hold the model
conversation_history = []
log_filename = None
current_search_method = SearchMethod.NONE  # Default to no search
current_chat_model_name = DEFAULT_MODEL_NAME
last_search_results = ""  # Store the most recent search results for context

# --- Helper function to highlight code blocks in text output ---
def highlight_text(text):
    """
    Highlight code blocks in text output.
    This is a simple implementation that looks for markdown-style code blocks.
    """
    lines = text.split('\n')
    in_code_block = False
    result = []

    for line in lines:
        # Check for code block markers
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            result.append(COLOR_CYAN + line + COLOR_RESET)
        elif in_code_block:
            # Inside a code block, highlight with cyan
            result.append(COLOR_CYAN + line + COLOR_RESET)
        else:
            # Regular text
            result.append(line)

    return '\n'.join(result)

# --- Log file management functions ---
def get_log_filename(prefix=""):
    """Generate a timestamped log filename with optional prefix."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if prefix:
        # Clean the prefix to make it filename-safe
        prefix = re.sub(r'[^\w\s-]', '', prefix).strip().replace(' ', '_')
        return os.path.join(LOG_FOLDER, f"{prefix}_{timestamp}.log")
    return os.path.join(LOG_FOLDER, f"conversation_{timestamp}.log")

def save_to_file(text):
    """Append text to the current log file."""
    global log_filename
    if log_filename:
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(text + "\n")

def get_latest_log_filename():
    """Get the most recently created log file."""
    log_files = list(LOG_FOLDER.glob("*.log"))
    if not log_files:
        return None
    return str(max(log_files, key=os.path.getctime))

def load_conversation_history(file_path):
    """Load conversation history from a log file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Process the lines to reconstruct the conversation
        processed_history = process_loaded_history(lines)

        # Update the database to mark this log as accessed
        try:
            conn = sqlite3.connect(BASE_DIR / "logs.db")
            cursor = conn.cursor()

            # Extract just the filename from the path
            filename = os.path.basename(file_path)

            # Update the last_accessed timestamp
            cursor.execute('''
            UPDATE log_descriptions 
            SET last_accessed = ? 
            WHERE filename = ?
            ''', (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not update log access time in database: {e}")

        return processed_history
    except Exception as e:
        print(f"Error loading conversation history: {e}")
        return []

def get_real_time_data():
    """Get real-time data like current date and time."""
    now = datetime.datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

def setup_database():
    """Set up the SQLite database for log management if it doesn't exist."""
    try:
        db_path = BASE_DIR / "logs.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create table for log descriptions if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_descriptions (
            filename TEXT PRIMARY KEY,
            description TEXT,
            tags TEXT,
            created_date TEXT,
            last_accessed TEXT,
            ai_generated_description TEXT
        )
        ''')

        # Create index on filename
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON log_descriptions(filename)')

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting up database: {e}")
        return False

# --- Multiline input function ---
def get_multiline_input(prompt_message="Enter text (type Ctrl+D or ESC followed by ENTER to finish):", default_text=None):
    """Get multiline input from the user with proper handling of keyboard shortcuts."""
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys

    # Create key bindings
    kb = KeyBindings()

    # Flag to track if we should exit
    exit_flag = [False]

    # Handle Ctrl+D to submit
    @kb.add('c-d')
    def _(event):
        exit_flag[0] = True
        event.app.exit()

    # Handle Escape followed by Enter to submit
    @kb.add(Keys.Escape)
    def _(event):
        # Set a flag that escape was pressed
        event.app.escape_pressed = True

    # Create a session with the key bindings
    session = PromptSession(key_bindings=kb)

    # Get the input
    lines = []
    first_line = True
    escape_pressed = False

    while not exit_flag[0]:
        try:
            if first_line:
                # Use the provided prompt for the first line
                line = session.prompt(HTML(f"<ansicyan>{prompt_message}</ansicyan> "), 
                                     style=prompt_style,
                                     default=default_text or "")
                first_line = False
            else:
                # Use a continuation prompt for subsequent lines
                line = session.prompt(HTML("<ansicyan>... </ansicyan>"), style=prompt_style)

            # Check if Escape was pressed before this line
            if hasattr(session.app, 'escape_pressed') and session.app.escape_pressed:
                escape_pressed = True
                # If this line is empty and Escape was pressed, exit
                if not line.strip():
                    break
                session.app.escape_pressed = False

            lines.append(line)
        except EOFError:
            # Ctrl+D was pressed
            break
        except KeyboardInterrupt:
            # Ctrl+C was pressed
            print("\nInput cancelled.")
            return None

    # Join the lines with newlines
    return "\n".join(lines)

def process_loaded_history(history_log_lines):
    """Process loaded history lines into a clean conversation history."""
    processed_history = []
    current_entry = ""
    current_role = None

    for line in history_log_lines:
        line = line.rstrip()

        # Skip empty lines at the beginning
        if not processed_history and not line:
            continue

        # Detect role changes
        if line.startswith("You: "):
            # If we were building a previous entry, save it
            if current_role and current_entry:
                processed_history.append(current_entry)

            # Start a new user entry
            current_role = "user"
            current_entry = line
        elif line.startswith("Note: "):
            # If we were building a previous entry, save it
            if current_role and current_entry:
                processed_history.append(current_entry)

            # Add the note as its own entry
            processed_history.append(line)
            current_role = None
            current_entry = ""
        elif line.startswith("---") or not line:
            # Separator lines or empty lines - ignore but preserve role
            continue
        else:
            # If no role is set yet and we have content, this must be the AI's first response
            if not current_role and line:
                # If we have a non-empty line and no current role, this is the start of an AI response
                current_role = "ai"
                current_entry = line
            # If we're in the middle of an AI response, append to it
            elif current_role == "ai":
                current_entry += "\n" + line
            # If we're in the middle of a user message (unlikely but possible for multiline), append to it
            elif current_role == "user":
                current_entry += "\n" + line

    # Add the last entry if there is one
    if current_role and current_entry:
        processed_history.append(current_entry)

    return processed_history

def print_wrapped_text(text):
    """Print text with proper wrapping for the terminal width."""
    wrapped_lines = []
    for line in text.split('\n'):
        if line.strip():
            # Wrap the line to fit the terminal width
            wrapped = textwrap.fill(line, width=terminal_width - 2)
            wrapped_lines.append(wrapped)
        else:
            # Preserve empty lines
            wrapped_lines.append('')

    return '\n'.join(wrapped_lines)

# --- Prompt template functions ---
def save_prompt_template(name, prompt_text, description=""):
    """Save a prompt template with the given name and text."""
    try:
        # Create the prompts directory if it doesn't exist
        os.makedirs(PROMPT_FOLDER, exist_ok=True)

        # Generate a description if none was provided
        if not description:
            description = generate_ai_prompt_description(prompt_text)

        # Save the prompt to a file
        file_path = os.path.join(PROMPT_FOLDER, f"{name}.json")
        prompt_data = {
            "text": prompt_text,
            "description": description,
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(prompt_data, f, indent=2)

        print(f"{COLOR_CYAN}Prompt template '{name}' saved successfully.{COLOR_RESET}")
        return True
    except Exception as e:
        print(f"Error saving prompt template: {e}")
        return False

def list_prompts():
    """List all saved prompt templates."""
    try:
        # Create the prompts directory if it doesn't exist
        os.makedirs(PROMPT_FOLDER, exist_ok=True)

        # Get all JSON files in the prompts directory
        prompt_files = [f for f in os.listdir(PROMPT_FOLDER) if f.endswith('.json')]

        if not prompt_files:
            print(f"{COLOR_CYAN}No prompt templates found.{COLOR_RESET}")
            return

        # Create a table to display the prompts
        table = Table(title="Saved Prompt Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Created", style="dim")

        for file in prompt_files:
            try:
                with open(os.path.join(PROMPT_FOLDER, file), "r", encoding="utf-8") as f:
                    data = json.load(f)

                name = file[:-5]  # Remove .json extension
                description = data.get("description", "No description")
                created = data.get("created", "Unknown")

                table.add_row(name, description, created)
            except Exception as e:
                table.add_row(file[:-5], f"Error: {e}", "Unknown")

        console.print(table)
    except Exception as e:
        print(f"Error listing prompt templates: {e}")

def load_prompt_template(name):
    """Load a prompt template by name."""
    try:
        file_path = os.path.join(PROMPT_FOLDER, f"{name}.json")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("text", "")
    except Exception as e:
        print(f"Error loading prompt template: {e}")
        return None

# --- Web search function ---
def search_web(query, num_results=5, timeout=10):
    """
    Search the web using Google Custom Search API.
    Returns a list of search results.
    """
    try:
        # Construct the API URL
        url = "https://www.googleapis.com/customsearch/v1"

        # Set up the parameters
        params = {
            "key": GOOGLE_SEARCH_API_KEY,
            "cx": GOOGLE_SEARCH_CX,
            "q": query,
            "num": num_results
        }

        # Make the request with timeout
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the response
        data = response.json()

        # Extract the search results
        results = []
        if "items" in data:
            for item in data["items"]:
                result = {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "displayLink": item.get("displayLink", "")
                }
                results.append(result)

        return results
    except Exception as e:
        print(f"\n{Fore.RED}Search Error:{ColoramaStyle.RESET_ALL} {str(e)}")
        return []

def format_search_results(results):
    """Format search results for display and for sending to Vertex AI."""
    # Format for display (with colors and formatting)
    display_text = f"{COLOR_CYAN}Search Results:{COLOR_RESET}\n\n"
    for i, result in enumerate(results, 1):
        display_text += f"{COLOR_CYAN}{i}. {result['title']}{COLOR_RESET}\n"
        display_text += f"   {COLOR_USER}URL:{COLOR_RESET} {result['link']}\n"
        display_text += f"   {COLOR_USER}Snippet:{COLOR_RESET} {result['snippet']}\n\n"

    # Format for Vertex AI (plain text)
    vertex_text = "Web search results:\n\n"
    for i, result in enumerate(results, 1):
        vertex_text += f"{i}. Title: {result['title']}\n"
        vertex_text += f"   URL: {result['link']}\n"
        vertex_text += f"   Snippet: {result['snippet']}\n\n"

    return display_text, vertex_text

def generate_ai_description(log_content, first_prompt, active_instruction_name=None):
    """Generate a description for a log file using Vertex AI."""
    try:
        # Create a model for generating descriptions
        description_model = GenerativeModel(model_name="gemini-1.5-flash")

        # Prepare a prompt for the AI
        prompt = f"""Generate a concise (10-15 words) description for this conversation log.

First user query: "{first_prompt}"

{f'System instruction: {active_instruction_name}' if active_instruction_name else ''}

Focus on capturing the main topic or purpose of the conversation.
Respond with just the description text, no quotes or additional commentary."""

        # Generate the description
        response = description_model.generate_content(prompt)
        description = response.text.strip()

        # Limit the length
        if len(description) > 100:
            description = description[:97] + "..."

        return description
    except Exception as e:
        print(f"Error generating AI description: {e}")
        # Fallback to a simple description based on the first prompt
        if first_prompt:
            return f"Conversation about: {first_prompt[:50]}..."
        return "Conversation log"

def generate_ai_prompt_description(prompt_text):
    """Generate a description for a prompt template using Vertex AI."""
    try:
        # Create a model for generating descriptions
        description_model = GenerativeModel(model_name="gemini-1.5-flash")

        # Prepare a prompt for the AI
        ai_prompt = f"""Create a brief (5-10 words) description for this prompt template:

{prompt_text[:500]}  # Limit to first 500 chars for brevity

The description should capture the essence of what this prompt is designed to do.
Respond with just the description text, no quotes or additional commentary."""

        # Generate the description
        response = description_model.generate_content(ai_prompt)
        description = response.text.strip()

        # Limit the length
        if len(description) > 50:
            description = description[:47] + "..."

        return description
    except Exception as e:
        print(f"Error generating prompt description: {e}")
        return "Custom prompt template"

def print_conversation_history():
    """Print the entire loaded conversation history."""
    global conversation_history

    if not conversation_history:
        print(f"{COLOR_CYAN}Vertex AI:{COLOR_RESET} {COLOR_WHITE}No conversation history loaded.{COLOR_RESET}")
        return

    terminal_width = shutil.get_terminal_size().columns
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(COLOR_CYAN + "Conversation History" + COLOR_RESET)
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    for line in conversation_history:
        if line.startswith("You: "):
            print(f"{COLOR_USER}{line}{COLOR_RESET}")
        elif line.startswith("Note:"):
            print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
        else:
            try:
                console.print(Markdown(line))
            except Exception:
                wrapped_text = print_wrapped_text(line)
                formatted_text = highlight_text(wrapped_text)
                print(formatted_text)

    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

def switch_search_method(new_method):
    """Switch the search method used by the application."""
    global current_search_method, chat, model

    # Validate the input
    try:
        if isinstance(new_method, str):
            # Convert string to enum
            new_method = SearchMethod[new_method.upper()]
        elif isinstance(new_method, int):
            # Convert int to enum
            new_method = SearchMethod(new_method)
        elif not isinstance(new_method, SearchMethod):
            raise ValueError(f"Invalid search method: {new_method}")
    except (KeyError, ValueError) as e:
        print(f"{COLOR_CYAN}Error: {e}. Valid methods are: {', '.join([m.name for m in SearchMethod])}{COLOR_RESET}")
        return False

    # If switching to or from grounding, we need to reset the chat
    if (current_search_method == SearchMethod.GEMINI_GROUNDING and new_method != SearchMethod.GEMINI_GROUNDING) or \
       (current_search_method != SearchMethod.GEMINI_GROUNDING and new_method == SearchMethod.GEMINI_GROUNDING):
        # Reset the chat session
        chat = None

        # If switching to grounding, use the grounding model
        if new_method == SearchMethod.GEMINI_GROUNDING:
            model = GenerativeModel(model_name=GROUNDING_MODEL_NAME)
        else:
            model = GenerativeModel(model_name=DEFAULT_MODEL_NAME)

    # Update the search method
    current_search_method = new_method

    # Print confirmation
    method_descriptions = {
        SearchMethod.NONE: "No search (AI will use its training data only)",
        SearchMethod.CUSTOM: "Custom search (explicit 'search' command or force_search flag)",
        SearchMethod.GEMINI_GROUNDING: "Vertex AI native grounding (using Google Search Retrieval)"
    }

    print(f"{COLOR_CYAN}Search method set to: {current_search_method.name} - {method_descriptions[current_search_method]}{COLOR_RESET}")
    return True

def show_command_help(command):
    """Show help for a specific command."""
    help_text = {
        "reset": "Reset the conversation and start a new session. Usage: reset [session_name]",
        "search": "Perform a web search and use results in the AI response. Usage: search <query>",
        "history": "Show the conversation history. Usage: history",
        "save": "Save the current prompt as a template. Usage: save <template_name> [description]",
        "load": "Load a prompt template. Usage: load <template_name>",
        "list": "List saved prompt templates. Usage: list",
        "method": "Change the search method. Usage: method <none|custom|grounding>",
        "help": "Show help information. Usage: help [command]",
        "exit": "Exit the application. Usage: exit",
        "quit": "Exit the application. Usage: quit",
        "instruction": "Apply a system instruction. Usage: instruction <name>",
        "instructions": "List available system instructions. Usage: instructions",
        "clear_instruction": "Clear the current system instruction. Usage: clear_instruction",
        "save_instruction": "Save a new system instruction. Usage: save_instruction <name> [description]",
        "logs": "List conversation logs. Usage: logs [filter]",
        "load_log": "Load a conversation log. Usage: load_log <log_name>",
        "describe": "Update the description of the current log. Usage: describe",
        "quick": "Quick ask without saving to history. Usage: quick <query>",
        "lookup": "Quick lookup with web search. Usage: lookup <query>",
        "context": "Show the current context window. Usage: context",
        "view": "View a specific log file. Usage: view <log_name>",
    }

    if command in help_text:
        print(f"{COLOR_CYAN}{command}:{COLOR_RESET} {help_text[command]}")
    else:
        print(f"{COLOR_CYAN}Unknown command: {command}{COLOR_RESET}")
        print(f"{COLOR_CYAN}Type 'help' to see all available commands.{COLOR_RESET}")

def display_help():
    """Display help information for the application."""
    terminal_width = shutil.get_terminal_size().columns

    # Create a table for the commands
    table = Table(title="Vertex AI CLI Commands", width=terminal_width)
    table.add_column("Command", style="cyan", width=20)
    table.add_column("Description", style="white")
    table.add_column("Example", style="green", width=30)

    # Add rows for each command
    table.add_row(
        "reset [name]",
        "Reset conversation and start a new session with optional name",
        "reset meeting_with_john"
    )
    table.add_row(
        "search <query>",
        "Perform a web search and use results in the AI response",
        "search latest news about AI"
    )
    table.add_row(
        "history",
        "Show the conversation history",
        "history"
    )
    table.add_row(
        "save <name> [desc]",
        "Save the current prompt as a template with optional description",
        "save meeting_summary"
    )
    table.add_row(
        "load <name>",
        "Load a prompt template",
        "load meeting_summary"
    )
    table.add_row(
        "list",
        "List saved prompt templates",
        "list"
    )
    table.add_row(
        "method <type>",
        "Change search method (none, custom, grounding)",
        "method grounding"
    )
    table.add_row(
        "instruction <name>",
        "Apply a system instruction",
        "instruction helpful_assistant"
    )
    table.add_row(
        "instructions",
        "List available system instructions",
        "instructions"
    )
    table.add_row(
        "clear_instruction",
        "Clear the current system instruction",
        "clear_instruction"
    )
    table.add_row(
        "save_instruction <name>",
        "Save a new system instruction",
        "save_instruction helpful_assistant"
    )
    table.add_row(
        "logs [filter]",
        "List conversation logs with optional filter",
        "logs meeting"
    )
    table.add_row(
        "load_log <name>",
        "Load a conversation log",
        "load_log meeting_20230615"
    )
    table.add_row(
        "describe",
        "Update the description of the current log",
        "describe"
    )
    table.add_row(
        "quick <query>",
        "Quick ask without saving to history",
        "quick what's 2+2?"
    )
    table.add_row(
        "lookup <query>",
        "Quick lookup with web search",
        "lookup latest news"
    )
    table.add_row(
        "context",
        "Show the current context window",
        "context"
    )
    table.add_row(
        "view <log>",
        "View a specific log file",
        "view meeting_20230615"
    )
    table.add_row(
        "help [command]",
        "Show help information for all commands or a specific command",
        "help search"
    )
    table.add_row(
        "exit, quit",
        "Exit the application",
        "exit"
    )

    # Print the table
    console.print(table)

    # Print additional information
    print(f"\n{COLOR_CYAN}Search Methods:{COLOR_RESET}")
    print(f"  {COLOR_CYAN}none:{COLOR_RESET} No search (AI will use its training data only)")
    print(f"  {COLOR_CYAN}custom:{COLOR_RESET} Custom search (explicit 'search' command or force_search flag)")
    print(f"  {COLOR_CYAN}grounding:{COLOR_RESET} Vertex AI native grounding (using Google Search Retrieval)")

    print(f"\n{COLOR_CYAN}Current Settings:{COLOR_RESET}")
    print(f"  {COLOR_CYAN}Search Method:{COLOR_RESET} {current_search_method.name}")
    print(f"  {COLOR_CYAN}Model:{COLOR_RESET} {current_chat_model_name}")

    active_instruction, active_name = instruction_manager.get_active_instruction()
    if active_instruction:
        print(f"  {COLOR_CYAN}Active Instruction:{COLOR_RESET} {active_name}")
    else:
        print(f"  {COLOR_CYAN}Active Instruction:{COLOR_RESET} None")

    if log_filename:
        print(f"  {COLOR_CYAN}Log File:{COLOR_RESET} {os.path.basename(log_filename)}")
    else:
        print(f"  {COLOR_CYAN}Log File:{COLOR_RESET} None")

def edit_log_description():
    """Update the description of the current log file."""
    global log_filename

    if not log_filename:
        print(f"{COLOR_CYAN}No active log file.{COLOR_RESET}")
        return

    print(f"{COLOR_CYAN}Current log file: {log_filename}{COLOR_RESET}")

    # Get the current description from the database
    current_description = None
    try:
        conn = sqlite3.connect(BASE_DIR / "logs.db")
        cursor = conn.cursor()

        # Extract just the filename from the path
        filename = os.path.basename(log_filename)

        cursor.execute("SELECT description FROM log_descriptions WHERE filename = ?", (filename,))
        result = cursor.fetchone()

        if result:
            current_description = result[0]

        conn.close()
    except Exception as e:
        print(f"Warning: Could not get current description from database: {e}")

    # Show the current description
    if current_description:
        print(f"{COLOR_CYAN}Current description: {current_description}{COLOR_RESET}")

    # Get a new description from the user
    new_description = get_multiline_input("Enter a new description (or press Ctrl+D with empty input to cancel):")

    if not new_description or new_description.strip() == "":
        print(f"{COLOR_CYAN}Description update cancelled.{COLOR_RESET}")
        return

    # Update the description in the database
    try:
        conn = sqlite3.connect(BASE_DIR / "logs.db")
        cursor = conn.cursor()

        # Extract just the filename from the path
        filename = os.path.basename(log_filename)

        cursor.execute('''
        UPDATE log_descriptions 
        SET description = ? 
        WHERE filename = ?
        ''', (new_description, filename))

        # If no row was updated, we need to insert a new row
        if cursor.rowcount == 0:
            created_date = datetime.datetime.fromtimestamp(
                os.path.getctime(log_filename)).strftime("%Y-%m-%d %H:%M:%S")
            last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
            INSERT INTO log_descriptions
            (filename, description, created_date, last_accessed)
            VALUES (?, ?, ?, ?)
            ''', (filename, new_description, created_date, last_accessed))

        conn.commit()
        conn.close()

        print(f"{COLOR_CYAN}Description updated successfully.{COLOR_RESET}")
    except Exception as e:
        print(f"Error updating description: {e}")

def list_logs(filter_text=None):
    """List all conversation logs with optional filtering."""
    try:
        # Ensure the database exists
        setup_database()

        # Connect to the database
        conn = sqlite3.connect(BASE_DIR / "logs.db")
        cursor = conn.cursor()

        # Get all log files
        log_files = list(LOG_FOLDER.glob("*.log"))

        # Create a table to display the logs
        table = Table(title="Conversation Logs")
        table.add_column("Filename", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Created", style="dim")
        table.add_column("Last Accessed", style="dim")
        table.add_column("Tags", style="yellow")

        # Get log information from the database
        log_info = {}
        cursor.execute("SELECT filename, description, created_date, last_accessed, tags FROM log_descriptions")
        for row in cursor.fetchall():
            log_info[row[0]] = {
                "description": row[1] or "No description",
                "created_date": row[2] or "Unknown",
                "last_accessed": row[3] or "Never",
                "tags": row[4] or ""
            }

        # Filter logs if a filter is provided
        if filter_text:
            filter_text = filter_text.lower()
            filtered_logs = []
            for log_file in log_files:
                filename = os.path.basename(log_file)
                info = log_info.get(filename, {
                    "description": "No description",
                    "created_date": "Unknown",
                    "last_accessed": "Never",
                    "tags": ""
                })

                # Check if the filter matches any of the log information
                if (filter_text in filename.lower() or
                    filter_text in info["description"].lower() or
                    filter_text in info["tags"].lower()):
                    filtered_logs.append((log_file, info))

            logs_to_display = filtered_logs
        else:
            logs_to_display = [(log_file, log_info.get(os.path.basename(log_file), {
                "description": "No description",
                "created_date": "Unknown",
                "last_accessed": "Never",
                "tags": ""
            })) for log_file in log_files]

        # Sort logs by creation date (newest first)
        logs_to_display.sort(key=lambda x: os.path.getctime(x[0]), reverse=True)

        # Add rows to the table
        for log_file, info in logs_to_display:
            filename = os.path.basename(log_file)
            table.add_row(
                filename,
                info["description"],
                info["created_date"],
                info["last_accessed"],
                info["tags"]
            )

        # Print the table
        console.print(table)

        # Print the total number of logs
        print(f"\n{COLOR_CYAN}Total logs: {len(logs_to_display)}{COLOR_RESET}")

        conn.close()
    except Exception as e:
        print(f"Error listing logs: {e}")

def quick_lookup(query):
    """Perform a quick web search lookup without saving to conversation history."""
    try:
        # Start timing the request
        start_time = time.time()

        # Perform the search
        print(f"{COLOR_CYAN}Performing quick lookup for: {query}{COLOR_RESET}")
        search_results = search_web(query, num_results=5, timeout=10)

        if not search_results:
            print(f"{COLOR_CYAN}No search results found.{COLOR_RESET}")
            return

        # Format the search results
        display_text, vertex_text = format_search_results(search_results)

        # Create a model for the lookup
        lookup_model = GenerativeModel(model_name="gemini-1.5-flash")

        # Prepare the prompt
        prompt = f"""I need information about: {query}

{vertex_text}

Based on these search results from the web, please provide a comprehensive and factual answer about '{query}'.
Incorporate information from the search results and cite sources where appropriate.
"""

        # Generate the response
        with console.status("[cyan]Generating answer from search results...", spinner="dots"):
            response = lookup_model.generate_content(prompt)
            response_text = response.text

        # Calculate the total time
        total_time = time.time() - start_time

        # Print the search results
        print(display_text)

        # Print the response
        terminal_width = shutil.get_terminal_size().columns
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(COLOR_CYAN + "Quick Lookup Response" + COLOR_RESET)
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

        try:
            console.print(Markdown(response_text, code_theme="monokai"))
        except Exception:
            wrapped_text = print_wrapped_text(response_text)
            formatted_text = highlight_text(wrapped_text)
            print(formatted_text)

        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(f"{COLOR_CYAN}Total lookup time: {total_time:.2f}s{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    except Exception as e:
        print(f"Error performing quick lookup: {e}")

def quick_ask(query):
    """Ask a quick question without saving to conversation history."""
    try:
        # Start timing the request
        start_time = time.time()

        # Create a model for the quick ask
        quick_model = GenerativeModel(model_name="gemini-1.5-flash")

        # Generate the response
        with console.status("[cyan]Thinking...", spinner="dots"):
            response = quick_model.generate_content(query)
            response_text = response.text

        # Calculate the total time
        total_time = time.time() - start_time

        # Print the response
        terminal_width = shutil.get_terminal_size().columns
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(COLOR_CYAN + "Quick Response" + COLOR_RESET)
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

        try:
            console.print(Markdown(response_text, code_theme="monokai"))
        except Exception:
            wrapped_text = print_wrapped_text(response_text)
            formatted_text = highlight_text(wrapped_text)
            print(formatted_text)

        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(f"{COLOR_CYAN}Response time: {total_time:.2f}s{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    except Exception as e:
        print(f"Error performing quick ask: {e}")

def reset_log_database():
    """Reset the log database by creating a new empty database."""
    try:
        # Backup the existing database if it exists
        db_path = BASE_DIR / "logs.db"
        if db_path.exists():
            backup_path = BASE_DIR / f"logs_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy(db_path, backup_path)
            print(f"{COLOR_CYAN}Backed up existing database to {backup_path}{COLOR_RESET}")

            # Delete the existing database
            os.remove(db_path)
            print(f"{COLOR_CYAN}Deleted existing database{COLOR_RESET}")

        # Create a new database
        setup_database()
        print(f"{COLOR_CYAN}Created new empty database{COLOR_RESET}")

        return True
    except Exception as e:
        print(f"Error resetting database: {e}")
        return False

def cleanup_client():
    """Clean up resources before exiting."""
    # Nothing specific to clean up for Vertex AI
    pass

def save_conversation_on_reset():
    """Save the current conversation before resetting."""
    global conversation_history, log_filename

    if not conversation_history:
        return None  # Nothing to save

    if not log_filename:
        # Generate a new log filename
        log_filename = get_log_filename("auto_save")

    # Check if the log file already exists and has content
    try:
        if os.path.exists(log_filename) and os.path.getsize(log_filename) > 0:
            # File exists and has content, so we don't need to save again
            return log_filename
    except Exception:
        pass  # Ignore errors and proceed with saving

    # Save the conversation history to the log file
    try:
        with open(log_filename, "w", encoding="utf-8") as f:
            for line in conversation_history:
                f.write(line + "\n")

        # Generate a description for the log
        try:
            description = generate_description_for_log(log_filename)

            # Save the description to the database
            conn = sqlite3.connect(BASE_DIR / "logs.db")
            cursor = conn.cursor()

            # Extract just the filename from the path
            filename = os.path.basename(log_filename)

            # Check if the log already has a description
            cursor.execute("SELECT description FROM log_descriptions WHERE filename = ?", (filename,))
            result = cursor.fetchone()

            if result and result[0]:
                # Log already has a description, so don't overwrite it
                pass
            else:
                # Save the generated description
                created_date = datetime.datetime.fromtimestamp(
                    os.path.getctime(log_filename)).strftime("%Y-%m-%d %H:%M:%S")
                last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute('''
                INSERT OR REPLACE INTO log_descriptions
                (filename, description, created_date, last_accessed, ai_generated_description)
                VALUES (?, ?, ?, ?, ?)
                ''', (filename, description, created_date, last_accessed, "Yes"))

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not generate or save description: {e}")

        return log_filename
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return None

def show_context_window():
    """Show the current context window (conversation history)."""
    global conversation_history, chat, model

    if not conversation_history:
        print(f"{COLOR_CYAN}No conversation history.{COLOR_RESET}")
        return

    # Print the conversation history
    terminal_width = shutil.get_terminal_size().columns
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(COLOR_CYAN + "Current Context Window" + COLOR_RESET)
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    # Count tokens in the conversation history
    total_tokens = 0
    for line in conversation_history:
        # Very rough token estimation (words + punctuation)
        tokens = len(re.findall(r'\w+|[^\w\s]', line))
        total_tokens += tokens

    # Print the conversation history with token counts
    for i, line in enumerate(conversation_history):
        tokens = len(re.findall(r'\w+|[^\w\s]', line))
        if line.startswith("You: "):
            print(f"{COLOR_USER}{line} {COLOR_CYAN}[~{tokens} tokens]{COLOR_RESET}")
        elif line.startswith("Note:"):
            print(f"{COLOR_CYAN}{line} [~{tokens} tokens]{COLOR_RESET}")
        else:
            try:
                print(f"{COLOR_CYAN}AI: {COLOR_RESET}")
                console.print(Markdown(line))
                print(f"{COLOR_CYAN}[~{tokens} tokens]{COLOR_RESET}")
            except Exception:
                wrapped_text = print_wrapped_text(line)
                formatted_text = highlight_text(wrapped_text)
                print(formatted_text)
                print(f"{COLOR_CYAN}[~{tokens} tokens]{COLOR_RESET}")

    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(f"{COLOR_CYAN}Total tokens in context: ~{total_tokens}{COLOR_RESET}")
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

def view_log(target):
    """View a specific log file."""
    try:
        # Find the log file
        log_file = None

        # Check if the target is a full path
        if os.path.exists(target) and target.endswith(".log"):
            log_file = target
        else:
            # Check if the target is a filename in the logs folder
            potential_file = os.path.join(LOG_FOLDER, target)
            if os.path.exists(potential_file):
                log_file = potential_file
            else:
                # Check if the target is a partial filename
                log_files = list(LOG_FOLDER.glob("*.log"))
                for file in log_files:
                    if target in os.path.basename(file):
                        log_file = str(file)
                        break

        if not log_file:
            print(f"{COLOR_CYAN}Log file not found: {target}{COLOR_RESET}")
            return

        # Get the log description from the database
        description = None
        tags = None
        try:
            conn = sqlite3.connect(BASE_DIR / "logs.db")
            cursor = conn.cursor()

            # Extract just the filename from the path
            filename = os.path.basename(log_file)

            cursor.execute("SELECT description, tags FROM log_descriptions WHERE filename = ?", (filename,))
            result = cursor.fetchone()

            if result:
                description = result[0]
                tags = result[1]

            conn.close()
        except Exception as e:
            print(f"Warning: Could not get log description from database: {e}")

        # Read the log file
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.readlines()

        # Print the log information
        terminal_width = shutil.get_terminal_size().columns
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(COLOR_CYAN + f"Log File: {os.path.basename(log_file)}" + COLOR_RESET)
        if description:
            print(COLOR_CYAN + f"Description: {description}" + COLOR_RESET)
        if tags:
            print(COLOR_CYAN + f"Tags: {tags}" + COLOR_RESET)
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

        # Process and print the log content
        current_role = None
        current_message = []

        for line in content:
            line = line.rstrip()

            if not line:
                # Empty line - print the current message if any
                if current_message:
                    if current_role == "user":
                        print(f"{COLOR_USER}{''.join(current_message)}{COLOR_RESET}")
                    elif current_role == "note":
                        print(f"{COLOR_CYAN}{''.join(current_message)}{COLOR_RESET}")
                    else:
                        try:
                            console.print(Markdown(''.join(current_message)))
                        except Exception:
                            wrapped_text = print_wrapped_text(''.join(current_message))
                            formatted_text = highlight_text(wrapped_text)
                            print(formatted_text)

                    current_message = []
                    print()  # Add an empty line for readability
                continue

            if line.startswith("You: "):
                # If we were building a previous message, print it
                if current_message:
                    if current_role == "user":
                        print(f"{COLOR_USER}{''.join(current_message)}{COLOR_RESET}")
                    elif current_role == "note":
                        print(f"{COLOR_CYAN}{''.join(current_message)}{COLOR_RESET}")
                    else:
                        try:
                            console.print(Markdown(''.join(current_message)))
                        except Exception:
                            wrapped_text = print_wrapped_text(''.join(current_message))
                            formatted_text = highlight_text(wrapped_text)
                            print(formatted_text)

                    print()  # Add an empty line for readability

                # Start a new user message
                current_role = "user"
                current_message = [line]
            elif line.startswith("Note: "):
                # If we were building a previous message, print it
                if current_message:
                    if current_role == "user":
                        print(f"{COLOR_USER}{''.join(current_message)}{COLOR_RESET}")
                    elif current_role == "note":
                        print(f"{COLOR_CYAN}{''.join(current_message)}{COLOR_RESET}")
                    else:
                        try:
                            console.print(Markdown(''.join(current_message)))
                        except Exception:
                            wrapped_text = print_wrapped_text(''.join(current_message))
                            formatted_text = highlight_text(wrapped_text)
                            print(formatted_text)

                    print()  # Add an empty line for readability

                # Start a new note
                current_role = "note"
                current_message = [line]
            else:
                # If no role is set yet, this must be the AI's first response
                if not current_role:
                    current_role = "ai"
                    current_message = [line]
                else:
                    # Append to the current message
                    current_message.append("\n" + line)

        # Print the last message if any
        if current_message:
            if current_role == "user":
                print(f"{COLOR_USER}{''.join(current_message)}{COLOR_RESET}")
            elif current_role == "note":
                print(f"{COLOR_CYAN}{''.join(current_message)}{COLOR_RESET}")
            else:
                try:
                    console.print(Markdown(''.join(current_message)))
                except Exception:
                    wrapped_text = print_wrapped_text(''.join(current_message))
                    formatted_text = highlight_text(wrapped_text)
                    print(formatted_text)

        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(f"{COLOR_CYAN}End of log file{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    except Exception as e:
        print(f"Error viewing log: {e}")

def main():
    """Main function to run the Vertex AI CLI."""
    global chat, model, conversation_history, log_filename, current_search_method, current_chat_model_name

    # Set up the database
    setup_database()

    # Register cleanup function to run on exit
    atexit.register(cleanup_client)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Vertex AI CLI")
    parser.add_argument("--session", "-s", help="Session name for the conversation log")
    parser.add_argument("--method", "-m", choices=["none", "custom", "grounding"], 
                        default="none", help="Search method to use")
    parser.add_argument("--instruction", "-i", help="System instruction to apply")
    parser.add_argument("--model", help="Model name to use")
    parser.add_argument("--load", "-l", help="Load a conversation log")
    args = parser.parse_args()

    # Set the search method
    if args.method:
        switch_search_method(args.method)

    # Set the model name
    if args.model:
        current_chat_model_name = args.model
        print(f"{COLOR_CYAN}Model set to: {current_chat_model_name}{COLOR_RESET}")

    # Load a conversation log if specified
    if args.load:
        log_path = None
        if os.path.exists(args.load):
            log_path = args.load
        else:
            potential_path = os.path.join(LOG_FOLDER, args.load)
            if os.path.exists(potential_path):
                log_path = potential_path
            else:
                # Try to find a log file with a matching name
                log_files = list(LOG_FOLDER.glob("*.log"))
                for log_file in log_files:
                    if args.load in os.path.basename(log_file):
                        log_path = str(log_file)
                        break

        if log_path:
            conversation_history = load_conversation_history(log_path)
            log_filename = log_path
            print(f"{COLOR_CYAN}Loaded conversation from: {log_path}{COLOR_RESET}")

            # Initialize the chat with the loaded history
            model = GenerativeModel(model_name=current_chat_model_name)

            # Convert conversation history to Vertex AI format
            vertex_history = []
            user_message = None
            ai_response = None

            for line in conversation_history:
                if line.startswith("You: "):
                    if user_message is not None and ai_response is not None:
                        vertex_history.append({"role": "user", "content": user_message})
                        vertex_history.append({"role": "assistant", "content": ai_response})

                    user_message = line[4:].strip()
                    ai_response = None
                elif line.startswith("Note:"):
                    # Skip notes
                    continue
                else:
                    ai_response = line

            # Add the last turn if it exists
            if user_message is not None and ai_response is not None:
                vertex_history.append({"role": "user", "content": user_message})
                vertex_history.append({"role": "assistant", "content": ai_response})

            # Create a chat session with the history
            chat = model.start_chat(history=[
                Content(role="user" if i % 2 == 0 else "model", parts=[Part.from_text(msg["content"])])
                for i, msg in enumerate(vertex_history)
            ])
        else:
            print(f"{COLOR_CYAN}Log file not found: {args.load}{COLOR_RESET}")

    # Apply a system instruction if specified
    if args.instruction:
        success, message, new_chat = instruction_manager.apply_instruction(
            "", args.instruction, chat, client, current_chat_model_name, 
            conversation_history, current_search_method, log_filename
        )
        if success and new_chat:
            chat = new_chat
            print(f"{COLOR_CYAN}{message}{COLOR_RESET}")
        else:
            print(f"{COLOR_CYAN}Error applying instruction: {message}{COLOR_RESET}")

    # Create a session name if specified
    if args.session:
        log_filename = get_log_filename(args.session)
        print(f"{COLOR_CYAN}Session name set to: {args.session}{COLOR_RESET}")
        print(f"{COLOR_CYAN}Log file: {log_filename}{COLOR_RESET}")

    # Print welcome message
    terminal_width = shutil.get_terminal_size().columns
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(COLOR_CYAN + "Vertex AI CLI" + COLOR_RESET)
    print(COLOR_CYAN + "Type 'help' for a list of commands, or start chatting!" + COLOR_RESET)
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    # Main loop
    session = PromptSession()
    while True:
        try:
            # Get user input
            user_input = session.prompt(HTML("<ansicyan>You: </ansicyan>"), style=prompt_style)

            # Skip empty input
            if not user_input.strip():
                continue

            # Process commands
            if user_input.lower() in ["exit", "quit"]:
                # Save conversation before exiting
                if conversation_history:
                    saved_log = save_conversation_on_reset()
                    if saved_log:
                        print(f"{COLOR_CYAN}Conversation saved to: {saved_log}{COLOR_RESET}")

                print(f"{COLOR_CYAN}Goodbye!{COLOR_RESET}")
                break

            elif user_input.lower() == "help":
                display_help()

            elif user_input.lower().startswith("help "):
                command = user_input[5:].strip()
                show_command_help(command)

            elif user_input.lower() == "history":
                print_conversation_history()

            elif user_input.lower().startswith("reset"):
                # Save the current conversation if there is one
                if conversation_history:
                    saved_log = save_conversation_on_reset()
                    if saved_log:
                        print(f"{COLOR_CYAN}Previous conversation saved to: {saved_log}{COLOR_RESET}")

                # Reset the conversation
                conversation_history = []

                # Get the session name if provided
                session_name = ""
                if len(user_input) > 5:
                    session_name = user_input[5:].strip()

                # Create a new log file if a session name is provided
                if session_name:
                    log_filename = get_log_filename(session_name)
                    print(f"{COLOR_CYAN}New session started: {session_name}{COLOR_RESET}")
                    print(f"{COLOR_CYAN}Log file: {log_filename}{COLOR_RESET}")
                else:
                    log_filename = None
                    print(f"{COLOR_CYAN}New session started{COLOR_RESET}")

                # Create a new chat session
                model = GenerativeModel(model_name=current_chat_model_name)
                chat = model.start_chat(history=[])

            elif user_input.lower().startswith("method "):
                method_name = user_input[7:].strip()
                switch_search_method(method_name)

            elif user_input.lower() == "list":
                list_prompts()

            elif user_input.lower().startswith("save "):
                # Parse the command
                parts = user_input[5:].strip().split(" ", 1)
                name = parts[0]
                description = parts[1] if len(parts) > 1 else ""

                # Get the last user message
                last_message = None
                for line in reversed(conversation_history):
                    if line.startswith("You: "):
                        last_message = line[4:].strip()
                        break

                if last_message:
                    save_prompt_template(name, last_message, description)
                else:
                    print(f"{COLOR_CYAN}No message to save.{COLOR_RESET}")

            elif user_input.lower().startswith("load "):
                template_name = user_input[5:].strip()
                template_text = load_prompt_template(template_name)

                if template_text:
                    print(f"{COLOR_CYAN}Loaded template: {template_name}{COLOR_RESET}")
                    print(f"{COLOR_USER}You: {template_text}{COLOR_RESET}")

                    # Send the template to the AI
                    ask_gemini_with_search(template_text)
                else:
                    print(f"{COLOR_CYAN}Template not found: {template_name}{COLOR_RESET}")

            elif user_input.lower().startswith("instruction "):
                instruction_name = user_input[12:].strip()
                instruction_text, description = instruction_manager.load_instruction_profile(instruction_name)

                if instruction_text:
                    success, message, new_chat = instruction_manager.apply_instruction(
                        instruction_text, instruction_name, chat, client, current_chat_model_name, 
                        conversation_history, current_search_method, log_filename
                    )

                    if success:
                        if new_chat:
                            chat = new_chat
                        print(f"{COLOR_CYAN}{message}{COLOR_RESET}")
                    else:
                        print(f"{COLOR_CYAN}Error: {message}{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Instruction not found: {instruction_name}{COLOR_RESET}")

            elif user_input.lower() == "instructions":
                instructions = instruction_manager.list_instruction_profiles()

                if instructions:
                    # Create a table to display the instructions
                    table = Table(title="System Instructions")
                    table.add_column("Name", style="cyan")
                    table.add_column("Description", style="green")
                    table.add_column("Created", style="dim")
                    table.add_column("Last Used", style="dim")

                    for instruction in instructions:
                        table.add_row(
                            instruction["name"],
                            instruction["description"],
                            instruction["created"],
                            instruction["last_used"]
                        )

                    console.print(table)
                else:
                    print(f"{COLOR_CYAN}No instructions found.{COLOR_RESET}")

            elif user_input.lower() == "clear_instruction":
                success, message = instruction_manager.clear_instruction()

                if success:
                    # Create a new chat session without the instruction
                    model = GenerativeModel(model_name=current_chat_model_name)
                    chat = model.start_chat(history=[])

                    print(f"{COLOR_CYAN}{message}{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Error: {message}{COLOR_RESET}")

            elif user_input.lower().startswith("save_instruction "):
                # Parse the command
                parts = user_input[16:].strip().split(" ", 1)
                name = parts[0]

                # Get the instruction text from the user
                print(f"{COLOR_CYAN}Enter the system instruction (press Ctrl+D or ESC followed by ENTER to finish):{COLOR_RESET}")
                instruction_text = get_multiline_input()

                if instruction_text:
                    # Get an optional description
                    description = ""
                    if len(parts) > 1:
                        description = parts[1]

                    # Save the instruction
                    success, message = instruction_manager.save_instruction_profile(name, instruction_text, description)

                    if success:
                        print(f"{COLOR_CYAN}{message}{COLOR_RESET}")
                    else:
                        print(f"{COLOR_CYAN}Error: {message}{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Instruction creation cancelled.{COLOR_RESET}")

            elif user_input.lower().startswith("logs"):
                filter_text = None
                if len(user_input) > 4:
                    filter_text = user_input[4:].strip()

                list_logs(filter_text)

            elif user_input.lower().startswith("load_log "):
                log_name = user_input[9:].strip()

                # Find the log file
                log_path = None
                if os.path.exists(log_name):
                    log_path = log_name
                else:
                    potential_path = os.path.join(LOG_FOLDER, log_name)
                    if os.path.exists(potential_path):
                        log_path = potential_path
                    else:
                        # Try to find a log file with a matching name
                        log_files = list(LOG_FOLDER.glob("*.log"))
                        for log_file in log_files:
                            if log_name in os.path.basename(log_file):
                                log_path = str(log_file)
                                break

                if log_path:
                    # Save the current conversation if there is one
                    if conversation_history:
                        saved_log = save_conversation_on_reset()
                        if saved_log:
                            print(f"{COLOR_CYAN}Previous conversation saved to: {saved_log}{COLOR_RESET}")

                    # Load the new conversation
                    conversation_history = load_conversation_history(log_path)
                    log_filename = log_path
                    print(f"{COLOR_CYAN}Loaded conversation from: {log_path}{COLOR_RESET}")

                    # Initialize the chat with the loaded history
                    model = GenerativeModel(model_name=current_chat_model_name)

                    # Convert conversation history to Vertex AI format
                    vertex_history = []
                    user_message = None
                    ai_response = None

                    for line in conversation_history:
                        if line.startswith("You: "):
                            if user_message is not None and ai_response is not None:
                                vertex_history.append({"role": "user", "content": user_message})
                                vertex_history.append({"role": "assistant", "content": ai_response})

                            user_message = line[4:].strip()
                            ai_response = None
                        elif line.startswith("Note:"):
                            # Skip notes
                            continue
                        else:
                            ai_response = line

                    # Add the last turn if it exists
                    if user_message is not None and ai_response is not None:
                        vertex_history.append({"role": "user", "content": user_message})
                        vertex_history.append({"role": "assistant", "content": ai_response})

                    # Create a chat session with the history
                    chat = model.start_chat(history=[
                        Content(role="user" if i % 2 == 0 else "model", parts=[Part.from_text(msg["content"])])
                        for i, msg in enumerate(vertex_history)
                    ])
                else:
                    print(f"{COLOR_CYAN}Log file not found: {log_name}{COLOR_RESET}")

            elif user_input.lower() == "describe":
                edit_log_description()

            elif user_input.lower().startswith("quick "):
                query = user_input[6:].strip()
                quick_ask(query)

            elif user_input.lower().startswith("lookup "):
                query = user_input[7:].strip()
                quick_lookup(query)

            elif user_input.lower() == "context":
                show_context_window()

            elif user_input.lower().startswith("view "):
                target = user_input[5:].strip()
                view_log(target)

            elif user_input.lower().startswith("search "):
                # This is handled by ask_gemini_with_search with force_search=True
                ask_gemini_with_search(user_input, force_search=True)

            else:
                # Regular chat message
                ask_gemini_with_search(user_input)

        except KeyboardInterrupt:
            print(f"\n{COLOR_CYAN}Interrupted. Type 'exit' to quit.{COLOR_RESET}")

        except Exception as e:
            print(f"\n{Fore.RED}Error:{ColoramaStyle.RESET_ALL} {str(e)}")

def ask_gemini_with_search(user_input, session_name="", force_search=False, search_method=None):
    """Send the user's input to Vertex AI with optional web search, update conversation history, and save the session."""
    global log_filename, client, chat, model, conversation_history, current_search_method, current_chat_model_name
    global last_search_results  # Add this to access the global variable

    # Start timing the request
    start_time = time.time()

    # Use the globally set search method if none is explicitly passed
    if search_method is None:
        search_method = current_search_method

    try:
        real_time_info = get_real_time_data()

        # Update terminal width
        terminal_width = shutil.get_terminal_size().columns
        console.width = terminal_width

        # Create new log file if needed (only if history is empty)
        if not conversation_history and session_name:
            log_filename = get_log_filename(session_name)

        # --- Determine if search is needed ---
        need_search = force_search

        search_results = []
        display_text = ""   # For showing user search results
        vertex_text = ""    # For feeding results to Vertex AI
        response_text = ""  # To store the final response from Vertex AI
        search_note = ""    # To add to history/log if search occurred

        # Timing for search operations
        search_start_time = None
        search_duration = 0

        # --- Perform Custom Search (if applicable) ---
        if search_method == SearchMethod.CUSTOM:
            # Check if this should be a search query
            if force_search or user_input.lower().startswith("search "):
                need_search = True
                search_start_time = time.time()
                search_query = user_input
                if user_input.lower().startswith("search "):
                    search_query = user_input[7:].strip()

                # Add timeout parameter to search request
                print(f"{COLOR_CYAN}Performing Google Custom Search for: {search_query}{COLOR_RESET}")
                search_results = search_web(search_query, timeout=10) # Add timeout parameter

                search_duration = time.time() - search_start_time
                if search_results:
                    display_text, vertex_text = format_search_results(search_results)
                    print(display_text) # Show results immediately
                    search_note = f"Note: Web search was performed in {search_duration:.2f}s to provide up-to-date information."

                    # Store the search results for context
                    last_search_results = vertex_text
                else:
                    print(f"{COLOR_CYAN}No search results found. (Search took {search_duration:.2f}s){COLOR_RESET}")
                    search_note = f"Note: Web search attempted but found no results. (Search took {search_duration:.2f}s)"

        # Timing for Vertex AI API operations
        api_start_time = time.time()
        api_duration = 0

        # --- Vertex AI Grounding Path ---
        if search_method == SearchMethod.GEMINI_GROUNDING:
            print(f"{COLOR_CYAN}Using Vertex AI's native grounding for this query...{COLOR_RESET}")
            search_note = "Note: Used Vertex AI's native grounding capability."  # Override previous note

            with console.status("[cyan]Thinking with grounding enabled...", spinner="dots"):
                try:
                    # Create a model with web search tool
                    grounding_model = GenerativeModel(
                        model_name=GROUNDING_MODEL_NAME,
                        tools=[Tool.from_google_search_retrieval()]
                    )

                    # Get active instruction if available
                    active_instruction, _ = None, None
                    try:
                        active_instruction, _ = instruction_manager.get_active_instruction()
                    except Exception as e:
                        print(
                            f"\n{Fore.YELLOW}Error getting active instruction: {e}. Continuing without instruction.{ColoramaStyle.RESET_ALL}")

                    # Build additional context for grounding if previous search results exist.
                    context_info = get_real_time_data()
                    if last_search_results:
                        context_info += f"\n\nPrevious search context: {last_search_results}"

                    full_prompt_for_grounding = f"{context_info}\n\nUser query: {user_input}"

                    # Configuration including system instruction if present
                    generation_config = GenerationConfig(
                        temperature=0.2,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=2048,
                    )

                    # Create content with system instruction if available
                    contents = []
                    if active_instruction:
                        contents.append(Content(role="system", parts=[Part.from_text(active_instruction)]))
                    contents.append(Content(role="user", parts=[Part.from_text(full_prompt_for_grounding)]))

                    # Generate content with grounding
                    response = grounding_model.generate_content(
                        contents=contents,
                        generation_config=generation_config
                    )

                    # Extract text from response
                    response_text = response.text
                    last_search_results = f"Recent search for '{user_input}':\n\n{response_text}"

                    api_duration = time.time() - api_start_time

                except Exception as e:
                    api_duration = time.time() - api_start_time
                    print(f"\n{Fore.RED}Grounding API Error:{ColoramaStyle.RESET_ALL} {str(e)}")
                    response_text = "Sorry, I encountered an error with the grounding feature."

        # --- Standard Model Path ---
        if search_method != SearchMethod.GEMINI_GROUNDING:
            if chat is None:
                # Initialize a new chat session if none exists
                model = GenerativeModel(model_name=current_chat_model_name)
                chat = model.start_chat(history=[])

            with console.status("[cyan]Thinking...", spinner="dots"):
                # For search results, always include that context when using custom search mode
                search_context = ""
                if search_results and search_method == SearchMethod.CUSTOM:
                    search_context = f"\n\nThe following are relevant search results to help answer the query: \n{vertex_text}"
                    search_context += "\nPlease use this information to provide an up-to-date response. Cite sources when appropriate."
                elif last_search_results and not search_results:
                    search_context = f"\n\nImportant context from previous searches: {last_search_results}"

                # Use the user's raw input and add search context if needed
                message_to_send = user_input
                if search_context:
                    if search_method == SearchMethod.CUSTOM and (force_search or user_input.lower().startswith("search ")):
                        # IMPROVED: Make the message more explicit to ensure search results are used
                        stripped_query = user_input[7:].strip() if user_input.lower().startswith("search ") else user_input
                        message_to_send = f"I need information about: {stripped_query}\n\n{search_context}\n\nBased on these search results from the web, please provide a comprehensive and factual answer about '{stripped_query}'. Incorporate information from the search results and cite sources where appropriate."
                    else:
                        message_to_send = f"{user_input}\n\n{search_context}"

                try:
                    # Send message to the chat
                    response = chat.send_message(message_to_send)
                    response_text = response.text
                    api_duration = time.time() - api_start_time
                except Exception as e:
                    api_duration = time.time() - api_start_time
                    print(f"\n{Fore.RED}Standard Model Error:{ColoramaStyle.RESET_ALL} {str(e)}")
                    response_text = "Sorry, I encountered an error generating a response."

        # Calculate total processing time
        total_duration = time.time() - start_time

        # --- Update History and Log ---
        conversation_history.append(f"You: {user_input}")
        save_to_file(f"You: {user_input}")
        if search_note:
            conversation_history.append(search_note)
            save_to_file(search_note)
        conversation_history.append(response_text)
        save_to_file(response_text)

        # --- Print Response ---
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(COLOR_CYAN + "Vertex AI Response" + (" (with grounding)" if current_search_method == SearchMethod.GEMINI_GROUNDING and search_note.startswith("Note: Used") else "") + COLOR_RESET)
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

        try:
            console.print(Markdown(response_text, code_theme="monokai"))
        except Exception:
            wrapped_text = print_wrapped_text(response_text)
            formatted_text = highlight_text(wrapped_text)
            print(formatted_text)

        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        formatted_datetime_info = get_formatted_datetime_info()
        print(
            f"{COLOR_CYAN}{formatted_datetime_info} | Response time: {total_duration:.2f}s total | API: {api_duration:.2f}s" +
            (f" | Search: {search_duration:.2f}s" if search_duration > 0 else "") + f"{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

    except Exception as e:
        print(f"\n{Fore.RED}Unhandled Error in ask_gemini_with_search:{ColoramaStyle.RESET_ALL} {str(e)}")
        save_to_file(f"\n--- ERROR ---\nError: {e}\n--- END ERROR ---\n")

# Entry point
if __name__ == "__main__":
    main()
