"""
Gemini CLI v9 - Enhanced command-line interface for Google's Gemini AI with:
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
from google import genai
from google.genai import types
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

# --- SDK Migration Change: Use Client ---
# Replace with your actual Gemini API key
API_KEY = "apykey"
# Add Google Custom Search API Key and Search Engine ID
GOOGLE_SEARCH_API_KEY = "apykey"
GOOGLE_SEARCH_CX = "apykey"

# --- SDK Migration Change: Initialize the client ---
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    print(f"{Fore.RED}Fatal Error: Could not initialize Google GenAI Client.{ColoramaStyle.RESET_ALL}")
    print(f"{Fore.RED}Error details: {e}{ColoramaStyle.RESET_ALL}")
    print(f"{Fore.YELLOW}Please ensure your API_KEY is valid and the 'google-genai' package is installed correctly.{ColoramaStyle.RESET_ALL}")
    exit(1) # Exit if client can't be created

# --- SDK Migration Change: Model name updated as per docs examples ---
DEFAULT_MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"
GROUNDING_MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"

# Define the folder structure
BASE_DIR = Path("/mnt/c/Users/Alex/gassistant")
instruction_manager = InstructionManager(BASE_DIR)
LOG_FOLDER = BASE_DIR / "logs"
PROMPT_FOLDER = BASE_DIR / "prompts"
SEARCH_FOLDER = BASE_DIR / "searches"

# Create necessary folders
LOG_FOLDER.mkdir(exist_ok=True)
PROMPT_FOLDER.mkdir(exist_ok=True)
SEARCH_FOLDER.mkdir(exist_ok=True)

# Define a custom style for the prompt input
from prompt_toolkit.styles import Style

# Your matrix green color as hex
MATRIX_GREEN = "#00FF00"  # This matches the green in your matrix_dark.yml

# Create a Style object with the desired colors
# The empty string style applies to the input text
style = Style.from_dict({
    '': MATRIX_GREEN,                  # Input text is green
    'prompt': f'bold {MATRIX_GREEN}',  # Prompt label is bold green
})

# Initialize the prompt session with both message and style
session = PromptSession(message="You: ", style=style)

# Global variables
chat = None  # Chat object
current_chat_model_name = DEFAULT_MODEL_NAME  # Current model name
conversation_history = []  # Global conversation history (list of strings from log)
last_search_results = None  # To store search results for context
log_filename = None  # Current log file

# Define ANSI colors
COLOR_USER = "\033[92m"       # Green for user input
COLOR_GEMINI = "\033[97m"   # Blue for Gemini's response (unused here)
COLOR_CYAN = "\033[92m"       # Cyan for names ("You:" and "Gemini:")
COLOR_RESET = "\033[0m"       # Reset color
COLOR_WHITE = "\033[97m"      # White for text


# Create custom theme for markdown rendering with your desired color
custom_theme = Theme({
    "markdown.text": "green",              # Use cyan for text
    "markdown.paragraph": "cyan",         # Apply cyan to paragraphs
    "markdown.code": "green",             # Keep code blocks distinct with white
    "markdown.link": "green underline",    # Links in cyan and underlined
    "markdown.list": "green",              # Lists in cyan
})

# Initialize console with theme
console = Console(width=terminal_width, highlight=False, theme=custom_theme)

def highlight_text(text):
    """
    Parse markdown-like formatting from Gemini's response and apply ANSI codes.
    - Lists: Replace '* ' at the start of a line with a bullet (•).
    - Bold: Replace '**text**' with bold ANSI formatting.
    - Italics: Replace '*text*' with italic ANSI formatting (if supported).
    """
    # Define ANSI color codes
    base_color = COLOR_GEMINI  # Base color for Gemini's response
    reset_color = COLOR_RESET  # Reset color
    code_fg_color = "\033[38;5;208m"  # Foreground color for code snippets (orange)
    code_bg_color = "\033[48;5;240m"  # Background color for code snippets (dark gray)
    bold_color = "\033[1m"  # Bold text
    italic_color = "\033[3m"  # Italic text

    # Apply base color to the entire text
    text = f"{base_color}{text}{reset_color}"

    # Regex pattern for code blocks
    code_block_pattern = r'```(.*?)```'
    # Change code snippet color
    text = re.sub(
        code_block_pattern,
        lambda m: f"\n{code_bg_color}{code_fg_color}{m.group(1)}{reset_color}\n",
        text,
        flags=re.DOTALL
    )

    # Handle list items, bold, and italics
    text = re.sub(r'^\* ', '• ', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', rf'{bold_color}\1{reset_color}', text)
    text = re.sub(r'\*(.*?)\*', rf'{italic_color}\1{reset_color}', text)

    return text

def get_log_filename(prefix=""):
    """Generate a new filename based on the current date and time."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if prefix:
        return Path(LOG_FOLDER) / f"{timestamp} {prefix}.txt"
    return Path(LOG_FOLDER) / f"{timestamp}.txt"

def save_to_file(text):
    """Append conversation history to the log file."""
    global log_filename
    if not log_filename:
        log_filename = get_log_filename()
        
    with open(log_filename, "a", encoding="utf-8") as file:
        file.write(text + "\n")

def get_latest_log_filename():
    """Retrieve the most recent log file from the LOG_FOLDER."""
    files = [f for f in os.listdir(LOG_FOLDER) if f.endswith(".txt")]
    if not files:
        return None
    # Sort by creation time (newest first)
    files.sort(key=lambda f: os.path.getctime(os.path.join(LOG_FOLDER, f)), reverse=True)
    return os.path.join(LOG_FOLDER, files[0])

def load_conversation_history(file_path):
    """Load conversation history from a specified log file."""
    history = []
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Split content into blocks (each consisting of a message and a response)
        blocks = re.split(r'You: ', content)[1:]  # Skip the first empty element

        for block in blocks:
            if block.strip():
                # Split the block into user message and AI response
                parts = block.split('\n', 1)
                user_message = parts[0].strip()

                # Add the user message to history
                history.append(f"You: {user_message}")

                # Add the AI response if available
                if len(parts) > 1 and parts[1].strip():
                    history.append(parts[1].strip())

        print(f"Conversation history loaded from '{file_path}'.")
    except Exception as e:
        print(f"Error loading log file '{file_path}': {e}")
    return history

def get_real_time_data():
    """Return the current date and time as a string."""
    now = datetime.datetime.now()
    return f"The current date and time is: {now.strftime('%Y-%m-%d %H:%M:%S')}."

def setup_database():
    """Create SQLite database for log management."""
    import sqlite3

    db_path = BASE_DIR / "logs.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table for log descriptions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS log_descriptions (
        filename TEXT PRIMARY KEY,
        description TEXT,
        first_prompt TEXT,
        created_date TEXT,
        last_accessed TEXT,
        description_updated INTEGER DEFAULT 0,
        tags TEXT
    )
    ''')

    conn.commit()
    conn.close()
    return db_path


def get_multiline_input(prompt_message="Enter text (type Ctrl+D or ESC followed by ENTER to finish):",
                        default_text=None):
    """Provide a full-featured multiline text editor with free movement and rich editing."""
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
    from prompt_toolkit.layout.containers import FloatContainer, Float
    from prompt_toolkit.widgets import TextArea, Frame, Box
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.filters import has_focus
    from prompt_toolkit.styles import Style
    from prompt_toolkit.lexers import PygmentsLexer
    from pygments.lexers import MarkdownLexer
    import re

    # Strip ANSI color codes for the editor title display
    clean_prompt = re.sub(r'\x1b\[[0-9;]*m', '', prompt_message)

    # Store the result
    result = [None]

    # Create key bindings
    kb = KeyBindings()

    @kb.add('c-d')
    @kb.add('escape', 'enter')
    def _(event):
        """Exit when user presses Ctrl+D or ESC followed by Enter."""
        result[0] = text_area.text
        event.app.exit()

    @kb.add('c-c')
    def _(event):
        """Exit and discard when user presses Ctrl+C."""
        result[0] = None
        event.app.exit()

    # Create text area with syntax highlighting
    text_area = TextArea(
        lexer=PygmentsLexer(MarkdownLexer),
        scrollbar=True,
        line_numbers=True,
        wrap_lines=True,
        focus_on_click=True,
        text="" if default_text is None else default_text,  # Ensure we never pass None
    )

    help_text = FormattedTextControl(
        [("class:help", " Ctrl+D or ESC+ENTER: Save and exit • Ctrl+C: Cancel ")]
    )

    style = Style.from_dict({
        'help': 'bg:#333333 #ffffff',
        'frame.border': '#888888',
    })

    app = Application(
        layout=Layout(
            FloatContainer(
                content=HSplit([
                    Frame(text_area),
                    Window(height=1, content=help_text),
                ]),
                floats=[],
            )
        ),
        key_bindings=kb,
        mouse_support=True,
        full_screen=True,
        style=style,
    )

    print(f"{prompt_message}")
    app.run()

    # Print the submitted text to console history
    if result[0] is not None:
        print("\n--- Your submitted text ---")
        print(result[0])
        print("-------------------------")

    return result[0]

def generate_description_for_log(filename):
    """Generate an AI description for an existing log file."""
    file_path = os.path.join(LOG_FOLDER, filename)
    if not os.path.exists(file_path):
        return f"Log file '{filename}' not found."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        first_prompt = None
        if "You: " in content:
            first_prompt = content.split("You: ", 1)[1]
            if "\n" in first_prompt:
                first_prompt = first_prompt.split("\n", 1)[0]

        if not first_prompt:
            return f"Could not extract first prompt from log '{filename}'."

        # Generate AI description
        description = generate_ai_description(content, first_prompt)

        # Update database
        import sqlite3
        db_path = BASE_DIR / "logs.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        created_date = datetime.datetime.fromtimestamp(
            os.path.getctime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
        INSERT OR REPLACE INTO log_descriptions
        (filename, description, first_prompt, created_date, last_accessed, description_updated)
        VALUES (?, ?, ?, ?, ?, 1)
        ''', (filename, description, first_prompt, created_date, last_accessed))

        conn.commit()
        conn.close()

        return f"AI-generated description for '{filename}': {description}"
    except Exception as e:
        return f"Error generating description: {str(e)}"


