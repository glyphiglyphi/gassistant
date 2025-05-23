import datetime
import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Union # Added Union for type hint
from vertexai.generative_models import Content, Part # Added Content, Part

class ConversationManager:
    """
    Manages conversation history, logging, and loading of conversations.
    """

    def __init__(self, log_folder_path: Path):
        """
        Initializes the ConversationManager.

        Args:
            log_folder_path: Path to the directory where conversation logs will be stored.
        """
        self.log_folder: Path = log_folder_path
        self.log_folder.mkdir(exist_ok=True)
        
        self.current_log_filename: Optional[Path] = None
        self.history: List[str] = []  # Stores raw string history: "You: ...", "AI: ...", "Note: ..."
        
        self.db_manager = None  # TODO: Integrate a database manager for log metadata.
        print(f"ConversationManager initialized. Log folder: {self.log_folder.resolve()}")

    def _generate_log_filename(self, prefix: str = "") -> Path:
        """
        Generate a new filename based on the current date and time.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if prefix:
            return self.log_folder / f"{timestamp}_{prefix}.txt"
        return self.log_folder / f"{timestamp}.txt"

    def append_to_log(self, text: str):
        """
        Append text to the current log file.
        If no log file is active, a new one is created.
        """
        if self.current_log_filename is None:
            self.current_log_filename = self._generate_log_filename()
            print(f"No active log file. New log started: {self.current_log_filename}")
        
        try:
            with open(self.current_log_filename, "a", encoding="utf-8") as file:
                file.write(text + "\n")
        except Exception as e:
            print(f"Error appending to log file {self.current_log_filename}: {e}")
        
    def get_latest_log_file(self) -> Optional[Path]:
        """
        Retrieve the most recent log file from the log_folder.
        """
        try:
            files = [f for f in os.listdir(self.log_folder) if f.endswith(".txt")]
            if not files:
                return None
            files.sort(key=lambda f: os.path.getctime(self.log_folder / f), reverse=True)
            return self.log_folder / files[0]
        except Exception as e:
            print(f"Error getting latest log file: {e}")
            return None

    def load_history_from_file(self, file_path: Path) -> bool:
        """
        Load conversation history from a specified log file.
        Populates self.history and sets self.current_log_filename.
        """
        if not file_path.exists():
            print(f"Error: Log file not found: {file_path}")
            return False
        
        loaded_history: List[str] = []
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            
            raw_turns = re.split(r'(You: )', content)
            if raw_turns[0].strip(): 
                loaded_history.extend(line.strip() for line in raw_turns[0].strip().split('\n') if line.strip())

            for i in range(1, len(raw_turns), 2): 
                user_marker = raw_turns[i]
                turn_content = raw_turns[i+1]
                parts = turn_content.split('\n', 1)
                user_message = user_marker + parts[0].strip()
                loaded_history.append(user_message)
                
                if len(parts) > 1 and parts[1].strip():
                    ai_response_lines = parts[1].strip().split('\n')
                    for line in ai_response_lines:
                        if line.strip():
                            loaded_history.append(line.strip())
            
            self.history = loaded_history
            self.current_log_filename = file_path
            print(f"Conversation history loaded from '{file_path}'. {len(self.history)} entries.")
            return True
        except Exception as e:
            print(f"Error loading log file '{file_path}': {e}")
            self.history = []
            return False

    def start_new_conversation(self, session_name_prefix: Optional[str] = None):
        """
        Starts a new conversation, clearing current history and setting a new log file.
        """
        self.history = []
        prefix = session_name_prefix if session_name_prefix else ""
        self.current_log_filename = self._generate_log_filename(prefix=prefix)
        initial_note = f"Note: New conversation started on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
        self.history.append(initial_note) # Add to history first
        
        try: 
            with open(self.current_log_filename, "w", encoding="utf-8") as f:
                f.write(initial_note + "\n") # Then log it
            print(f"Starting new conversation. Logging to: {self.current_log_filename}")
        except Exception as e:
            print(f"Error creating new log file {self.current_log_filename}: {e}")

    def add_user_message(self, message: str):
        """
        Adds a user message to the history and logs it.
        """
        formatted_message = f"You: {message}"
        self.history.append(formatted_message)
        self.append_to_log(formatted_message)

    def add_ai_message(self, message: str):
        """
        Adds an AI message to the history and logs it.
        The message is expected to be the raw text from the AI.
        """
        # We need to decide if we prefix AI messages with "AI: " or similar in the log/history.
        # For parsing in get_history_for_model, it's easier if it's not prefixed there,
        # but for human readability of logs, a prefix might be good.
        # Let's assume for now 'message' is the raw AI response.
        # The get_history_for_model will determine roles based on "You: " prefix.
        self.history.append(message) 
        self.append_to_log(message)

    def add_system_note(self, note: str, log_immediately: bool = True):
        """
        Adds a system note to the history and logs it.
        """
        formatted_note = f"Note: {note}"
        self.history.append(formatted_note)
        if log_immediately:
            self.append_to_log(formatted_note)

    def get_history_for_model(self) -> List[Content]:
        """
        Converts self.history (list of strings) into a list of Content objects
        suitable for Vertex AI GenerativeModel.
        """
        model_history: List[Content] = []
        current_role: Optional[str] = None
        current_parts: List[Part] = []

        for line in self.history:
            line_strip = line.strip()
            if not line_strip or line_strip.startswith("Note:"):
                continue

            if line_strip.startswith("You: "):
                if current_role and current_parts: # Finalize previous entry
                    model_history.append(Content(role=current_role, parts=current_parts))
                current_role = "user"
                current_parts = [Part.from_text(line_strip[4:].strip())]
            elif current_role == "user": # This line must be from the model
                if current_parts: # Finalize user message
                    model_history.append(Content(role=current_role, parts=current_parts))
                current_role = "model"
                current_parts = [Part.from_text(line_strip)] # Start of model message
            elif current_role == "model": # Continuing a model message
                # Append to the last part's text if it exists, or add new part
                # For simplicity, let's assume multi-line AI responses are single Part for now.
                # The previous logic for self.history.append(message) for AI would store multiline as one entry.
                # If AI messages were broken into multiple history entries, this needs adjustment.
                # Given add_ai_message appends the whole message, this part might be simpler.
                # Let's assume one line in history is one part for model, unless it's a continuation.
                # This parsing logic needs to be robust against how AI messages are added.
                # If add_ai_message adds a single string (possibly with newlines),
                # then a model turn will always be one Content object with one Part.
                current_parts.append(Part.from_text(line_strip)) # This would create many parts for a multi-line AI response
                                                              # if AI response was split into lines in self.history
            # else: # Should not happen if history starts with "You:" or "Note:"
                # print(f"Warning: Unexpected line in history: {line_strip}")
        
        # Add the last pending message
        if current_role and current_parts:
            model_history.append(Content(role=current_role, parts=current_parts))
        
        # Refined logic assuming add_ai_message adds the full response as one string:
        model_history_refined: List[Content] = []
        user_message_text: Optional[str] = None

        for line_entry in self.history:
            line_strip = line_entry.strip()
            if not line_strip or line_strip.startswith("Note:"):
                continue

            if line_strip.startswith("You: "):
                if user_message_text is not None: # We had a user message, but no model response followed before next user msg
                    model_history_refined.append(Content(role="user", parts=[Part.from_text(user_message_text)]))
                    # This case (user -> user) might indicate an issue or need specific handling.
                user_message_text = line_strip[4:].strip()
            else: # This is an AI model response line
                if user_message_text is not None: # We must have a user message to respond to
                    model_history_refined.append(Content(role="user", parts=[Part.from_text(user_message_text)]))
                    model_history_refined.append(Content(role="model", parts=[Part.from_text(line_strip)]))
                    user_message_text = None # Reset, ready for next "You:"
                # else: an AI message without a preceding user message (after filtering notes) - usually an error or implies history starts with AI.
                    # For now, we assume conversations start with a user message or a note.

        # If the last message was from the user and there's no AI response yet
        if user_message_text is not None:
            model_history_refined.append(Content(role="user", parts=[Part.from_text(user_message_text)]))
            
        return model_history_refined

if __name__ == "__main__":
    log_dir = Path("./test_logs_conversation_manager") # Unique name for this test
    manager = ConversationManager(log_folder_path=log_dir)

    # Test starting a new conversation
    print("\n--- Test: Starting New Conversation ---")
    manager.start_new_conversation("test_session")
    print(f"Current log file: {manager.current_log_filename}")
    initial_history_len = len(manager.history)
    print(f"History length after start: {initial_history_len}") # Should be 1 (initial note)

    # Test adding messages
    print("\n--- Test: Adding Messages ---")
    manager.add_user_message("Hello from user")
    manager.add_ai_message("Hello from AI, this is my response.")
    manager.add_system_note("This is a test note after some messages.")

    print("\nConversation History (in-memory):")
    for entry in manager.history:
        print(entry)
    
    # Verify content of the log file (manual check or by reading it back)
    if manager.current_log_filename and manager.current_log_filename.exists():
        print(f"\nContent of log file '{manager.current_log_filename}':")
        with open(manager.current_log_filename, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print(f"\nLog file '{manager.current_log_filename}' not found or not created.")


    # Test loading the latest log
    print("\n--- Test: Loading Latest Log ---")
    latest_log = manager.get_latest_log_file()
    if latest_log:
        print(f"Latest log file found: {latest_log}")
        new_manager = ConversationManager(log_folder_path=log_dir)
        success = new_manager.load_history_from_file(latest_log)
        if success:
            print(f"\nSuccessfully loaded history from {latest_log}:")
            # Compare lengths first
            print(f"Original manager history length: {len(manager.history)}")
            print(f"New manager history length: {len(new_manager.history)}")
            
            if len(manager.history) == len(new_manager.history):
                print("History lengths match.")
            else:
                print("Error: History lengths DO NOT match after loading.")

            # Print a few entries for manual comparison if needed
            print("\nFirst few entries of loaded history:")
            for i, entry in enumerate(new_manager.history):
                if i < 5: print(entry)
            
            # Test converting history for model
            print("\n--- Test: Converting History for Model ---")
            model_history = new_manager.get_history_for_model()
            print("\nHistory for model (JSON format):")
            # Import json here as it's only for testing
            import json
            print(json.dumps(model_history, indent=2))

            # Check a specific conversion
            expected_user_message = "Hello from user"
            expected_ai_message = "Hello from AI, this is my response."
            found_user = any(turn.get("role") == "user" and turn["parts"][0]["text"] == expected_user_message for turn in model_history)
            found_ai = any(turn.get("role") == "model" and turn["parts"][0]["text"] == expected_ai_message for turn in model_history)

            if found_user:
                print(f"User message '{expected_user_message}' correctly converted.")
            else:
                print(f"Error: User message '{expected_user_message}' NOT found or incorrect in model history.")
            
            if found_ai:
                print(f"AI message '{expected_ai_message}' correctly converted.")
            else:
                print(f"Error: AI message '{expected_ai_message}' NOT found or incorrect in model history.")

        else:
            print(f"Failed to load history from {latest_log}")
    else:
        print("\nNo log files found to test loading.")
    
    print("\n--- Test: Starting another new conversation to check log naming ---")
    manager.start_new_conversation("another_session")
    print(f"Current log file after second new conversation: {manager.current_log_filename}")
    print(f"History length after 2nd start: {len(manager.history)}")


    print("\n--- ConversationManager Test Complete ---")
