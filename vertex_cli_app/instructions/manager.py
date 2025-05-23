"""
System Instructions module for the Vertex AI CLI application.
This module provides functionality to create, save, list, apply, edit, 
and clear system instruction profiles that shape AI behavior.
"""

import json
import os
import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Any

# Removed colorama imports as direct console output with colors is minimized here.
# CLI/UI layer will handle presentation.

class InstructionManager:
    """
    Manages system instruction profiles stored as JSON files.
    Interacts with a database manager for tagging logs with active instructions.
    """

    def __init__(self, instruction_folder_path: Path, db_manager: Optional[Any] = None):
        """
        Initializes the InstructionManager.

        Args:
            instruction_folder_path: Path to the directory where instruction profiles are stored.
            db_manager: Optional database manager instance for log tagging.
        """
        self.instruction_folder = instruction_folder_path
        self.instruction_folder.mkdir(parents=True, exist_ok=True)
        self.db_manager = db_manager
        
        self.active_instruction_name: Optional[str] = None
        self.active_instruction_text: Optional[str] = None
        print(f"InstructionManager initialized. Profile folder: {self.instruction_folder.resolve()}")
        if self.db_manager:
            print("Database manager is configured.")
        else:
            print("Database manager is NOT configured. Log tagging for instructions will be skipped.")

    
    def save_instruction_profile(self, name: str, instruction_text: str, description: str = "") -> Tuple[bool, str]:
        """
        Save an instruction profile with the given name, text, and description.
        Description generation is removed; it should be user-provided.

        Args:
            name: The name of the instruction profile (used as filename).
            instruction_text: The content of the instruction.
            description: A user-provided description for the profile.

        Returns:
            A tuple (success: bool, message: str).
        """
        if not name or not name.strip():
            return False, "Instruction profile name cannot be empty."
        if not instruction_text or not instruction_text.strip():
            return False, "Instruction text cannot be empty."
        if description is None: # Ensure description is at least an empty string
            description = ""

        file_path = self.instruction_folder / f"{name}.json"
        instruction_data = {
            "instruction": instruction_text,
            "description": description, # User-provided or empty
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(instruction_data, f, indent=2)
            return True, f"Instruction profile '{name}' saved successfully."
        except IOError as e:
            return False, f"Failed to save instruction profile '{name}': {e}"
    
    def list_instruction_profiles(self) -> List[Dict[str, str]]:
        """
        List all saved instruction profiles.
        
        Returns:
            List of dictionaries containing profile info, sorted by creation date (oldest first).
        """
        instructions = []
        if not self.instruction_folder.exists() or not self.instruction_folder.is_dir():
            print(f"Instruction folder not found: {self.instruction_folder}")
            return []

        for file_name in os.listdir(self.instruction_folder):
            if file_name.endswith(".json"):
                file_path = self.instruction_folder / file_name
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        instructions.append({
                            "name": file_name[:-5],  # Remove .json extension
                            "description": data.get("description", "No description"),
                            "created": data.get("created", "Unknown"),
                            "last_used": data.get("last_used", "Never") # Retain for now, may be updated by set_active_instruction
                        })
                except Exception as e:
                    print(f"Error loading instruction file '{file_name}': {e}")

        try:
            instructions.sort(
                key=lambda x: datetime.datetime.strptime(x["created"], "%Y-%m-%d %H:%M:%S") if x["created"] != "Unknown" else datetime.datetime.min
            )
        except (ValueError, KeyError) as e:
            print(f"Warning: Error sorting instructions by date: {e}")

        return instructions

    def load_instruction_profile(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Load an instruction profile by name.

        Args:
            name: Name of the profile to load.

        Returns:
            Tuple of (instruction_text, description) or (None, None) if not found.
        """
        file_path = self.instruction_folder / f"{name}.json"
        if not file_path.exists():
            return None, None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Note: Updating "last_used" timestamp is now handled by set_active_instruction
            return data.get("instruction"), data.get("description", "")
        except Exception as e:
            print(f"Error loading instruction profile '{name}': {e}")
            return None, None

    def edit_instruction_profile(self, name: str, new_instruction: Optional[str] = None, 
                                new_description: Optional[str] = None) -> Tuple[bool, str]:
        """
        Edit an existing instruction profile.
        
        Args:
            name: Name of the profile to edit.
            new_instruction: New instruction text (or None to keep current).
            new_description: New description (or None to keep current, or provide empty string to clear).
            
        Returns:
            Tuple of (success, message).
        """
        file_path = self.instruction_folder / f"{name}.json"
        try:
            if not file_path.exists():
                return False, f"Instruction profile '{name}' not found."
                
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if new_instruction is not None:
                data["instruction"] = new_instruction
                
            if new_description is not None: # Allows setting description to empty string
                data["description"] = new_description
                
            data["modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            return True, f"Instruction profile '{name}' updated."
        except Exception as e:
            return False, f"Error editing instruction profile '{name}': {e}"

    def set_active_instruction(self, name: str, log_filename_str: Optional[str] = None) -> Tuple[bool, str]:
        """
        Sets the active system instruction by loading it from a profile.
        Optionally tags the current log file with this instruction.

        Args:
            name: The name of the instruction profile to load and set as active.
            log_filename_str: Optional. The filename of the current log to tag.

        Returns:
            Tuple of (success: bool, message: str).
        """
        instruction_text, _ = self.load_instruction_profile(name)
        if instruction_text is None:
            return False, f"Instruction profile '{name}' not found."

        self.active_instruction_name = name
        self.active_instruction_text = instruction_text
        
        # Update last_used timestamp in the instruction file
        try:
            file_path = self.instruction_folder / f"{name}.json"
            if file_path.exists():
                with open(file_path, "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    data["last_used"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.seek(0)
                    json.dump(data, f, indent=2)
                    f.truncate()
        except Exception as e:
            print(f"Warning: Failed to update last_used timestamp for '{name}': {e}")

        # Database tagging
        if self.db_manager and log_filename_str:
            try:
                # Assuming db_manager has a method like update_log_tags
                self.db_manager.update_log_tags(log_filename_str, "instruction", name)
                print(f"Tagged log '{log_filename_str}' with instruction '{name}'.")
            except Exception as e:
                # TODO: Define specific exceptions or logging for db_manager interactions
                print(f"Error tagging log '{log_filename_str}' with instruction '{name}': {e}")
        elif self.db_manager and not log_filename_str:
             print(f"Instruction '{name}' set active. No log file provided for tagging.")
        elif not self.db_manager and log_filename_str:
             print(f"Instruction '{name}' set active. DB manager not available for tagging log '{log_filename_str}'.")
        
        return True, f"Instruction profile '{name}' is now active."

    def clear_active_instruction(self) -> str:
        """
        Clears the active instruction profile.
        """
        self.active_instruction_name = None
        self.active_instruction_text = None
        return "Active system instruction cleared."
    
    def get_active_instruction(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the currently active instruction text and name.
        
        Returns:
            Tuple of (active_instruction_text, active_instruction_name) or (None, None).
        """
        return self.active_instruction_text, self.active_instruction_name

    def delete_instruction_profile(self, name: str) -> Tuple[bool, str]:
        """
        Delete an instruction profile by name.
        If the deleted instruction was active, it clears the active instruction.
        """
        file_path = self.instruction_folder / f"{name}.json"

        if not file_path.exists():
            return False, f"Instruction profile '{name}' not found."

        is_active = (self.active_instruction_name == name)

        try:
            file_path.unlink() # Deletes the file
            message = f"Instruction profile '{name}' deleted."
            if is_active:
                self.clear_active_instruction()
                message += " It was active, so instruction has been cleared."
            return True, message
        except Exception as e:
            return False, f"Error deleting instruction profile '{name}': {e}"

    def get_instruction_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific instruction by its 1-based display index.
        The display index is typically newest first (highest index for oldest item
        if list_instruction_profiles returns oldest first and UI reverses it).
        UIRenderer.display_instructions reverses the list from list_instruction_profiles.
        So, if list_instruction_profiles gives [oldest, middle, newest], UI displays:
        1. newest
        2. middle
        3. oldest
        This method needs to map this display index back to the original list.
        Display index 1 (newest) = original_list[len-1]
        Display index N (oldest) = original_list[0]
        So, original_list_index = len(original_list) - display_index
        """
        all_instructions = self.list_instruction_profiles() # This returns oldest first
        if not all_instructions:
            return None
        
        num_items = len(all_instructions)
        if 1 <= index <= num_items:
            # Convert display index (1-based, newest first) to list index (0-based, oldest first)
            actual_idx = num_items - index 
            return all_instructions[actual_idx]
        return None

# Removed _convert_history_to_sdk_format as it's not needed here anymore.
# Removed global update_log_tags and generate_ai_role_description.
# These functionalities are either moved to db_manager or removed (AI description for roles).

if __name__ == "__main__":
    instr_dir = Path("./test_instructions")
    
    # Mock DB Manager for testing tagging
    class MockDBManager:
        def update_log_tags(self, log_filename_str, tag_key, tag_value):
            print(f"MockDB: Tagged {log_filename_str} with {tag_key}={tag_value}")

    mock_db = MockDBManager()
    manager = InstructionManager(instruction_folder_path=instr_dir, db_manager=mock_db)

    # Test save
    manager.save_instruction_profile("test_role_old", "Be an old helpful assistant.", "Oldest role.")
    # Add a small delay to ensure created times are different
    import time; time.sleep(0.01)
    manager.save_instruction_profile("test_role_mid", "Be a sarcastic pirate.", "A witty pirate role.")
    time.sleep(0.01)
    manager.save_instruction_profile("test_role_new", "Be a futuristic AI.", "Newest role.")
    print("Saved instructions.")

    # Test list (returns oldest first)
    profiles = manager.list_instruction_profiles()
    print("\nAvailable profiles (oldest first from list_instruction_profiles):")
    for i, p in enumerate(profiles):
        print(f"{i}. {p['name']} - {p['created']}")

    # Test get_instruction_by_index (assuming UI displays newest as index 1)
    # UI would display: 1. test_role_new, 2. test_role_mid, 3. test_role_old
    print("\n--- Test: Get Instruction by Index (UI perspective) ---")
    instr_idx_1 = manager.get_instruction_by_index(1) # Should be newest: test_role_new
    print(f"Instruction at UI index 1: {instr_idx_1['name'] if instr_idx_1 else 'Not found'}")
    assert instr_idx_1 and instr_idx_1["name"] == "test_role_new"

    instr_idx_3 = manager.get_instruction_by_index(3) # Should be oldest: test_role_old
    print(f"Instruction at UI index 3: {instr_idx_3['name'] if instr_idx_3 else 'Not found'}")
    assert instr_idx_3 and instr_idx_3["name"] == "test_role_old"

    instr_idx_invalid = manager.get_instruction_by_index(99)
    assert instr_idx_invalid is None
    print(f"Instruction at UI index 99: {'Not found' if instr_idx_invalid is None else 'Found unexpectedly'}")


    # Test load
    text, desc = manager.load_instruction_profile("test_role_mid")
    print(f"\nLoaded test_role_mid: '{text}' (Desc: '{desc}')")

    # Test set_active_instruction
    success, msg = manager.set_active_instruction("test_role_new", "dummy_log_file.txt")
    print(f"Set active: {success} - {msg}")
    active_text, active_name = manager.get_active_instruction()
    print(f"Active instruction: '{active_name}' - '{active_text}'")

    # Test clear
    clear_msg = manager.clear_active_instruction()
    print(f"\n{clear_msg}")
    active_text, active_name = manager.get_active_instruction()
    assert active_text is None, f"Active text should be None, got {active_text}"
    assert active_name is None, f"Active name should be None, got {active_name}"
    print("Cleared active instruction confirmed.")

    # Test delete
    del_success, del_msg = manager.delete_instruction_profile("test_role_mid")
    print(f"\nDelete test_role_mid: {del_success} - {del_msg}")
    profiles_after_del = manager.list_instruction_profiles()
    assert len(profiles_after_del) == 2
    found_deleted = any(p['name'] == 'test_role_mid' for p in profiles_after_del)
    assert not found_deleted
    print("Remaining profiles count:", len(profiles_after_del))


    # Clean up
    import shutil # Moved import here as it's only for test cleanup
    if instr_dir.exists():
        shutil.rmtree(instr_dir)
        print(f"\nCleaned up test directory: {instr_dir}")