def update_log_description():
    """Update the description of the current log file."""
    global log_filename, conversation_history

    if not log_filename or not os.path.exists(log_filename):
        return

    # Connect to database
    import sqlite3
    db_path = BASE_DIR / "logs.db"
    if not os.path.exists(db_path):
        setup_database()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get filename from path
    filename = os.path.basename(log_filename)

    # First check if a record exists and get existing tags
    cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (filename,))
    result = cursor.fetchone()
    existing_tags = result[0] if result and result[0] else None

    # Extract first prompt from conversation history
    description = "No description available"
    first_prompt = None
    log_content = "\n".join(conversation_history)

    for line in conversation_history:
        if line.startswith("You: "):
            first_prompt = line[4:].strip()
            break

    if first_prompt:
        # Get active instruction if any
        active_instruction, active_name = instruction_manager.get_active_instruction()
        # Generate AI description with instruction context
        description = generate_ai_description(log_content, first_prompt, active_name)

    created_date = datetime.datetime.fromtimestamp(
        os.path.getctime(log_filename)).strftime("%Y-%m-%d %H:%M:%S")
    last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update or insert the description, preserving tags
    cursor.execute('''
    INSERT OR REPLACE INTO log_descriptions
    (filename, description, first_prompt, created_date, last_accessed, description_updated, tags)
    VALUES (?, ?, ?, ?, ?, 1, ?)
    ''', (filename, description, first_prompt, created_date, last_accessed, existing_tags))

    conn.commit()
    conn.close()

def process_loaded_history(history_log_lines):
    """Process loaded history (list of strings) into the global conversation_history list
       and populate the chat object's history if using a standard chat model."""
    global chat, current_search_method, conversation_history, client, current_chat_model_name

    # Always clear and repopulate the global conversation_history list from the loaded log
    conversation_history.clear()
    conversation_history.extend(history_log_lines) # Keep the raw log history

    # If using grounding, chat history is managed differently (stateless calls)
    # We don't populate a persistent global 'chat' object's history here.
    if current_search_method == SearchMethod.GEMINI_GROUNDING:
         chat = None # Ensure standard chat object is None
         print(f"{Fore.YELLOW}History loaded for logging. Grounding sessions are stateless.{ColoramaStyle.RESET_ALL}")
         return

    # --- SDK Migration Change: Create chat using client if not in grounding mode ---
    # If using standard model, ensure 'chat' exists and populate its history
    print(f"{Fore.CYAN}Re-initializing chat session with loaded history...{ColoramaStyle.RESET_ALL}")
    # Convert the log history (list of strings) into the SDK's expected format
    sdk_history = []
    user_message = None
    model_response_parts = []

    for line in history_log_lines: # Iterate the raw log lines passed in
        line_strip = line.strip()
        if not line_strip: continue # Skip empty lines

        # Ignore notes added by the script WHEN populating chat.history
        if line_strip.startswith("Note:"):
             continue # Skip notes for the chat object's history

        if line.startswith("You: "):
            # If we have a pending model response, add the previous turn to sdk_history
            if user_message is not None and model_response_parts:
                 try:
                     # --- Fix: Ensure parts are dictionaries/objects, not raw strings ---
                     sdk_history.append({"role": "user", "parts": [{'text': user_message}]})
                     sdk_history.append({"role": "model", "parts": [{'text': "\n".join(model_response_parts)}]})
                 except Exception as e:
                     print(f"{Fore.RED}Error processing history turn: {e}{ColoramaStyle.RESET_ALL}")

            # Start new turn
            user_message = line[4:].strip()
            model_response_parts = []

        elif user_message is not None: # If we are expecting a model response
            model_response_parts.append(line) # Append the raw line

    # Add the last turn if it exists
    if user_message is not None and model_response_parts:
        try:
            # --- Fix: Ensure parts are dictionaries/objects, not raw strings ---
            sdk_history.append({"role": "user", "parts": [{'text': user_message}]})
            sdk_history.append({"role": "model", "parts": [{'text': "\n".join(model_response_parts)}]})
        except Exception as e:
            print(f"{Fore.RED}Error processing final history turn: {e}{ColoramaStyle.RESET_ALL}")

    # --- SDK Migration Change: Create chat session with history ---
    try:
        # Use the client to create the chat session
        active_instruction, _ = None, None
        try:
            active_instruction, _ = instruction_manager.get_active_instruction()
        except Exception as e:
            print(f"{Fore.YELLOW}Error getting active instruction: {e}. Continuing without instruction.{ColoramaStyle.RESET_ALL}")
            
        if active_instruction:
            chat = client.chats.create(model=current_chat_model_name, history=sdk_history, system_instruction=active_instruction)
            print(f"{Fore.CYAN}Chat session re-created with history using model '{current_chat_model_name}' and active system instruction.{ColoramaStyle.RESET_ALL}")
        else:
            chat = client.chats.create(model=current_chat_model_name, history=sdk_history)
            print(f"{Fore.CYAN}Chat session re-created with history using model '{current_chat_model_name}'.{ColoramaStyle.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error creating chat session with history: {e}{ColoramaStyle.RESET_ALL}")
        print(f"{Fore.YELLOW}Starting a new empty chat session.{ColoramaStyle.RESET_ALL}")
        # Fallback to an empty chat
        try:
            chat = client.chats.create(model=current_chat_model_name, history=[])
        except Exception as e2:
            print(f"{Fore.RED}Fatal Error: Could not create even an empty chat session: {e2}{ColoramaStyle.RESET_ALL}")
            chat = None # Ensure chat is None if creation fails

def print_wrapped_text(text):
    """Print text wrapped to the terminal width with proper word boundaries."""
    terminal_width = shutil.get_terminal_size().columns
    # Use textwrap for proper word boundary wrapping
    wrapped_lines = []

    # Process text line by line to handle markdown properly
    for line in text.split('\n'):
        # If the line is longer than the terminal width, wrap it
        if (len(line) > terminal_width):
            # Adjust width slightly to account for possible color codes
            wrap_width = max(terminal_width - 5, 40)  # Don't go below 40 chars width
            wrapped_line = textwrap.fill(line, width=wrap_width, break_long_words=False, replace_whitespace=False)
            wrapped_lines.append(wrapped_line)
        else:
            wrapped_lines.append(line)

    return '\n'.join(wrapped_lines)

