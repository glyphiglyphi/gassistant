import sqlite3
import datetime
import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any

class LogDatabase:
    """
    Manages the SQLite database for conversation log metadata.
    """

    def __init__(self, db_path: Path):
        """
        Initializes the LogDatabase.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        
        if not self.db_path.exists():
            print(f"Database not found at {self.db_path}, initializing.")
            self._initialize_database()
        else:
            print(f"Using existing database at {self.db_path}")

    def _initialize_database(self):
        """
        Creates the log_descriptions table if it doesn't exist.
        (Migrated from setup_database in gemini_cli_v8.py)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
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
            print(f"Database initialized/verified successfully at {self.db_path}")
        except sqlite3.Error as e:
            print(f"Error initializing database at {self.db_path}: {e}")
            raise # Re-raise after logging if initialization is critical

    def _generate_ai_description_for_log_content(
        self, 
        ai_handler: Any, 
        log_content: str, 
        first_prompt: str, 
        active_instruction_name: Optional[str] = None
    ) -> str:
        """
        Generates a concise description for log content.
        Placeholder implementation.
        (Adapted from generate_ai_description in gemini_cli_v8.py)

        Args:
            ai_handler: An AI handler instance (currently unused, for future AI integration).
            log_content: The full content of the log.
            first_prompt: The first user prompt in the log.
            active_instruction_name: Name of any active AI instruction/role.

        Returns:
            A short description (currently derived from the first prompt).
        """
        # TODO: Integrate with VertexAIHandler.generate_content_for_text_summary
        # For now, using placeholder logic:
        if first_prompt:
            desc = first_prompt[:50] + ("..." if len(first_prompt) > 50 else "")
            print(f"Generated placeholder description: {desc}")
            return desc
        print("Could not generate placeholder description (no first prompt).")
        return "Log summary placeholder"

    def update_log_entry(
        self, 
        log_filename_str: str, 
        conversation_history_lines: List[str], 
        instruction_manager: Any,  # For active instruction
        ai_handler: Any            # For generating description
    ):
        """
        Updates or inserts a log entry in the database with its description and metadata.
        (Adapted from update_log_description in gemini_cli_v8.py)

        Args:
            log_filename_str: The filename of the log (e.g., "timestamp_session.txt").
            conversation_history_lines: List of strings representing the conversation.
            instruction_manager: Instance of InstructionManager to get active instructions.
            ai_handler: Instance of AIHandler for description generation.
        """
        first_prompt: Optional[str] = None
        for line in conversation_history_lines:
            if line.startswith("You: "):
                first_prompt = line[4:].strip()
                break
        
        log_content_for_summary = "\n".join(conversation_history_lines)
        active_instruction, active_instruction_name = None, None
        if instruction_manager: # instruction_manager could be None
            try:
                active_instruction, active_instruction_name = instruction_manager.get_active_instruction()
            except Exception as e:
                print(f"Warning: Could not get active instruction: {e}")
        
        description = self._generate_ai_description_for_log_content(
            ai_handler, log_content_for_summary, first_prompt or "", active_instruction_name
        )

        created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Assuming new entry or update now
        # For existing files, created_date might be different, this simplifies for now.
        # If log_filename_str implies a timestamp, that could be parsed for a more accurate created_date.
        
        try:
            log_file_path_obj = Path(log_filename_str) # Assuming log_filename_str could be a full path or just filename
            actual_filename = log_file_path_obj.name # Use only the filename part as primary key

            # Try to get actual file creation time if it's a real file
            # This assumes log_filename_str is a path that might exist
            # For the test case, it's just a string, so os.path.getctime would fail if not careful.
            # We need to know the log_root_folder to make this robust.
            # For now, we'll use current time, or rely on it being updated later if file exists.

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Preserve existing tags if any
                cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (actual_filename,))
                result = cursor.fetchone()
                existing_tags = result[0] if result and result[0] else None

                cursor.execute('''
                INSERT OR REPLACE INTO log_descriptions
                (filename, description, first_prompt, created_date, last_accessed, description_updated, tags)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ''', (actual_filename, description, first_prompt, created_date, created_date, existing_tags))
                conn.commit()
            print(f"Log entry '{actual_filename}' updated/inserted.")
        except sqlite3.Error as e:
            print(f"Error updating log entry for '{log_filename_str}': {e}")


    def update_description_for_existing_log(self, log_file_path: Path, ai_handler: Any):
        """
        Generates and updates the description for an existing log file.
        (Adapted from generate_description_for_log in gemini_cli_v8.py)

        Args:
            log_file_path: Path to the log file.
            ai_handler: Instance of AIHandler for description generation.
        """
        if not log_file_path.exists():
            print(f"Log file '{log_file_path}' not found.")
            return

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            first_prompt: Optional[str] = None
            # Basic extraction of first "You: " line
            match = re.search(r"You: (.*)", content)
            if match:
                first_prompt = match.group(1).strip()
            
            if not first_prompt:
                print(f"Could not extract first prompt from log '{log_file_path.name}'. Using file content for summary.")
                # Fallback: use start of content if no "You:" found
                first_prompt = content[:100] 

            description = self._generate_ai_description_for_log_content(ai_handler, content, first_prompt or "")
            
            actual_filename = log_file_path.name
            created_date = datetime.datetime.fromtimestamp(os.path.getctime(log_file_path)).strftime("%Y-%m-%d %H:%M:%S")
            last_accessed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                 # Preserve existing tags if any
                cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (actual_filename,))
                result = cursor.fetchone()
                existing_tags = result[0] if result and result[0] else None

                cursor.execute('''
                INSERT OR REPLACE INTO log_descriptions
                (filename, description, first_prompt, created_date, last_accessed, description_updated, tags)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ''', (actual_filename, description, first_prompt, created_date, last_accessed, existing_tags))
                conn.commit()
            print(f"Description for '{actual_filename}' updated in database.")
        except Exception as e:
            print(f"Error generating/updating description for '{log_file_path.name}': {e}")

    def get_all_log_entries(self, log_root_folder: Path) -> List[Dict[str, Any]]:
        """
        Lists all log files from the filesystem and enriches them with data from the database.
        (Adapted from list_logs in gemini_cli_v8.py)

        Args:
            log_root_folder: Path to the root folder containing .txt log files.

        Returns:
            A list of dictionaries, each representing a log entry.
        """
        db_entries: Dict[str, Dict[str, Any]] = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT filename, description, created_date, tags FROM log_descriptions")
                for row in cursor.fetchall():
                    db_entries[row[0]] = {"description": row[1], "db_created_date": row[2], "tags": row[3]}
        except sqlite3.Error as e:
            print(f"Error fetching log entries from database: {e}")

        all_log_infos: List[Dict[str, Any]] = []
        if not log_root_folder.exists() or not log_root_folder.is_dir():
            print(f"Log root folder not found or not a directory: {log_root_folder}")
            return []

        for file_path_obj in log_root_folder.glob("*.txt"):
            filename = file_path_obj.name
            file_stat = file_path_obj.stat()
            
            entry_info = {
                "filename": filename,
                "size_kb": file_stat.st_size / 1024,
                "filesystem_created_date": datetime.datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                "filesystem_modified_date": datetime.datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "description": "N/A",
                "tags": ""
            }
            
            db_data = db_entries.get(filename)
            if db_data:
                entry_info["description"] = db_data.get("description", "N/A")
                entry_info["tags"] = db_data.get("tags", "")
                # Optionally, use db_created_date if it's considered more authoritative
                # entry_info["authoritative_created_date"] = db_data.get("db_created_date")
            
            all_log_infos.append(entry_info)

        # Sort by filesystem_created_date (newest first for display, typical)
        all_log_infos.sort(key=lambda x: x["filesystem_created_date"], reverse=True)
        return all_log_infos

    def update_log_tags(self, log_filename_str: str, tag_key: str, tag_value: str):
        """
        Updates or adds a tag for a specific log file in the database.
        Tags are stored as a comma-separated string like "key1:value1, key2:value2".

        Args:
            log_filename_str: The filename of the log (e.g., "timestamp_session.txt").
            tag_key: The key of the tag (e.g., "status", "favorite").
            tag_value: The value of the tag.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                actual_filename = Path(log_filename_str).name # Ensure we use only filename as key
                
                cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (actual_filename,))
                result = cursor.fetchone()
                
                current_tags_str = result[0] if result and result[0] else ""
                tags_dict: Dict[str, str] = {}
                if current_tags_str:
                    for tag_pair in current_tags_str.split(","):
                        if ":" in tag_pair:
                            key, val = tag_pair.split(":", 1)
                            tags_dict[key.strip()] = val.strip()
                
                tags_dict[tag_key.strip()] = tag_value.strip()
                
                new_tags_list = [f"{k}:{v}" for k, v in tags_dict.items()]
                new_tags_str = ", ".join(new_tags_list)
                
                cursor.execute("UPDATE log_descriptions SET tags = ? WHERE filename = ?", (new_tags_str, actual_filename))
                
                # If no row was updated (e.g., file not in DB yet), we might need to insert.
                # For simplicity, this assumes an entry exists if tags are being updated.
                # A more robust version might UPSERT the basic file info if missing.
                if cursor.rowcount == 0:
                    print(f"Warning: No existing entry found for '{actual_filename}' to update tags. Creating one.")
                    # Minimal insert; other fields would ideally be populated by update_log_entry first.
                    now_str =  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute('''
                    INSERT INTO log_descriptions (filename, tags, created_date, last_accessed) 
                    VALUES (?, ?, ?, ?)
                    ''', (actual_filename, new_tags_str, now_str, now_str))

                conn.commit()
                print(f"Tags for '{actual_filename}' updated to: {new_tags_str}")
        except sqlite3.Error as e:
            print(f"Error updating tags for '{log_filename_str}': {e}")

    def archive_and_reset_database(self, log_root_folder: Path, archive_root_folder: Path):
        """
        Archives existing log files and then resets (re-initializes) the database.
        (Adapted from reset_log_database in gemini_cli_v8.py)

        Args:
            log_root_folder: The folder where current .txt logs are stored.
            archive_root_folder: The folder where logs will be moved.
        """
        archive_root_folder.mkdir(parents=True, exist_ok=True)
        moved_count = 0
        if log_root_folder.exists() and log_root_folder.is_dir():
            for log_file in log_root_folder.glob("*.txt"):
                try:
                    shutil.move(str(log_file), str(archive_root_folder / log_file.name))
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving log file {log_file.name} to archive: {e}")
            print(f"Moved {moved_count} log files from {log_root_folder} to {archive_root_folder}.")
        else:
            print(f"Log root folder {log_root_folder} not found. No logs to archive.")

        if self.db_path.exists():
            try:
                self.db_path.unlink() # Deletes the database file
                print(f"Removed old database file: {self.db_path}")
            except Exception as e:
                print(f"Error removing database file {self.db_path}: {e}")
        
        self._initialize_database()
        print("Database has been reset and re-initialized.")

    def get_log_by_index(self, index: int, log_root_folder: Path) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific log entry by its 1-based display index.
        The index corresponds to the order in get_all_log_entries (newest first).
        """
        all_logs = self.get_all_log_entries(log_root_folder)
        if 1 <= index <= len(all_logs):
            # get_all_log_entries returns newest first, so index 1 is all_logs[0]
            return all_logs[index - 1]
        return None

    def edit_log_description(self, filename_str: str, new_description: str) -> bool:
        """
        Updates the description of a specific log file in the database.

        Args:
            filename_str: The filename of the log.
            new_description: The new description to set.

        Returns:
            True if update was successful, False otherwise.
        """
        actual_filename = Path(filename_str).name
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE log_descriptions
                    SET description = ?, description_updated = 1, last_accessed = ?
                    WHERE filename = ?
                """, (new_description, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actual_filename))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"Description for '{actual_filename}' updated successfully to '{new_description}'.")
                    return True
                else:
                    print(f"Log file '{actual_filename}' not found in database for description update.")
                    return False
        except sqlite3.Error as e:
            print(f"Error updating description for '{actual_filename}': {e}")
            return False


if __name__ == "__main__":
    test_db_path = Path("./test_logs.db")
    # Clean up previous test runs if any
    if test_db_path.exists():
        os.remove(test_db_path)
        
    test_log_folder = Path("./test_conversation_logs_db_manager") # Unique name
    if test_log_folder.exists():
        shutil.rmtree(test_log_folder)
    test_log_folder.mkdir(exist_ok=True, parents=True)
    
    # Create dummy log files
    log_file_1_path = test_log_folder / "2023-01-01_10-00-00_test1.txt"
    log_file_2_path = test_log_folder / "2023-01-02_11-00-00_test2.txt"
    log_file_3_path = test_log_folder / "2023-01-03_09-00-00_test0.txt" # older for sorting test
    log_file_1_path.write_text("You: Hello from test1\nAI: Hi from test1")
    log_file_2_path.write_text("You: Query from test2\nAI: Response from test2")
    log_file_3_path.write_text("You: Initial query test0\nAI: Initial response test0")


    db = LogDatabase(db_path=test_db_path)
    print(f"Database initialized at {db.db_path}")

    # Mock AI Handler for description generation
    class MockAIHandler:
        def generate_content_for_text_summary(self, log_content, first_prompt, instruction_name):
            return f"Mock AI desc: {first_prompt[:30]}"

    mock_ai = MockAIHandler()
    
    # Mock Instruction Manager
    class MockInstructionManager:
        def get_active_instruction(self): return None, None # No active instruction

    mock_im = MockInstructionManager()

    print("\n--- Test: update_description_for_existing_log ---")
    db.update_description_for_existing_log(log_file_1_path, mock_ai)
    db.update_description_for_existing_log(log_file_2_path, mock_ai)
    db.update_description_for_existing_log(log_file_3_path, mock_ai)
    
    print("\n--- Test: update_log_entry (for a new/active log concept) ---")
    new_log_filename = "2023-01-04_12-00-00_test_new.txt"
    db.update_log_entry(
        log_filename_str=new_log_filename, 
        conversation_history_lines=["You: New live chat query", "AI: New live response"],
        instruction_manager=mock_im,
        ai_handler=mock_ai
    )

    all_logs = db.get_all_log_entries(log_root_folder=test_log_folder)
    print("\nAll logs (from FS and DB, newest first):")
    for idx, log_entry in enumerate(all_logs):
        print(f"{idx+1}. {log_entry}")
    
    # Test get_log_by_index
    print("\n--- Test: get_log_by_index ---")
    # Assuming test_new.txt is newest, then test2.txt, then test1.txt, then test0.txt
    # get_all_log_entries sorts newest first.
    log_at_idx_1 = db.get_log_by_index(1, test_log_folder) # Should be the newest FS log (test2.txt or test1.txt if new_log_filename isn't in FS)
                                                          # The new_log_filename is DB only, get_all_log_entries only lists FS files.
                                                          # So this will be test2.txt
    log_at_idx_3 = db.get_log_by_index(3, test_log_folder) # Should be test0.txt
    
    print(f"Log at index 1: {log_at_idx_1['filename'] if log_at_idx_1 else 'Not found'}")
    assert log_at_idx_1 and "test2.txt" in log_at_idx_1["filename"] 
    print(f"Log at index 3: {log_at_idx_3['filename'] if log_at_idx_3 else 'Not found'}")
    assert log_at_idx_3 and "test0.txt" in log_at_idx_3["filename"]

    # Test edit_log_description
    print("\n--- Test: edit_log_description ---")
    db.edit_log_description(log_file_1_path.name, "Edited description for test1.")
    log_1_updated = db.get_log_by_index(2, test_log_folder) # test1.txt should be at index 2 now
    print(f"Log 1 updated: {log_1_updated}")
    assert log_1_updated and log_1_updated["description"] == "Edited description for test1."


    print("\n--- Test: update_log_tags ---")
    db.update_log_tags(log_file_1_path.name, "status", "reviewed")
    db.update_log_tags(log_file_1_path.name, "favorite", "yes")
    db.update_log_tags(new_log_filename, "project", "alpha") # Tag the DB-only entry
    
    all_logs_after_tags = db.get_all_log_entries(log_root_folder=test_log_folder)
    print("\nAll logs after tagging (from FS and DB):")
    for log_entry in all_logs_after_tags:
        print(log_entry)
        if log_entry["filename"] == log_file_1_path.name:
            assert "status:reviewed" in log_entry["tags"]
            assert "favorite:yes" in log_entry["tags"]
            
    print("\nVerifying tags for new_log_filename (DB-only) in DB (direct check):")
    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tags FROM log_descriptions WHERE filename = ?", (new_log_filename,))
            row = cursor.fetchone()
            if row:
                print(f"Tags for {new_log_filename} in DB: {row[0]}")
                assert "project:alpha" in row[0]
            else:
                print(f"{new_log_filename} not found for tag verification.")
    except sqlite3.Error as e:
        print(f"DB error checking tags for {new_log_filename}: {e}")
        
    print("\n--- LogDatabase Test Complete ---")
