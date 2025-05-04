"""
System Instructions module for Gemini CLI application.
This module provides functionality to create, save, list, apply, edit, 
and clear system instruction profiles that shape Gemini's behavior across conversations.
"""

import json
import os
import datetime
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Any
from colorama import init, Fore, Style as ColoramaStyle


# Colors for console output
COLOR_CYAN = "\033[96m"
COLOR_WHITE = "\033[97m"
COLOR_RESET = "\033[0m"

BASE_DIR = Path("/mnt/c/Users/Alex/gassistant")


# Configure logging
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def update_log_tags(log_file_path, tag_category, tag_value):
    """Update tags for a log file in the database."""
    import sqlite3

    # Extract just the filename from the path
    filename = os.path.basename(log_file_path)

    # Make sure the file exists before trying to tag it
    if not os.path.exists(log_file_path):
        print(f"{Fore.RED}Error updating tags: File not found: {log_file_path}{ColoramaStyle.RESET_ALL}")
        return False

    try:
        db_path = BASE_DIR / "logs.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if file already has tags
        cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (filename,))
        result = cursor.fetchone()

        new_tag = f"{tag_category}:{tag_value}"

        if result and result[0]:
            # Append to existing tags
            existing_tags = result[0]
            if new_tag not in existing_tags:
                updated_tags = f"{existing_tags}, {new_tag}"
            else:
                updated_tags = existing_tags  # Tag already exists
        else:
            updated_tags = new_tag

        # Update or insert the tag
        cursor.execute('''
        UPDATE log_descriptions 
        SET tags = ?
        WHERE filename = ?
        ''', (updated_tags, filename))

        # If no row was updated, we need to insert a new row
        if cursor.rowcount == 0:
            created_date = datetime.datetime.fromtimestamp(
                os.path.getctime(log_file_path)).strftime("%Y-%m-%d %H:%M:%S")
            last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
            INSERT OR REPLACE INTO log_descriptions
            (filename, tags, created_date, last_accessed)
            VALUES (?, ?, ?, ?)
            ''', (filename, updated_tags, created_date, last_accessed))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"{Fore.RED}Error updating tags: {e}{ColoramaStyle.RESET_ALL}")
        return False

def generate_ai_role_description(instruction_text):
    """Generate a concise description for a role based on its instruction text.
    
    Args:
        instruction_text: The system instruction text to generate a description for
        
    Returns:
        A short description summarizing the role
    """
    try:
        # Import the client for AI generation
        from google import genai
        from google.genai import types
        
        # Get API key from environment
        api_key = "AIzaSyDmx0ghR9fUFFLbiK-_q4_oyRt8a07wmVE"
        if not api_key:
            return "Custom system role"
        
        # Initialize the client
        client = genai.Client(api_key=api_key)
        
        # Clean up the instruction text for the prompt
        cleaned_text = instruction_text[:500]  # Use first 500 chars for brevity
        
        # Generate a description using a smaller model for efficiency
        generation_model = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"""Create a very brief (4-6 word) title/description that captures the essence of this AI system role:

System role: {cleaned_text}

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
        # Fall back to generic description on error
        print(f"Error generating role description: {e}")
        return "Custom system role"

class InstructionManager:


    def __init__(self, base_dir: Path):
        """Initialize the InstructionManager with the base directory."""
        self.instruction_folder = base_dir / "instructions"
        self.instruction_folder.mkdir(exist_ok=True)
        
        # Active instruction tracking
        self.active_instruction = None
        self.active_instruction_name = None
    
    def save_instruction_profile(self, name: str, instruction_text: str, description: str = "") -> tuple:
        """
        Save an instruction profile with the given name, text, and optional description.
        If no description is provided, one will be automatically generated.
        
        Returns a tuple (success: bool, message: str).
        """
        try:
            # Generate description if none was provided
            if not description:
                description = generate_ai_role_description(instruction_text)
                print(f"Auto-generated description for role '{name}': {description}")
            
            # Save the instruction to a file
            file_path = self.instruction_folder / f"{name}.json"
            instruction_data = {
                "instruction": instruction_text,
                "description": description,
                "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(instruction_data, f, indent=2)

            return True, f"Instruction profile '{name}' saved successfully."
        except Exception as e:
            return False, f"Failed to save instruction profile '{name}': {e}"
    
    def list_instruction_profiles(self) -> List[Dict[str, str]]:
        """List all saved instruction profiles.
        
        Returns:
            List of dictionaries containing profile info, sorted by creation date
        """
        instructions = []
        for file in os.listdir(self.instruction_folder):
            if file.endswith(".json"):
                try:
                    with open(os.path.join(self.instruction_folder, file), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        instructions.append({
                            "name": file[:-5],  # Remove .json extension
                            "description": data.get("description", "No description"),
                            "created": data.get("created", "Unknown"),
                            "last_used": data.get("last_used", "Never")
                        })
                except Exception as e:
                    print(f"Error loading instruction file '{file}': {e}")

        # Sort instructions by creation date (oldest first)
        try:
            instructions.sort(key=lambda x: datetime.datetime.strptime(x["created"], "%Y-%m-%d %H:%M:%S") if x["created"] != "Unknown" else datetime.datetime.min)
        except (ValueError, KeyError) as e:
            print(f"Warning: Error sorting instructions by date: {e}")

        return instructions

    def load_instruction_profile(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """Load an instruction profile by name.

        Args:
            name: Name of the profile to load

        Returns:
            Tuple of (instruction_text, description) or (None, None) if not found
        """
        file_path = self.instruction_folder / f"{name}.json"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Update last used timestamp
            data["last_used"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"Loaded instruction profile '{name}': {data.get('instruction', '')}")
            return data.get("instruction", ""), data.get("description", "")
        except Exception as e:
            print(f"Error loading instruction profile '{name}': {e}")
            return None, None

    def edit_instruction_profile(self, name: str, new_instruction: Optional[str] = None, 
                                new_description: Optional[str] = None) -> Tuple[bool, str]:
        """Edit an existing instruction profile.
        
        Args:
            name: Name of the profile to edit
            new_instruction: New instruction text (or None to keep current)
            new_description: New description (or None to keep current)
            
        Returns:
            Tuple of (success, message)
        """
        file_path = self.instruction_folder / f"{name}.json"
        try:
            if not os.path.exists(file_path):
                return False, f"Instruction profile '{name}' not found."
                
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if new_instruction is not None:
                data["instruction"] = new_instruction
                
            if new_description is not None:
                data["description"] = new_description
                
            data["modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            return True, f"Instruction profile '{name}' updated."
        except Exception as e:
            return False, f"Error editing instruction profile '{name}': {e}"

    def set_active_instruction(self, name: str, instruction_text: str) -> None:
        """Set the active system instruction for the current session.

        Args:
            name: The name of the instruction profile
            instruction_text: The actual instruction text
        """
        self.active_instruction = instruction_text
        self.active_instruction_name = name

        # Update the last_used timestamp in the instruction file
        try:
            if name:
                file_path = self.instruction_folder / f"{name}.json"
                if file_path.exists():
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    data["last_used"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to update last_used timestamp: {e}")

    def apply_instruction(self, instruction_text: str, name: str, chat, client, model_name,
                          conversation_history, search_method, log_filename=None) -> Tuple[bool, str, object]:

        """Apply a system instruction to the current session.

        Args:
            instruction_text: The system instruction text
            name: The name of the instruction profile
            chat: Current chat object
            client: Gemini API client
            model_name: Model name to use
            conversation_history: Current conversation history
            search_method: Current search method being used

        Returns:
            Tuple of (success, message, new_chat_object)
        """
        try:
            # Set the active instruction in the manager first
            self.set_active_instruction(name, instruction_text)

            # Add tagging when an instruction is applied
            if log_filename:
                update_log_tags(log_filename, "Role", name)

            # If using grounding mode, we don't need to create a persistent chat object
            if search_method and search_method.name == "GEMINI_GROUNDING":
                return True, "System instruction set for future grounding requests.", None

            # For standard chat mode, we need to create a new chat with the instruction
            sdk_history = self._convert_history_to_sdk_format(conversation_history)

            # Create chat first without system instruction
            new_chat = client.chats.create(model=model_name, history=sdk_history)

            # Then set system instruction on the chat object
            if hasattr(new_chat, "send_message") and hasattr(new_chat, "system_instruction"):
                # If the API has a direct system_instruction property
                new_chat.system_instruction = instruction_text
            else:
                # Try an alternate approach - send a hidden context message
                try:
                    new_chat.send_message(f"System instruction (not visible to user): {instruction_text}")
                except Exception as e:
                    return False, f"Failed to set system instruction: {e}", None

            return True, f"System instruction '{name}' applied successfully!", new_chat

        except Exception as e:
            return False, f"Error applying instruction: {e}", None

    def _convert_history_to_sdk_format(self, conversation_history: list) -> list:
        """Helper method to convert conversation history to SDK format."""
        sdk_history = []
        user_message = None
        model_response_parts = []

        try:
            for line in conversation_history:
                line_strip = line.strip()
                if not line_strip:
                    continue
                
                if line_strip.startswith("Note:"):
                    continue
                
                if line.startswith("You: "):
                    if user_message is not None and model_response_parts:
                        sdk_history.append({"role": "user", "parts": [{'text': user_message}]})
                        sdk_history.append({"role": "model", "parts": [{'text': "\n".join(model_response_parts)}]})
                    
                    user_message = line[4:].strip()
                    model_response_parts = []
                elif user_message is not None:
                    model_response_parts.append(line)
            
            # Add the last turn if it exists
            if user_message is not None and model_response_parts:
                sdk_history.append({"role": "user", "parts": [{'text': user_message}]})
                sdk_history.append({"role": "model", "parts": [{'text': "\n".join(model_response_parts)}]})
        except Exception as e:
            print(f"Error converting history to SDK format: {e}")
            # Return empty history on error
            return []
        
        return sdk_history
    
    def clear_instruction(self) -> Tuple[bool, str]:
        """Clear the active instruction profile."""
        self.active_instruction = None
        self.active_instruction_name = None
        return True, "Active system instruction cleared."
    
    def get_active_instruction(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the currently active instruction.
        
        Returns:
            Tuple of (instruction_text, instruction_name) or (None, None) if no active instruction
        """
        return self.active_instruction, self.active_instruction_name

    def delete_instruction_profile(self, name):
        """Delete an instruction profile by name."""
        file_path = self.instruction_folder / f"{name}.json"  # Use correct attribute name

        if not file_path.exists():
            return False, f"Instruction profile '{name}' not found."

        # Check if this is the active instruction
        active_instruction, active_name = self.get_active_instruction()
        is_active = (active_name == name)

        try:
            # Delete the file
            file_path.unlink()

            # Clear the active instruction if this was it
            if is_active:
                self.clear_instruction()
                return True, f"Instruction profile '{name}' deleted. It was active, so instruction has been cleared."

            return True, f"Instruction profile '{name}' deleted."
        except Exception as e:
            return False, f"Error deleting instruction profile: {e}"