def save_prompt_template(name, prompt_text, description=""):
    """Save a prompt template to the prompts folder."""
    # Auto-generate description if it's empty
    if not description:
        description = generate_ai_prompt_description(prompt_text)
        
    prompt_data = {
        "prompt": prompt_text,
        "description": description,
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    file_path = PROMPT_FOLDER / f"{name}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(prompt_data, f, indent=2)

    return file_path

def list_prompts():
    """List all saved prompt templates."""
    prompts = []
    for file in os.listdir(PROMPT_FOLDER):
        if file.endswith(".json"):
            try:
                with open(os.path.join(PROMPT_FOLDER, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    prompts.append({
                        "name": file[:-5],  # Remove .json extension
                        "description": data.get("description", "No description"),
                        "created": data.get("created", "Unknown")
                    })
            except Exception as e:
                print(f"Error loading prompt file '{file}': {e}")

    return prompts

def load_prompt_template(name):
    """Load a prompt template by name."""
    file_path = PROMPT_FOLDER / f"{name}.json"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("prompt", "")
    except Exception as e:
        print(f"Error loading prompt template '{name}': {e}")
        return None

def search_web(query, num_results=5, timeout=10):
    """Search the web using Google Custom Search API with timeout."""
    search_url = "https://www.googleapis.com/customsearch/v1"

    params = {
        'key': GOOGLE_SEARCH_API_KEY,
        'cx': GOOGLE_SEARCH_CX,
        'q': query,
        'num': num_results
    }

    try:
        with console.status("[cyan]Searching the web...", spinner="dots2"):
            response = requests.get(search_url, params=params, timeout=timeout)
            response.raise_for_status()  # Raise exception for non-200 responses
            results = response.json()

            # Save search results to file for reference
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            search_file = SEARCH_FOLDER / f"search_{timestamp}.json"
            with open(search_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

            # Format search results
            formatted_results = []

            if 'items' in results:
                for item in results['items']:
                    formatted_results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'displayLink': item.get('displayLink', '')
                    })

                return formatted_results
            else:
                return []
    except requests.exceptions.Timeout:
        print(f"\n{Fore.RED}Search Timeout:{ColoramaStyle.RESET_ALL} The search request took too long to complete")
        return []
    except Exception as e:
        print(f"\n{Fore.RED}Search Error:{ColoramaStyle.RESET_ALL} {str(e)}")
        return []

def format_search_results(results):
    """Format search results for display and for use with Gemini."""
    if not results:
        return "No search results found."

    # Format for display
    display_text = "\n" + COLOR_CYAN + "Web Search Results:" + COLOR_RESET + "\n"
    for i, result in enumerate(results, 1):
        display_text += f"{i}. {COLOR_WHITE}{result['title']}{COLOR_RESET}\n"
        display_text += f"   {result['link']}\n"
        display_text += f"   {result['snippet']}\n\n"

    # Format for Gemini (plain text)
    gemini_text = "Web search results:\n\n"
    for i, result in enumerate(results, 1):
        gemini_text += f"{i}. Title: {result['title']}\n"
        gemini_text += f"   URL: {result['link']}\n"
        gemini_text += f"   Snippet: {result['snippet']}\n\n"

    return display_text, gemini_text

def ask_gemini_with_search(user_input, session_name="", force_search=False, search_method=None):
    """Send the user's input to Gemini with optional web search, update conversation history, and save the session."""
    global log_filename, client, chat, conversation_history, current_search_method, current_chat_model_name
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
        gemini_text = ""    # For feeding results to Gemini
        response_text = ""  # To store the final response from Gemini
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
                    display_text, gemini_text = format_search_results(search_results)
                    print(display_text) # Show results immediately
                    search_note = f"Note: Web search was performed in {search_duration:.2f}s to provide up-to-date information."
                    
                    # Store the search results for context
                    last_search_results = gemini_text
                else:
                    print(f"{COLOR_CYAN}No search results found. (Search took {search_duration:.2f}s){COLOR_RESET}")
                    search_note = f"Note: Web search attempted but found no results. (Search took {search_duration:.2f}s)"

        # Timing for Gemini API operations
        api_start_time = time.time()
        api_duration = 0

        # --- SDK Migration Change: Grounding Path uses client.models.generate_content ---
        if search_method == SearchMethod.GEMINI_GROUNDING:
            print(f"{COLOR_CYAN}Using Gemini's native grounding for this query...{COLOR_RESET}")
            search_note = "Note: Used Gemini's native grounding capability."  # Override previous note

            with console.status("[cyan]Thinking with grounding enabled...", spinner="dots"):
                try:
                    google_search_tool = types.Tool(
                        google_search=types.GoogleSearch()
                    )

                    # Use the specific model for grounding
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
                    config_args = {"tools": [google_search_tool]}
                    if active_instruction:
                        config_args["system_instruction"] = active_instruction

                    response = client.models.generate_content(
                        model=GROUNDING_MODEL_NAME,  # Use the grounding model
                        contents=full_prompt_for_grounding,
                        config=types.GenerateContentConfig(**config_args)
                    )

                    # Extract text from response
                    if hasattr(response, 'text'):
                        response_text = response.text
                        last_search_results = f"Recent search for '{user_input}':\n\n{response_text}"
                    elif response.parts:
                        response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                        last_search_results = f"Recent search for '{user_input}':\n\n{response_text}"
                    else:
                        response_text = "Error: Could not extract text from grounded response."

                    api_duration = time.time() - api_start_time

                except Exception as e:
                    api_duration = time.time() - api_start_time
                    print(f"\n{Fore.RED}Grounding API Error:{ColoramaStyle.RESET_ALL} {str(e)}")
                    response_text = "Sorry, I encountered an error with the grounding feature."

        # --- SDK Migration Change: Standard Model Path uses 'chat' object created by client ---
        if search_method != SearchMethod.GEMINI_GROUNDING:
            if chat:
                with console.status("[cyan]Thinking...", spinner="dots"):
                    # For search results, always include that context when using custom search mode
                    search_context = ""
                    if search_results and search_method == SearchMethod.CUSTOM:
                        search_context = f"\n\nThe following are relevant search results to help answer the query: \n{gemini_text}"
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
                        # This will use the existing chat history automatically
                        response = chat.send_message(message_to_send)
                        response_text = response.text
                        api_duration = time.time() - api_start_time
                    except Exception as e:
                        api_duration = time.time() - api_start_time
                        print(f"\n{Fore.RED}Standard Model Error:{ColoramaStyle.RESET_ALL} {str(e)}")
                        response_text = "Sorry, I encountered an error generating a response."
            else:
                response_text = "Error: No active chat session. Please try using 'reset' to create a new session."
                print(f"\n{Fore.RED}No active chat session:{ColoramaStyle.RESET_ALL} Please try using 'reset' to create a new session.")

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
        print(COLOR_CYAN + "Gemini Response" + (" (with grounding)" if current_search_method == SearchMethod.GEMINI_GROUNDING and search_note.startswith("Note: Used") else "") + COLOR_RESET)
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

def print_conversation_history():
    """Print the entire loaded conversation history."""
    global conversation_history

    if not conversation_history:
        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No conversation history loaded.{COLOR_RESET}")
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

        print()  # Add blank line for separation

    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

def switch_search_method(new_method):
    """Switch between search methods and adjust chat state if needed."""
    global chat, current_search_method, conversation_history, client, current_chat_model_name

    previous_method = current_search_method
    current_search_method = new_method # Update the global state first

    switching_to_grounding = (new_method == SearchMethod.GEMINI_GROUNDING)
    switching_from_grounding = (previous_method == SearchMethod.GEMINI_GROUNDING and not switching_to_grounding)
    switching_to_custom = (new_method == SearchMethod.CUSTOM)

    if switching_to_grounding:
        print(f"{Fore.CYAN}Switching to Grounding mode. Standard chat session will be inactive.{ColoramaStyle.RESET_ALL}")
        chat = None # Grounding uses stateless calls, no persistent chat object needed
        return "Switched to Gemini's native grounding capability."

    elif switching_from_grounding:
        print(f"{Fore.CYAN}Switching away from Grounding mode. Re-initializing standard chat session...{ColoramaStyle.RESET_ALL}")
        current_log_history = conversation_history.copy()
        current_chat_model_name = DEFAULT_MODEL_NAME
        process_loaded_history(current_log_history)
        if new_method == SearchMethod.CUSTOM:
            return "Switched to custom Google search."
        else:
            return "All search methods disabled."
    elif switching_to_custom:
        # Always reinitialize the chat when switching to custom search mode
        print(f"{Fore.CYAN}Switching to Custom Search mode. Initializing chat session...{ColoramaStyle.RESET_ALL}")
        try:
            # Use the client to create the chat session with conversation history
            if conversation_history:
                sdk_history = instruction_manager._convert_history_to_sdk_format(conversation_history)
                active_instruction, _ = instruction_manager.get_active_instruction()
                
                if active_instruction:
                    chat = client.chats.create(model=current_chat_model_name, history=sdk_history, system_instruction=active_instruction)
                else:
                    chat = client.chats.create(model=current_chat_model_name, history=sdk_history)
            else:
                active_instruction, _ = instruction_manager.get_active_instruction()
                
                if active_instruction:
                    chat = client.chats.create(model=current_chat_model_name, history=[], system_instruction=active_instruction)
                else:
                    chat = client.chats.create(model=current_chat_model_name, history=[])
            
            return "Switched to custom Google search."
        except Exception as e:
            print(f"{Fore.RED}Error initializing chat session: {e}{ColoramaStyle.RESET_ALL}")
            return "Switched to custom Google search, but encountered an error initializing the chat session."
    else:
        return "All search methods disabled."

# Create a dictionary mapping commands to their detailed help text with examples
COMMAND_HELP = {
    "help": {
        "description": "Display help information about commands",
        "usage": "help [command]",
        "examples": [
            "help - Show all available commands",
            "help search - Show detailed help for the search command"
        ]
    },
    "search": {
        "description": "Perform a web search and keep results in context for follow-up questions",
        "usage": "search <query>",
        "examples": [
            "search latest AI research papers",
            "search current weather in London"
        ]
    },
    "logs": {
        "description": "Show all available conversation logs with their descriptions",
        "usage": "logs",
        "examples": [
            "logs - Display all saved conversation logs"
        ]
    },
    "load": {
        "description": "Load a conversation history from file",
            "usage": "load [filename] [--with_history]",
            "examples": [
                "load - Load the most recent conversation",
                "load --with_history - Load the most recent conversation and print its history",
                "load 2023-11-24_14-22-33.txt - Load a specific log file",
                "load 2023-11-24_14-22-33.txt --with_history - Load a specific log file and print its history"
            ]
    },
    "prompts": {
        "description": "List all saved prompt templates",
        "usage": "prompts",
        "examples": [
            "prompts - Show all available prompt templates with descriptions"
        ]
    },
    "save prompt": {
        "description": "Save the last user message as a reusable prompt template",
        "usage": "save prompt <name> [description]",
        "examples": [
            "save prompt story_helper - Save last prompt with default description",
            "save prompt code_review A template for reviewing Python code - Save with custom description"
        ]
    },
    "use prompt": {
        "description": "Load and use a saved prompt template",
        "usage": "use prompt <name>",
        "examples": [
            "use prompt story_helper - Apply the story_helper template to your next message"
        ]
    },
    "roles": {
        "description": "List all saved AI role profiles",
        "usage": "roles",
        "examples": [
            "roles - Display all saved AI role profiles"
        ]
    },
    "save role": {
        "description": "Save a system role profile for future use",
        "usage": "save role <name> [description]",
        "examples": [
            "save role python_expert - Saves the role you enter",
            "save role sql_tutor SQL expertise role - Saves with description"
        ]
    },
    "use role": {
        "description": "Apply a saved role profile to the current session",
        "usage": "use role <name>",
        "examples": [
            "use role python_expert - Apply the Python expert role to the current chat"
        ]
    },
    "clear role": {
        "description": "Remove the active system role",
        "usage": "clear role",
        "examples": [
            "clear role - Return to default AI behavior without special roles"
        ]
    },
    "show role": {
        "description": "Display the currently active system role",
        "usage": "show role",
        "examples": [
            "show role - See what role is currently active"
        ]
    },
    "delete role": {
        "description": "Delete a saved role profile",
        "usage": "delete role <name>",
        "examples": [
            "delete role python_expert - Delete the Python expert role profile"
        ]
    },
    "delete instruction": {
        "description": "Delete a saved instruction profile",
        "usage": "delete instruction <name>",
        "examples": [
            "delete instruction python_expert - Delete the Python expert instruction profile"
        ]
    },
    "show search method": {
        "description": "Display the current search method being used",
        "usage": "show search method",
        "examples": [
            "show search method - See which search capability is active"
        ]
    },
    "use cs": {
        "description": "Switch to custom Google search method",
        "usage": "use cs",
        "examples": [
            "use cs - Enable custom search API for better control over search results"
        ]
    },
    "use gs": {
        "description": "Switch to Gemini's native grounding capability",
        "usage": "use gs",
        "examples": [
            "use gs - Enable Gemini's built-in search capabilities"
        ]
    },
    "disable search": {
        "description": "Disable all search methods",
        "usage": "disable search",
        "examples": [
            "disable search - Turn off all search functionality"
        ]
    },
    "reset": {
        "description": "Clear the current conversation history and start a new chat session",
        "usage": "reset",
        "examples": [
            "reset - Start a fresh conversation while maintaining settings"
        ]
    },
    "reset database": {
        "description": "Archive logs and reset the log database",
        "usage": "reset database",
        "examples": [
            "reset database - Move all logs to archive folder and create a new database"
        ]
    },
    "textbox": {
        "description": "Open a flexible multiline text editor for writing structured content",
        "usage": "textbox, writing_mode or wm",
        "examples": [
            "textbox - Open the multiline editor",
            "writing_mode - Alternative command to open the editor",
            "wr - Shortcut to open the editor"
        ]
    },
    "lookup": {
        "description": "Perform a quick web search without affecting conversation history",
        "usage": "lookup <query> or ql <query>",
        "examples": [
            "lookup current weather in Berlin",
            "ql latest AI news"
        ]
    },
    "ask": {
        "description": "Ask Gemini a question without affecting conversation history",
        "usage": "ask <query> or qg <query>",
        "examples": [
            "ask what is the capital of France",
            "qg explain quantum computing"
        ]
    },
    "edit description": {
        "description": "Edit the description of a selected log file",
        "usage": "edit description",
        "examples": [
            "edit description - Select a log and update its description"
        ]
    },
    "show context": {
        "description": "Display the current context window being sent to Gemini",
        "usage": "show context",
        "examples": [
            "show context - Show what Gemini is remembering from your conversation, including chat history and search results"
        ]
    },
    "favorite": {
        "description": "Mark a log file as a favorite for easier identification",
        "usage": "favorite <log_index or filename>",
        "examples": [
            "favorite 3 - Mark the log with index 3 as a favorite",
            "favorite 2023-04-18_22-57-12.txt - Mark a specific log file"
        ]
    },
    "unfavorite": {
        "description": "Remove the favorite mark from a log file",
        "usage": "unfavorite <log_index or filename>",
        "examples": [
            "unfavorite 3 - Remove the favorite mark from log with index 3",
            "unfavorite 2023-04-18_22-57-12.txt - Remove the favorite mark from a specific log file"
        ]
    },
    "view log": {
        "description": "View the contents of a log file without loading it into your active conversation",
        "usage": "view log <log_index or filename>",
        "examples": [
            "view log 3 - View the conversation history in log with index 3",
            "view log 2023-04-18_22-57-12.txt - View a specific log file"
        ]
    },
}

def show_command_help(command):
    """Display detailed help for a specific command."""
    if command in COMMAND_HELP:
        help_info = COMMAND_HELP[command]
        help_panel = Panel(
            f"[white]{help_info['description']}[/white]\n\n"
            f"[bold cyan]Usage:[/bold cyan]\n[white]{help_info['usage']}[/white]\n\n"
            f"[bold cyan]Examples:[/bold cyan]\n" + "\n".join(f"[yellow]•[/yellow] [white]{ex}[/white]" for ex in help_info['examples']),
            title=f"[bold magenta]Help: {command}[/bold magenta]",
            expand=False,
            border_style="cyan"
        )
        console.print(help_panel)
        return True
    return False

# Updated display_help function
def display_help():
    """Display help information about available commands, organized by categories."""
    help_table = Table(title="[bold magenta]Available Commands[/bold magenta]", expand=True)
    help_table.add_column("[cyan]Command[/cyan]", style="bold cyan")
    help_table.add_column("[white]Description[/white]", style="bold white")

    # General Commands
    help_table.add_row("[bold yellow]General Commands[/bold yellow]", "")
    help_table.add_row("[cyan]help[/cyan]", "Show this help message")
    help_table.add_row("[cyan]help <command>[/cyan]", "Provides detailed help for a specific comman")
    help_table.add_row("[cyan]exit, quit[/cyan]", "[white]Exit the application[white]")
    help_table.add_row("[cyan]reset[/cyan]", "[white]Clear the current conversaShow this help messagetion history and start a new chat session[white]")
    help_table.add_row("[cyan]reset database[/cyan]", "[white]Archive logs and reset the log database[white]")

    # Log Management
    help_table.add_row("\n[bold yellow]Log Management[/bold yellow]", "")
    help_table.add_row("[cyan]logs[/cyan]", "[white]List all available conversation logs[white]")
    help_table.add_row("[cyan]load, load last[/cyan]", "[white]Load the most recent conversation history[white]")
    help_table.add_row("[cyan]load <filename>[/cyan]", "[white]Load a specific conversation history file[white]")
    help_table.add_row("[cyan]load --with_history[/cyan]", "[white]Load and display the conversation history[white]")
    help_table.add_row("[cyan]generate description <filename>[/cyan]", "[white]Generate AI description for a log file[white]")
    help_table.add_row("[cyan]edit log[/cyan]", "[white]Edit the description of a selected log file[white]")

    # Prompt Management
    help_table.add_row("\n[bold yellow]Prompt Management[/bold yellow]", "")
    help_table.add_row("[cyan]prompts[/cyan]", "[white]List all saved prompt templates[white]")
    help_table.add_row("[cyan]save prompt <name>[/cyan]", "[white]Save the last message as a prompt template[white]")
    help_table.add_row("[cyan]save prompt <name> <description[/cyan]", "[white]Save prompt with description[white]")
    help_table.add_row("[cyan]use prompt <name>[/cyan]", "[white]Load and use a saved prompt template[white]")

    # Instruction Management
    # Modify the "Instruction Management" section in the display_help function
    help_table.add_row("\n[bold yellow]Role Management[/bold yellow]", "")
    help_table.add_row("[cyan]roles[/cyan]", "[white]List all saved AI role profiles[white]")
    help_table.add_row("[cyan]save role <name>[/cyan]", "[white]Save a system role profile[white]")
    help_table.add_row("[cyan]save role <name> <description[/cyan]", "[white]Save role with description[white]")
    help_table.add_row("[cyan]use role <name>[/cyan]","[white]Apply a saved role profile to the current session[white]")
    help_table.add_row("[cyan]edit role <name>[/cyan]", "[white]Edit an existing role profile[white]")
    help_table.add_row("[cyan]clear role[/cyan]", "[white]Remove the active system role[white]")
    help_table.add_row("[cyan]show role[/cyan]", "[white]Display the currently active system role[white]")
    help_table.add_row("[cyan]delete role <name>[/cyan]", "[white]Delete a saved role profile[/white]")

    # Search Features
    help_table.add_row("\n[bold yellow]Search Features[/bold yellow]", "")
    help_table.add_row("[cyan]search <query>[/cyan]", "[white]Perform a web search and keep results in context for follow-up questions[white]")
    help_table.add_row("[cyan]lookup <query>, ql <query>[/cyan]","[white]Perform a quick web search without affecting conversation history[white]")
    help_table.add_row("[cyan]ask <query>, qg <query>[/cyan]","[white]Ask Gemini a question without affecting conversation history[white]")
    help_table.add_row("[cyan]clear search context[/cyan]", "[white]Clear previously searched information from context[white]")
    help_table.add_row("[cyan]show search context[/cyan]", "[white]Display the current search context[white]")
    help_table.add_row("[cyan]show context[/cyan]", "[white]Display what Gemini is remembering from your conversation[white]")
    help_table.add_row("[cyan]use cs[/cyan]", "[white]Switch to custom Google search method (Custom Search)[white]")
    help_table.add_row("[cyan]use gs[/cyan]", "[white]Switch to Gemini's native grounding capability (Grounding Search)[white]")
    help_table.add_row("[cyan]disable search[/cyan]", "[white]Disable all search methods (Custom and Grounding)[white]")
    help_table.add_row("[cyan]show search method[/cyan]", "[white]Display the current search method[white]")

    # Textbox Feature
    help_table.add_row("\n[bold yellow]Textbox Feature[/bold yellow]", "")
    help_table.add_row("[cyan]textbox, writing_mode, wm[/cyan]","Open a flexible multiline text editor for writing structured content")

    console.print(help_table)

def edit_log_description():
    """Allow the user to edit the description of a log."""
    import sqlite3

    db_path = BASE_DIR / "logs.db"

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch all logs
    cursor.execute("""
        SELECT filename, description, created_date
        FROM log_descriptions
        ORDER BY created_date DESC
    """)
    logs = cursor.fetchall()

    if not logs:
        print("No logs available to edit.")
        conn.close()
        return

    # Display logs for selection
    print("Available logs:")
    for i, (filename, description, created_date) in enumerate(logs, start=1):
        print(f"{i}. {filename} - {description} (Created: {created_date})")

    # Prompt user to select a log
    try:
        choice = int(input("Enter the number of the log you want to edit: "))
        if choice < 1 or choice > len(logs):
            print("Invalid choice.")
            conn.close()
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        conn.close()
        return

    selected_log = logs[choice - 1]
    filename = selected_log[0]

    # Prompt for a new description
    new_description = input(f"Enter a new description for '{filename}': ").strip()
    if not new_description:
        print("Description cannot be empty.")
        conn.close()
        return

    # Update the database
    try:
        cursor.execute("""
            UPDATE log_descriptions
            SET description = ?, description_updated = 1
            WHERE filename = ?
        """, (new_description, filename))
        conn.commit()
        print(f"Description for '{filename}' updated successfully.")
    except Exception as e:
        print(f"Error updating description: {e}")
    finally:
        conn.close()

def list_logs():
    """List all available logs with descriptions from the database."""
    import sqlite3
    db_path = BASE_DIR / "logs.db"

    logs = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Modified query to include tags
    cursor.execute("""
        SELECT l.filename, l.description, l.created_date, l.tags
        FROM log_descriptions l
        ORDER BY l.created_date DESC
    """)

    db_logs = cursor.fetchall()

    # Process log files with tags included
    for file in os.listdir(LOG_FOLDER):
        if file.endswith(".txt"):
            file_path = os.path.join(LOG_FOLDER, file)
            file_size = os.path.getsize(file_path) / 1024  # Size in KB

            # Find in database results
            description = "No description"
            created_date = datetime.datetime.fromtimestamp(os.path.getctime(file_path))
            created_date_str = created_date.strftime("%Y-%m-%d %H:%M:%S %a")  # Add day abbreviation
            tags = ""
            is_favorite = False

            for db_log in db_logs:
                if db_log[0] == file:
                    description = db_log[1] or "No description"
                    try:
                        created_date = datetime.datetime.strptime(db_log[2], "%Y-%m-%d %H:%M:%S")
                        created_date_str = created_date.strftime("%Y-%m-%d %H:%M:%S %a")  # Add day abbreviation
                    except (ValueError, TypeError):
                        pass  # Keep the previously defined created_date
                    tags = db_log[3] or ""
                    # Check if this is a favorite log
                    if tags and "favorite:" in tags:
                        is_favorite = True
                    break

            logs.append({
                "filename": file,
                "description": description,
                "date": created_date_str,
                "date_obj": created_date,  # Store datetime object for sorting
                "size": file_size,
                "tags": tags,
                "is_favorite": is_favorite
            })

    conn.close()

    # First sort logs by date (oldest first) to assign index numbers
    logs.sort(key=lambda x: x["date_obj"])  # Sort in ascending order by date
    
    # Assign sequential index numbers (oldest = 1, newest = highest)
    total_logs = len(logs)
    for i, log in enumerate(logs, 1):
        log["index"] = i
    
    # Now sort logs by date (newest first) for display
    logs.sort(key=lambda x: x["date_obj"], reverse=True)  # Sort in descending order by date
    
    logs_table = Table(title="Available Logs", expand=True)
    logs_table.add_column("Index", style="bright_cyan", justify="right")
    logs_table.add_column("Filename", style="cyan")
    logs_table.add_column("Size (KB)", justify="right")
    logs_table.add_column("Description")
    logs_table.add_column("Tags", style="yellow")  # Column for tags

    # Display logs with most recent at top but with correct index numbers
    for log in logs:
        # More subtle favorites highlighting as requested
        if log['is_favorite']:
            # Just a single star on the index, and yellow color but no stars for the filename
            index_display = f"[bold yellow]★ {log['index']}[/bold yellow]"
            filename_display = f"[bold yellow]{log['filename']}[/bold yellow]"
            description_style = "[italic bright_white]" + log["description"] + "[/italic bright_white]"
        else:
            index_display = str(log["index"])
            filename_display = log["filename"]
            description_style = log["description"]
        
        logs_table.add_row(
            index_display,
            filename_display,
            f"{log['size']:.1f}",
            description_style,
            log['tags']
        )

    console.print(logs_table)
    return logs

def quick_lookup(query):
    """Perform a quick lookup using Gemini's grounding capability without affecting conversation history."""
    print(f"{COLOR_CYAN}Quick lookup (using Gemini grounding): {query}{COLOR_RESET}")

    try:
        with console.status("[cyan]Getting Gemini information...", spinner="dots"):
            # Set up the Google search tool
            google_search_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            # Get active instruction if available
            active_instruction, _ = instruction_manager.get_active_instruction()

            # Configuration for grounding
            config_args = {
                "tools": [google_search_tool],
                "temperature": 0.2  # More factual responses
            }

            if active_instruction:
                config_args["system_instruction"] = active_instruction

            # Make the request with proper grounding configuration
            response = client.models.generate_content(
                model=GROUNDING_MODEL_NAME,
                contents=[{"role": "user", "parts": [{"text": f"Please answer this query using up-to-date information from reliable sources: {query}"}]}],
                config=types.GenerateContentConfig(**config_args)
            )

            if hasattr(response, 'text'):
                result = response.text
            elif response.parts:
                result = response.parts[0].text
            else:
                result = "No response received"

        # Print the response with formatting
        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)
        print(f"{COLOR_CYAN}Quick Lookup (Gemini Grounding Response):{COLOR_RESET}")
        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)

        try:
            console.print(Markdown(result))
        except Exception:
            print(f"{COLOR_GEMINI}{result}{COLOR_RESET}")

        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)
    except Exception as e:
        print(f"{COLOR_CYAN}Error during quick Gemini lookup: {str(e)}{COLOR_RESET}")

def quick_ask(query):
    """Perform a quick lookup using Gemini's standard model without affecting conversation history."""
    print(f"{COLOR_CYAN}Quick lookup (using Gemini): {query}{COLOR_RESET}")

    try:
        with console.status("[cyan]Getting Gemini information...", spinner="dots"):
            # Use Gemini without grounding - use specifically gemini-2.0-flash for test compatibility
            response = client.models.generate_content(
                model="gemini-2.0-flash",  # Use specific model name for test compatibility
                contents=[{"role": "user", "parts": [{"text": query}]}]
            )

            if hasattr(response, 'text'):
                result = response.text
            elif response.parts:
                result = response.parts[0].text
            else:
                result = "No response received"

        # Print the response with formatting
        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)
        print(f"{COLOR_CYAN}Quick Lookup (Gemini Response):{COLOR_RESET}")
        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)

        try:
            console.print(Markdown(result))
        except Exception:
            print(f"{COLOR_GEMINI}{result}{COLOR_RESET}")

        print(f"{COLOR_CYAN}─" * shutil.get_terminal_size().columns + COLOR_RESET)
    except Exception as e:
        print(f"{COLOR_CYAN}Error during quick lookup: {str(e)}{COLOR_RESET}")

def generate_ai_description(log_content, first_prompt, active_instruction_name=None):
    """Use Gemini to generate a concise log description."""
    try:
        # Add instruction context to prompt if available
        instruction_context = ""
        if active_instruction_name:
            instruction_context = f"\nThis conversation used the '{active_instruction_name}' instruction profile."

        # Use a smaller model for efficiency
        generation_model = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"""Create a very brief (3-5 word) title for this conversation that captures its essence.

First user question: {first_prompt}{instruction_context}

Keep it concise and descriptive. Do not use quotes or formatting. Respond with just the title text.""",
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=20,
                top_p=0.95,
            )
        )

        description = generation_model.text.strip()
        # Sanitize the description
        if len(description) > 50:
            description = description[:47] + "..."
        return description
    except Exception as e:
        # Fall back to first prompt on error
        return first_prompt[:50] + ("..." if len(first_prompt) > 50 else "")

def generate_ai_prompt_description(prompt_text):
    """Use Gemini to generate a concise prompt description."""
    try:
        # Use a smaller model for efficiency
        generation_model = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"""Create a very brief (4-8 word) description of what this prompt template is designed to do:

Prompt: {prompt_text}

Keep it concise and descriptive. Do not use quotes or formatting. Respond with just the description text.""",
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=20,
                top_p=0.95,
            )
        )

        description = generation_model.text.strip()
        # Sanitize the description
        if len(description) > 50:
            description = description[:47] + "..."
        return description
    except Exception as e:
        # Fall back to a generic description on error
        return "Prompt template for specialized queries"

def reset_log_database():
    """Delete the logs database and create a fresh one."""

    import shutil
    from pathlib import Path

    # Path to database file
    db_path = BASE_DIR / "logs.db"

    # Create archive folder
    archive_folder = BASE_DIR / "logs_archived"
    archive_folder.mkdir(exist_ok=True)

    # Move log files to archive
    log_count = 0
    for log_file in LOG_FOLDER.glob("*.txt"):
        archive_path = archive_folder / log_file.name
        shutil.copy2(log_file, archive_path)
        log_count += 1

    for log_file in LOG_FOLDER.glob("*.txt"):
        try:
            log_file.unlink()  # Deletes the file
        except Exception as e:
            print(f"Failed to delete {log_file.name}: {e}")

    # Remove old database
    if db_path.exists():
        try:
            db_path.unlink()
            print(f"Removed old database: {db_path}")
        except Exception as e:
            print(f"Error removing database: {e}")

    # Create fresh database
    setup_database()

    return log_count


def cleanup_client():
    """Properly clean up the Google GenAI client before program exit."""
    global client, chat
    try:
        # First set chat to None
        chat = None

        # Then handle client cleanup
        if hasattr(client, '_sync_client') and client._sync_client is not None:
            client._sync_client._transport = None

        if hasattr(client, '_async_client') and client._async_client is not None:
            client._async_client._transport = None

        # Finally set client to None
        client = None
    except Exception:
        pass  # Suppress errors during shutdown

def save_conversation_on_reset():
    """Save the current conversation history to a new log file when reset is called."""
    global log_filename, conversation_history
    
    # Only save if we have conversation history
    if not conversation_history:
        return None
    
    # Generate a new log filename
    new_log_filename = get_log_filename("reset")
    
    # Save all conversation history to the new file
    with open(new_log_filename, "w", encoding="utf-8") as file:
        for line in conversation_history:
            file.write(line + "\n")
            
    # Update the database with a description for this log
    import sqlite3
    db_path = BASE_DIR / "logs.db"
    
    if not os.path.exists(db_path):
        setup_database()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get filename from path
    filename = os.path.basename(new_log_filename)
    
    # Extract first prompt from conversation history
    description = "Conversation until reset"
    first_prompt = None
    log_content = "\n".join(conversation_history)
    
    for line in conversation_history:
        if line.startswith("You: "):
            first_prompt = line[4:].strip()
            break
    
    if first_prompt:
        # Get active instruction if any
        active_instruction, active_name = None, None
        try:
            active_instruction, active_name = instruction_manager.get_active_instruction()
        except Exception:
            pass
            
        # Generate AI description with instruction context
        description = generate_ai_description(log_content, first_prompt, active_name)
    
    created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update or insert the description
    cursor.execute('''
    INSERT OR REPLACE INTO log_descriptions
    (filename, description, first_prompt, created_date, last_accessed, description_updated, tags)
    VALUES (?, ?, ?, ?, ?, 1, ?)
    ''', (filename, description, first_prompt, created_date, created_date, "reset"))
    
    conn.commit()
    conn.close()
    
    return new_log_filename

def show_context_window():
    """Show the current context window that would be sent to Gemini."""
    global conversation_history, client, chat, current_search_method, last_search_results
    
    terminal_width = shutil.get_terminal_size().columns
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(COLOR_CYAN + "Context Window Content" + COLOR_RESET)
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    
    # Get real-time info that would be included in context
    real_time_info = get_real_time_data()
    print(f"{COLOR_CYAN}Real-time Context:{COLOR_RESET}")
    print(f"{COLOR_WHITE}{real_time_info}{COLOR_RESET}")
    print()
    
    # Show system instruction if any
    active_instruction, active_instruction_name = None, None
    try:
        active_instruction, active_instruction_name = instruction_manager.get_active_instruction()
    except Exception as e:
        pass
    
    if active_instruction:
        print(f"{COLOR_CYAN}Active System Instruction ({active_instruction_name}):{COLOR_RESET}")
        print(f"{COLOR_WHITE}{active_instruction}{COLOR_RESET}")
        print()
    
    # Show conversation history
    if conversation_history:
        print(f"{COLOR_CYAN}Conversation History:{COLOR_RESET}")
        history_count = 0
        for line in conversation_history:
            if line.startswith("You: "):
                print(f"{COLOR_USER}{line}{COLOR_RESET}")
                history_count += 1
            elif line.startswith("Note:"):
                print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
            else:
                # This is a model response - may be truncated for display purposes
                if len(line) > 500:
                    preview = line[:500] + "... [truncated for display]"
                    print(f"{COLOR_WHITE}{preview}{COLOR_RESET}")
                else:
                    print(f"{COLOR_WHITE}{line}{COLOR_RESET}")
                history_count += 1
            print()
        
        print(f"{COLOR_CYAN}Total conversation turns: {history_count // 2}{COLOR_RESET}")
    else:
        print(f"{COLOR_CYAN}No conversation history loaded.{COLOR_RESET}")
    
    # Show search context if any
    if last_search_results:
        print(f"\n{COLOR_CYAN}Search Context:{COLOR_RESET}")
        if len(last_search_results) > 500:
            preview = last_search_results[:500] + "... [truncated for display]"
            print(f"{COLOR_WHITE}{preview}{COLOR_RESET}")
        else:
            print(f"{COLOR_WHITE}{last_search_results}{COLOR_RESET}")
    
    # Show SDK format if standard chat mode
    if current_search_method != SearchMethod.GEMINI_GROUNDING and chat:
        print(f"\n{COLOR_CYAN}Chat Model: {current_chat_model_name}{COLOR_RESET}")
    elif current_search_method == SearchMethod.GEMINI_GROUNDING:
        print(f"\n{COLOR_CYAN}Using Gemini Grounding with model: {GROUNDING_MODEL_NAME}{COLOR_RESET}")
    
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
    print(f"{COLOR_CYAN}Search Method: {current_search_method.name}{COLOR_RESET}")
    print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)

def view_log(target):
    """View the contents of a log file without loading it into the active conversation."""
    if not target:
        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please specify a log file by index or filename.{COLOR_RESET}")
        return
    
    # Check if it's an index or a filename
    try:
        idx = int(target)
        # Get all logs
        all_logs = list_logs()
        total_logs = len(all_logs)
        
        if 1 <= idx <= total_logs:
            # Get filename at the right position (converting displayed index to actual index)
            filename = all_logs[total_logs - idx]["filename"]
        else:
            print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid log index. Please use a number between 1 and {total_logs}.{COLOR_RESET}")
            return
    except ValueError:
        # Not a number, treat as filename
        filename = target
    
    # Find the full path
    log_path = os.path.join(LOG_FOLDER, filename)
    if not os.path.exists(log_path):
        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Log file not found: '{filename}'.{COLOR_RESET}")
        return
    
    try:
        # Read the log file
        with open(log_path, "r", encoding="utf-8") as file:
            content = file.read()
        
        # Prepare the content for display
        terminal_width = shutil.get_terminal_size().columns
        
        # Connect to database to get description and tags
        db_path = BASE_DIR / "logs.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT description, tags FROM log_descriptions WHERE filename = ?", (filename,))
        result = cursor.fetchone()
        conn.close()
        
        description = "No description available"
        tags = ""
        
        if result:
            if result[0]:
                description = result[0]
            if result[1]:
                tags = result[1]
        
        # Display log information
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(f"{COLOR_CYAN}Log File: {COLOR_WHITE}{filename}{COLOR_RESET}")
        print(f"{COLOR_CYAN}Description: {COLOR_WHITE}{description}{COLOR_RESET}")
        if tags:
            print(f"{COLOR_CYAN}Tags: {COLOR_WHITE}{tags}{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(COLOR_CYAN + "Conversation Content" + COLOR_RESET)
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        
        # Process the content line by line for better formatting
        lines = content.split('\n')
        for line in lines:
            if line.startswith("You: "):
                print(f"{COLOR_USER}{line}{COLOR_RESET}")
            elif line.startswith("Note:"):
                print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
            else:
                # Could be a model response, try with Markdown rendering
                try:
                    console.print(Markdown(line))
                except Exception:
                    print(f"{COLOR_WHITE}{line}{COLOR_RESET}")
                    
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        print(f"{COLOR_CYAN}End of log file {COLOR_WHITE}{filename}{COLOR_RESET}")
        print(COLOR_CYAN + "─" * terminal_width + COLOR_RESET)
        
        # Add info that this was just a view, not a load
        print(f"{COLOR_CYAN}Note: {COLOR_WHITE}This log was only viewed. Your active conversation was not changed.{COLOR_RESET}")
        
    except Exception as e:
        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Error reading log file: {str(e)}{COLOR_RESET}")

# Register cleanup function
atexit.register(cleanup_client)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced Gemini AI client with prompt management and web search.")
    parser.add_argument("--load-log", nargs="?", const="latest", default=None,
                        help=("Load a conversation log at startup. "
                              "Provide the exact filename (with spaces allowed) or omit to load the latest log."))
    parser.add_argument("--use-prompt", metavar="PROMPT_NAME", help="Use a saved prompt template at startup")
    parser.add_argument("--session-name", metavar="NAME", help="Name for this session (for log file naming)")

    # Setup database and register the exit handler
    setup_database()
    atexit.register(update_log_description)

    search_group = parser.add_argument_group('search options')
    search_method_arg = search_group.add_mutually_exclusive_group()
    search_method_arg.add_argument("--custom-search", action="store_true", help="Enable custom Google search")
    search_method_arg.add_argument("--gemini-grounding", action="store_true", help="Enable Gemini's native grounding")

    parser.add_argument("prompt", nargs="*", help="Your question to Gemini")
    args = parser.parse_args()

    if args.session_name:
        log_filename = get_log_filename(args.session_name)

    # Default to NONE (search disabled)
    current_search_method = SearchMethod.NONE
    
    # Only enable search if explicitly requested
    if args.gemini_grounding:
        current_search_method = SearchMethod.GEMINI_GROUNDING
        chat = None
        print(f"{Fore.CYAN}Starting in Grounding mode.{ColoramaStyle.RESET_ALL}")
    elif args.custom_search:
        current_search_method = SearchMethod.CUSTOM
        print(f"{Fore.CYAN}Starting with Custom Search mode.{ColoramaStyle.RESET_ALL}")
        try:
            chat = client.chats.create(model=DEFAULT_MODEL_NAME, history=[])
        except Exception as e:
            print(f"{Fore.RED}Error initializing chat session on startup: {e}{ColoramaStyle.RESET_ALL}")
            chat = None
    else:
        # Default case - no search
        try:
            chat = client.chats.create(model=DEFAULT_MODEL_NAME, history=[])
            current_chat_model_name = DEFAULT_MODEL_NAME
            print(f"{Fore.CYAN}Starting with search disabled (default). Initialized chat with model '{current_chat_model_name}'.{ColoramaStyle.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error initializing chat session on startup: {e}{ColoramaStyle.RESET_ALL}")
            chat = None

    if args.load_log:
        log_to_load_path = None
        if args.load_log == "latest":
            latest_log = get_latest_log_filename()
            if (latest_log):
                log_to_load_path = latest_log
            else:
                print("No log files found to load.")
        else:
            log_to_load_path = os.path.join(LOG_FOLDER, args.load_log)

        if log_to_load_path and os.path.exists(log_to_load_path):
            loaded_history_lines = load_conversation_history(log_to_load_path)
            if loaded_history_lines:
                process_loaded_history(loaded_history_lines)
        elif log_to_load_path:
             print(f"Log file not found: {log_to_load_path}")

    prompt_text = " ".join(args.prompt)
    if args.use_prompt:
        loaded_prompt = load_prompt_template(args.use_prompt)
        if loaded_prompt:
            if prompt_text:
                prompt_text = f"{loaded_prompt}\n\nSpecific query: {prompt_text}"
            else:
                prompt_text = loaded_prompt
            print(f"Using prompt template: {args.use_prompt}")

    if prompt_text:
        print(f"{COLOR_USER}You: {COLOR_USER}{prompt_text}{COLOR_RESET}")
        is_search = prompt_text.lower().startswith("search ") and current_search_method == SearchMethod.CUSTOM
        ask_gemini_with_search(prompt_text, args.session_name, force_search=is_search, search_method=current_search_method)
    else:
        method_name = current_search_method.name.lower().replace('_', ' ')
        print(f"Current search method: {method_name}.")

    while True:
        try:
            if current_search_method != SearchMethod.GEMINI_GROUNDING and not chat:
                print(f"{Fore.YELLOW}No active chat session. Creating a new one...{ColoramaStyle.RESET_ALL}")
                try:
                    chat = client.chats.create(model=current_chat_model_name, history=[])
                    print(f"{Fore.CYAN}New chat session started with model '{current_chat_model_name}'.{ColoramaStyle.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}Error creating chat session: {e}. Please try restarting.{ColoramaStyle.RESET_ALL}")
                    break

            prompt_text = session.prompt(HTML('<prompt>You:</prompt> '))

            if prompt_text.lower() == "edit log":
                edit_log_description()
                continue

            if prompt_text.lower() == "textbox" or prompt_text.lower() == "writing_mode" or prompt_text.lower() == "wm":
                text = get_multiline_input("Enter your text in multiline mode:")
                if text is not None:
                    print(
                        f"{COLOR_CYAN}Multiline text captured ({len(text.splitlines())} lines). What would you like to do with it?{COLOR_RESET}")
                    print(
                        f"{COLOR_CYAN}Options: use it as a prompt (type 'prompt'), save as instruction (type 'save instruction <name>'), or cancel (type 'cancel'){COLOR_RESET}")

                    action = session.prompt(HTML('<prompt>Action: </prompt> '))

                    if action.lower() == "prompt":
                        # Use as a prompt immediately
                        ask_gemini_with_search(text, force_search=False, search_method=current_search_method)
                    elif action.lower().startswith("save instruction "):
                        # Save as an instruction
                        name = action[16:].strip()
                        if name:
                            success, message = instruction_manager.save_instruction_profile(name, text)
                            print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                        else:
                            print(
                                f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please provide a name for the instruction.{COLOR_RESET}")
                continue

            if prompt_text.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if prompt_text.lower() == "help":
                display_help()
                continue

            # In the main command handling loop, add this condition:
            if prompt_text.lower().startswith("help "):
                command = prompt_text[5:].strip()
                if not show_command_help(command):
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No help available for '{command}'.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "show search method":
                method_name = current_search_method.name.lower().replace('_', ' ')
                print(f"{COLOR_CYAN}Current search method:{COLOR_RESET} {COLOR_WHITE}{method_name}{COLOR_RESET}")
                continue
            
            if prompt_text.lower() == "clear search context":
                last_search_results = None
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Search context has been cleared from memory.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "show search context":
                if last_search_results:
                    print(f"{COLOR_CYAN}Current search context:{COLOR_RESET}")
                    console.print(Panel(last_search_results, title="Search Context", border_style="cyan"))
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No search context in memory.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "use cs":
                message = switch_search_method(SearchMethod.CUSTOM)
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                continue

            if prompt_text.lower() == "use gs":
                message = switch_search_method(SearchMethod.GEMINI_GROUNDING)
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                continue

            if prompt_text.lower() == "disable search":
                message = switch_search_method(SearchMethod.NONE)
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                continue

            if prompt_text.lower() in ["load", "load last"]:
                log_to_load = get_latest_log_filename()
                if not log_to_load:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No log files found to load.{COLOR_RESET}")
                else:
                    loaded_history_lines = load_conversation_history(log_to_load)
                    if loaded_history_lines:
                        process_loaded_history(loaded_history_lines)
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Loaded conversation history from latest log: '{os.path.basename(log_to_load)}'.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Failed to load latest conversation history.{COLOR_RESET}")
                continue
            
            if prompt_text.lower() == "show instruction":
                active_instruction, active_instruction_name = instruction_manager.get_active_instruction()
                if active_instruction:
                    print(f"{COLOR_CYAN}Current system instruction ({active_instruction_name}):{COLOR_RESET}")
                    console.print(Panel(active_instruction, title="System Instruction", border_style="cyan"))
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No active system instruction.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "logs":
                list_logs()
                continue

            # Replace the existing "load" and "load last" command handlers with this:
            if prompt_text.lower() in ["load", "load last"] or prompt_text.lower() in ["load --with_history",
                                                                                       "load last --with_history"]:
                print_history = "--with_history" in prompt_text.lower()
                log_to_load = get_latest_log_filename()
                if not log_to_load:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No log files found to load.{COLOR_RESET}")
                else:
                    loaded_history_lines = load_conversation_history(log_to_load)
                    if loaded_history_lines:
                        process_loaded_history(loaded_history_lines)
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Loaded conversation history from latest log: '{os.path.basename(log_to_load)}'.{COLOR_RESET}")

                        # Print history if flag is present
                        if print_history:
                            print_conversation_history()
                    else:
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Failed to load latest conversation history.{COLOR_RESET}")
                continue

            # Replace the existing "load <filename>" command handler with this:
            if prompt_text.lower().startswith("load ") and not prompt_text.lower() == "load last":
                parts = prompt_text.split()
                print_history = "--with_history" in parts
                
                # Remove the --with_history flag if present
                if print_history:
                    parts.remove("--with_history")
                
                # Check for numeric index vs. filename
                try:
                    # If the second part is a number, treat it as an index
                    if len(parts) > 1 and parts[1].isdigit():
                        idx = int(parts[1])
                        # Get all logs
                        all_logs = list_logs()
                        total_logs = len(all_logs)
                        
                        if 1 <= idx <= total_logs:
                            # We need to handle the index conversion correctly
                            # Since logs are sorted oldest first but displayed newest with highest number,
                            # we need to do this conversion: If displaying index N (out of T total),
                            # we want the log at position (N-1) in the array
                            filename_to_load = all_logs[total_logs - idx]["filename"]  # Get filename at the right position
                        else:
                            print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid log index. Please use a number between 1 and {total_logs}.{COLOR_RESET}")
                            continue
                    else:
                        # Reconstruct the filename (might contain spaces)
                        filename_to_load = " ".join(parts[1:])
                except (ValueError, IndexError):
                    # Reconstruct the filename (might contain spaces)
                    filename_to_load = " ".join(parts[1:])

                log_path = os.path.join(LOG_FOLDER, filename_to_load)
                if os.path.exists(log_path):
                    loaded_history_lines = load_conversation_history(log_path)
                    if loaded_history_lines:
                        process_loaded_history(loaded_history_lines)
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Loaded conversation history from '{filename_to_load}'.{COLOR_RESET}")

                        # Print history if flag is present
                        if print_history:
                            print_conversation_history()
                    else:
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Failed to load conversation history from '{filename_to_load}'.{COLOR_RESET}")
                else:
                    print(
                        f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Log file not found: '{filename_to_load}'.{COLOR_RESET}")
                continue


            if prompt_text.lower() == "roles" or prompt_text.lower() == "instructions":
                instructions = instruction_manager.list_instruction_profiles()
                if not instructions:
                    print(
                        f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No saved role profiles found.{COLOR_RESET}")
                else:
                    instructions_table = Table(title="Saved AI Role Profiles", expand=True)
                    instructions_table.add_column("Index", style="bright_cyan", justify="right")
                    instructions_table.add_column("Name", style="cyan")
                    instructions_table.add_column("Description")
                    instructions_table.add_column("Created")
                    instructions_table.add_column("Last Used")

                    # Get the total number of roles
                    total_roles = len(instructions)
                    
                    # We'll number them in reverse order with newest getting the highest number
                    # Reversed list to show newest first
                    for i, instruction_data in enumerate(reversed(instructions)):
                        instructions_table.add_row(
                            str(total_roles - i),  # Numbering: newest = highest number, oldest = lowest
                            instruction_data["name"],
                            instruction_data["description"],
                            instruction_data["created"],
                            instruction_data["last_used"]
                        )

                    console.print(instructions_table)
                continue

            # Handle save role command
            if prompt_text.lower().startswith("save role ") or prompt_text.lower().startswith("save instruction "):
                cmd_parts = prompt_text.split(" ", 2)
                name = cmd_parts[2].split(" ", 1)[0] if len(cmd_parts) >= 3 else ""
                description = cmd_parts[2].split(" ", 1)[1] if len(cmd_parts) >= 3 and " " in cmd_parts[2] else ""

                instruction_text = get_multiline_input(f"{COLOR_CYAN}Enter system role for '{name}':{COLOR_RESET}")

                if instruction_text and instruction_text.strip():
                    success, message = instruction_manager.save_instruction_profile(name, instruction_text,
                                                                                      description)
                    message = message.replace("instruction", "role")
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                else:
                    print(
                        f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Role creation cancelled or empty input.{COLOR_RESET}")
                continue

            # Handle use role command
            if prompt_text.lower().startswith("use role ") or prompt_text.lower().startswith("use instruction "):
                name_or_index = prompt_text.split(" ", 2)[2] if len(prompt_text.split(" ", 2)) > 2 else ""
                
                # Check if it's a number (index-based selection)
                try:
                    idx = int(name_or_index)
                    # Get all instructions/roles
                    all_instructions = instruction_manager.list_instruction_profiles()
                    total_roles = len(all_instructions)
                    
                    if 1 <= idx <= total_roles:
                        # Roles are displayed with newest first (reversed from original order)
                        # and numbered so that:
                        # - tyler_durden (oldest) should be 1
                        # - david_goggins (middle) should be 2 
                        # - winston_churchill (newes    t) should be 3
                        
                        # We need to access the roles in original order (oldest first)
                        # For idx=1, we want the oldest role at position 0 in the original list
                        role_index = idx - 1  # Convert from 1-based to 0-based index
                        name = all_instructions[role_index]["name"]
                        print(f"{COLOR_CYAN}Selected role: {name} (with display number {idx}){COLOR_RESET}")
                    else:
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid role index. Please use a number between 1 and {total_roles}.{COLOR_RESET}")
                        continue
                except ValueError:
                    # Not a number, treat as name
                    name = name_or_index

                if not log_filename:
                    log_filename = get_log_filename()
                    # Create the empty file to ensure it exists for tagging
                    with open(log_filename, "a", encoding="utf-8") as f:
                        pass

                instruction_text, description = instruction_manager.load_instruction_profile(name)
                if instruction_text:
                    success, message, new_chat = instruction_manager.apply_instruction(
                        instruction_text, name, chat, client, current_chat_model_name,
                        conversation_history, current_search_method, log_filename)

                    message = message.replace("instruction", "role")
                    if success and new_chat:
                        chat = new_chat
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Role '{name}' not found.{COLOR_RESET}")
                continue

            # Handle clear role command
            if prompt_text.lower() == "clear role" or prompt_text.lower() == "clear instruction":
                active_instruction, _ = instruction_manager.get_active_instruction()
                if active_instruction:
                    success, message = instruction_manager.clear_instruction()
                    message = message.replace("instruction", "role")

                    # Need to recreate chat without system instruction
                    if current_search_method != SearchMethod.GEMINI_GROUNDING and chat is not None:
                        try:
                            sdk_history = instruction_manager._convert_history_to_sdk_format(conversation_history)
                            chat = client.chats.create(model=current_chat_model_name, history=sdk_history)
                            message += " Chat session has been reset."
                        except Exception as e:
                            message += f" Error resetting chat: {e}"

                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No active role to clear.{COLOR_RESET}")
                continue

            # Handle show role command
            if prompt_text.lower() == "show role" or prompt_text.lower() == "show instruction":
                active_instruction, active_instruction_name = instruction_manager.get_active_instruction()
                if active_instruction:
                    print(f"{COLOR_CYAN}Current system role ({active_instruction_name}):{COLOR_RESET}")
                    console.print(Panel(active_instruction, title="System Role", border_style="cyan"))
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No active system role.{COLOR_RESET}")
                continue

            # Handle delete role command
            if prompt_text.lower().startswith("delete role ") or prompt_text.lower().startswith(
                    "delete instruction "):
                name = prompt_text.split(" ", 2)[2] if len(prompt_text.split(" ", 2)) > 2 else ""
                if not name:
                    print(
                        f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please provide the name of the role to delete.{COLOR_RESET}")
                    continue

                # Ask for confirmation
                confirm = input(f"{COLOR_CYAN}Are you sure you want to delete role '{name}'? (y/n):{COLOR_RESET} ")
                if confirm.lower() != 'y':
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Deletion cancelled.{COLOR_RESET}")
                    continue

                success, message = instruction_manager.delete_instruction_profile(name)
                message = message.replace("instruction", "role")
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")

                # If it was active and we're not in grounding mode, ensure chat is recreated
                active_instruction, _ = instruction_manager.get_active_instruction()
                if not active_instruction and success and current_search_method != SearchMethod.GEMINI_GROUNDING and "has been cleared" in message:
                    try:
                        sdk_history = instruction_manager._convert_history_to_sdk_format(conversation_history)
                        chat = client.chats.create(model=current_chat_model_name, history=sdk_history)
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Chat session has been reset.{COLOR_RESET}")
                    except Exception as e:
                        print(
                            f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Error resetting chat: {str(e)}{COLOR_RESET}")
                continue

            # Handle edit role command
            # Handle edit role command
            if prompt_text.lower().startswith("edit role ") or prompt_text.lower().startswith("edit instruction "):
                name = prompt_text.split(" ", 2)[2] if len(prompt_text.split(" ", 2)) > 2 else ""
                instruction_text, description = instruction_manager.load_instruction_profile(name)

                if instruction_text:
                    print(f"{COLOR_CYAN}Current role:{COLOR_RESET}")
                    console.print(Panel(instruction_text, title=f"Role: {name}", border_style="cyan"))

                    # Use the multiline textbox for editing instead of line-by-line input
                    new_instruction = get_multiline_input(
                        f"{COLOR_CYAN}Edit role (prefilled with current content):{COLOR_RESET}",
                        default_text=instruction_text)

                    # Only update if content was actually changed
                    if new_instruction is None or new_instruction == instruction_text:
                        new_instruction = None
                        print(f"{COLOR_CYAN}Role content unchanged.{COLOR_RESET}")

                    print(f"{COLOR_CYAN}Current description:{COLOR_RESET} {COLOR_WHITE}{description}{COLOR_RESET}")
                    new_description = input(
                        f"{COLOR_CYAN}Enter new description (or press Enter to keep current):{COLOR_RESET} ")
                    if not new_description.strip():
                        new_description = None

                    success, message = instruction_manager.edit_instruction_profile(name, new_instruction,
                                                                                    new_description)
                    message = message.replace("instruction", "role")
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}{message}{COLOR_RESET}")

                    # If the active instruction was edited, apply the changes
                    active_instruction, active_instruction_name = instruction_manager.get_active_instruction()
                    if success and name == active_instruction_name:
                        reloaded_text, _ = instruction_manager.load_instruction_profile(name)
                        if reloaded_text:
                            success, message, new_chat = instruction_manager.apply_instruction(
                                reloaded_text, name, chat, client,
                                current_chat_model_name, conversation_history,
                                current_search_method, log_filename
                            )

                            # Update chat if a new one was created
                            if new_chat is not None:
                                chat = new_chat

                            print(
                                f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Updated role has been reapplied to the session.{COLOR_RESET}")
                else:
                    print(
                        f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Role profile '{name}' not found.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "reset":
                # Save the conversation history to a new log file before clearing
                saved_log = save_conversation_on_reset()
                if saved_log:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Conversation saved to log file: {os.path.basename(saved_log)}{COLOR_RESET}")
                
                # Clear conversation history and reset as before
                conversation_history.clear()
                last_search_results = None  # Also clear search context
                chat = None
                if current_search_method != SearchMethod.GEMINI_GROUNDING:
                    try:
                        chat = client.chats.create(model=current_chat_model_name, history=[])
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Conversation history cleared and new chat session started!{COLOR_RESET}")
                    except Exception as e:
                         print(f"{Fore.RED}Error starting new chat session after reset: {e}{ColoramaStyle.RESET_ALL}")
                else:
                     print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Conversation history cleared! Grounding mode remains active (stateless).{COLOR_RESET}")
                continue

            if prompt_text.lower() == "prompts":
                prompts = list_prompts()
                if not prompts:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No saved prompt templates found.{COLOR_RESET}")
                else:
                    prompts_table = Table(title="Saved Prompt Templates", expand=True)
                    prompts_table.add_column("Index", style="bright_cyan", justify="right")
                    prompts_table.add_column("Name", style="cyan")
                    prompts_table.add_column("Description")
                    prompts_table.add_column("Created")
                    
                    # Sort prompts by creation date - ASCENDING (oldest first)
                    try:
                        prompts.sort(key=lambda x: datetime.datetime.strptime(x["created"], "%Y-%m-%d %H:%M:%S") if x["created"] != "Unknown" else datetime.datetime.min)
                    except (ValueError, KeyError):
                        pass  # Skip sorting if there's any issue
                    
                    # Get total number of prompts
                    total_prompts = len(prompts)
                    
                    # Reverse the list to show newest prompts at the top
                    prompts.reverse()
                        
                    # Add index numbers starting from the bottom (oldest) to the top (newest)
                    for i, prompt_data in enumerate(prompts):
                        # Calculate index: newest prompts at the top get the highest numbers 
                        # (i is 0 for the first item which is now newest after reverse)
                        index = total_prompts - i
                        
                        prompts_table.add_row(
                            str(index),  # Show higher index for newer prompts
                            prompt_data["name"],
                            prompt_data["description"],
                            prompt_data["created"]
                        )

                    console.print(prompts_table)
                continue

            if prompt_text.lower().startswith("save prompt "):
                parts = prompt_text[12:].strip().split(" ", 1)
                name = parts[0]
                description = parts[1] if len(parts) > 1 else ""

                last_user_message_index = -1
                for i in range(len(conversation_history) - 1, -1, -1):  # Fixed the range error
                    if conversation_history[i].startswith("You: "):
                        last_user_message_index = i
                        break

                if last_user_message_index != -1:
                    last_prompt = conversation_history[last_user_message_index][4:].strip()
                    file_path = save_prompt_template(name, last_prompt, description)
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Prompt template saved as '{name}'.{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}No previous user message found in history to save.{COLOR_RESET}")
                continue

            if prompt_text.lower().startswith("use prompt "):
                name_or_index = prompt_text[11:].strip()
                
                # Check if it's a number (index-based selection)
                try:
                    idx = int(name_or_index)
                    # Get all prompts first
                    all_prompts = list_prompts()
                    
                    # Get total number of prompts
                    total_prompts = len(all_prompts)
                    
                    if 1 <= idx <= total_prompts:
                        # For clarity, let's print what we're doing
                        print(f"{COLOR_CYAN}Looking for prompt with index {idx}...{COLOR_RESET}")
                        
                        # Sort by creation date (oldest first)
                        all_prompts.sort(key=lambda x: datetime.datetime.strptime(x["created"], "%Y-%m-%d %H:%M:%S") if x["created"] != "Unknown" else datetime.datetime.min)
                        
                        # Our display shows newest prompts at the top with highest numbers,
                        # so index 3 (if there are 3 prompts) should be the newest prompt
                        # Find the prompt that corresponds to this display index
                        target_prompt = all_prompts[idx-1]
                        name = target_prompt["name"]
                        print(f"{COLOR_CYAN}Selected prompt: {name} ({target_prompt['description']}){COLOR_RESET}")
                    else:
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid prompt index. Please use a number between 1 and {total_prompts}.{COLOR_RESET}")
                        continue
                except ValueError:
                    # Not a number, treat as name
                    name = name_or_index
                    
                loaded_prompt = load_prompt_template(name)
                if loaded_prompt:
                    # Show the prompt content to the user
                    print(f"{COLOR_CYAN}Prompt template '{name}':{COLOR_RESET}")
                    console.print(Panel(loaded_prompt, title=f"Prompt: {name}", border_style="cyan"))
                    
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Enter your specific query or press Enter to use as is.{COLOR_RESET}")
                    specific_query = session.prompt(HTML('<prompt>Specific query (optional):</prompt> '))

                    if log_filename and os.path.exists(log_filename):
                        update_log_tags(log_filename, "Prompt", name)

                    if specific_query.strip():
                        final_prompt = f"{loaded_prompt}\n\nSpecific query: {specific_query}"
                    else:
                        final_prompt = loaded_prompt

                    print(f"{COLOR_USER}You: {COLOR_WHITE}{final_prompt}{COLOR_RESET}")

                    is_search = final_prompt.lower().startswith("search ") and current_search_method == SearchMethod.CUSTOM
                    ask_gemini_with_search(final_prompt, force_search=is_search, search_method=current_search_method)
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Prompt template '{name}' not found.{COLOR_RESET}")
                continue

            if prompt_text.lower() == "reset database":
                print(
                    f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Archiving logs and resetting database...{COLOR_RESET}")
                log_count = reset_log_database()
                print(
                    f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Archived {log_count} logs and created fresh database.{COLOR_RESET}")
                continue

            if prompt_text.lower().startswith("search "):
                # Extract the search query
                search_query = prompt_text[7:].strip()
                if search_query:
                    # Special note to add to conversation history about search context
                    conversation_history.append(f"Note: The following is a web search for '{search_query}'. Results will be kept in context for follow-up questions.")
                    save_to_file(f"Note: The following is a web search for '{search_query}'. Results will be kept in context for follow-up questions.")
                    
                    # Use the currently active search method instead of always defaulting to GEMINI_GROUNDING
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Performing web search using current search method ({current_search_method.name})...{COLOR_RESET}")
                    ask_gemini_with_search(search_query, force_search=True, search_method=current_search_method)
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please provide a search query.{COLOR_RESET}")
                continue

            if prompt_text.lower().startswith("generate description "):
                # Extract the log name more carefully
                log_name = prompt_text[len("generate description "):].strip()
                result = generate_description_for_log(log_name)
                print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_GEMINI}{result}{COLOR_RESET}")
                continue

            # Add lookup command here
            elif prompt_text.lower().startswith("lookup ") or prompt_text.lower().startswith("ql "):
                lookup_query = prompt_text[7:] if prompt_text.lower().startswith("lookup ") else prompt_text[3:]
                quick_lookup(lookup_query.strip())
                continue

            elif prompt_text.lower().startswith("ask ") or prompt_text.lower().startswith("qg "):
                gemini_query = prompt_text[4:] if prompt_text.lower().startswith("ask ") else prompt_text[3:]
                quick_ask(gemini_query.strip())
                continue

            if prompt_text.lower() == "show context":
                show_context_window()
                continue

            # Add favorite/unfavorite command handlers
            if prompt_text.lower().startswith("favorite "):
                target = prompt_text[9:].strip()
                if not target:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please specify a log file by index or filename.{COLOR_RESET}")
                    continue
                
                # Check if it's an index or a filename
                try:
                    idx = int(target)
                    # Get all logs
                    all_logs = list_logs()
                    total_logs = len(all_logs)
                    
                    if 1 <= idx <= total_logs:
                        # Get filename at the right position (converting displayed index to actual index)
                        filename = all_logs[total_logs - idx]["filename"]
                    else:
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid log index. Please use a number between 1 and {total_logs}.{COLOR_RESET}")
                        continue
                except ValueError:
                    # Not a number, treat as filename
                    filename = target
                
                # Find the full path
                log_path = os.path.join(LOG_FOLDER, filename)
                if not os.path.exists(log_path):
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Log file not found: '{filename}'.{COLOR_RESET}")
                    continue
                
                # Update the log tags to add a favorite marker (⭐ or *)
                success = update_log_tags(log_path, "favorite", "⭐")
                if success:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Added favorite mark (⭐) to log: '{filename}'.{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Failed to update log tags.{COLOR_RESET}")
                continue
            
            if prompt_text.lower().startswith("unfavorite "):
                target = prompt_text[11:].strip()
                if not target:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Please specify a log file by index or filename.{COLOR_RESET}")
                    continue
                
                # Check if it's an index or a filename
                try:
                    idx = int(target)
                    # Get all logs
                    all_logs = list_logs()
                    total_logs = len(all_logs)
                    
                    if 1 <= idx <= total_logs:
                        # Get filename at the right position
                        filename = all_logs[total_logs - idx]["filename"]
                    else:
                        print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Invalid log index. Please use a number between 1 and {total_logs}.{COLOR_RESET}")
                        continue
                except ValueError:
                    # Not a number, treat as filename
                    filename = target
                
                # Find the full path
                log_path = os.path.join(LOG_FOLDER, filename)
                if not os.path.exists(log_path):
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Log file not found: '{filename}'.{COLOR_RESET}")
                    continue
                
                # Connect to the database
                db_path = BASE_DIR / "logs.db"
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get current tags
                cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (filename,))
                result = cursor.fetchone()
                
                if result and result[0] and "favorite:" in result[0]:
                    # Remove the favorite tag
                    tags = result[0].split(", ")
                    new_tags = [tag for tag in tags if not tag.startswith("favorite:")]
                    
                    if new_tags:
                        updated_tags = ", ".join(new_tags)
                    else:
                        updated_tags = None
                    
                    # Update the database
                    cursor.execute("UPDATE log_descriptions SET tags = ? WHERE filename = ?", (updated_tags, filename))
                    conn.commit()
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Removed favorite mark from log: '{filename}'.{COLOR_RESET}")
                else:
                    print(f"{COLOR_CYAN}Gemini:{COLOR_RESET} {COLOR_WHITE}Log was not marked as favorite: '{filename}'.{COLOR_RESET}")
                
                conn.close()
                continue

            if prompt_text.lower().startswith("view log "):
                target = prompt_text[9:].strip()
                view_log(target)
                continue

            # Regular case (no special command)
            is_search = False  # By default, no search
            if current_search_method == SearchMethod.CUSTOM and prompt_text.lower().startswith("search "):
                is_search = True

            ask_gemini_with_search(prompt_text, force_search=is_search, search_method=current_search_method)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
