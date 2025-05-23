import argparse
from pathlib import Path
import os # For API keys etc.

from ai_core.handler import VertexAIHandler
from cli.parser import CLIParser
from conversation.manager import ConversationManager
from database.manager import LogDatabase
from instructions.manager import InstructionManager
from prompts.manager import PromptManager
from search.handler import SearchHandler
from ui.renderer import UIRenderer
from ui.command_help import COMMAND_HELP # For command validation
from utils import SearchMethod, get_formatted_datetime_info, is_simple_query 

class VertexCLIApplication:
    def __init__(self, args): # args from argparse
        # Configuration
        self.project_id = os.getenv("GCP_PROJECT_ID")
        if not self.project_id:
            print("Error: GCP_PROJECT_ID environment variable is not set.")
            print("Please set GCP_PROJECT_ID to your Google Cloud Project ID.")
            # Decide if to raise error or use a placeholder that will show warnings
            self.project_id = "your-gcp-project-id-placeholder" # Will trigger warning later

        self.location = os.getenv("GCP_LOCATION", "us-central1")
        
        self.google_search_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.google_search_cx = os.getenv("GOOGLE_SEARCH_CX")

        self.app_data_dir = Path.home() / ".vertex_cli_app_data"
        self.app_data_dir.mkdir(exist_ok=True)

        log_folder = self.app_data_dir / "logs"
        db_file_path = self.app_data_dir / "logs.db" # Ensure this matches LogDatabase's expectation
        prompt_folder = self.app_data_dir / "prompts"
        instruction_folder = self.app_data_dir / "instructions"
        
        # Initialize managers and handlers
        self.ui = UIRenderer()
        self.cli_parser = CLIParser()
        
        self.ai_handler = VertexAIHandler(project_id=self.project_id, location=self.location)
        self.search_handler = SearchHandler(
            google_search_api_key=self.google_search_api_key,
            google_search_cx=self.google_search_cx
        )
        
        self.db_manager = LogDatabase(db_path=db_file_path)
        self.conversation_manager = ConversationManager(log_folder_path=log_folder)
        # TODO: Link db_manager to conversation_manager if methods in ConversationManager need it directly.
        # For now, assuming db_manager is used by other components or passed as needed.

        self.prompt_manager = PromptManager(prompt_folder_path=prompt_folder)
        self.instruction_manager = InstructionManager(
            instruction_folder_path=instruction_folder,
            db_manager=self.db_manager 
        )

        # Application state
        self.current_search_method = SearchMethod.VERTEX_AI_SEARCH # Default
        self.current_chat_session = None 
        self.current_model_name = "gemini-1.0-pro-001" # Default model, make configurable
        # Ensure this model is available in your project and location.
        # For grounding, Vertex AI often uses the same model but with specific tools.
        self.grounding_model_name = "gemini-1.0-pro-001" 

        self._handle_initial_args(args)
        
        self.ui.display_message(f"Welcome to Vertex AI CLI! Type 'help' for commands.", style="bold magenta")
        self.ui.display_message(f"Using project '{self.project_id}' in '{self.location}'. App data: {self.app_data_dir}", style="dim")
        if self.project_id == "your-gcp-project-id-placeholder": # Check against the placeholder
             self.ui.display_message("Warning: GCP_PROJECT_ID is not set. AI features may not work.", style="bold yellow")
        if not self.google_search_api_key or not self.google_search_cx:
            self.ui.display_message("Warning: GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_CX not set. Custom search will be unavailable.", style="yellow")


    def _handle_initial_args(self, args):
        # Start a conversation log regardless of --session-name
        session_prefix = args.session_name if args.session_name else "cli_session"
        self.conversation_manager.start_new_conversation(session_name_prefix=session_prefix)

        if args.load_log:
            log_to_load_path = None
            if args.load_log == "latest":
                latest_log_file = self.conversation_manager.get_latest_log_file()
                if latest_log_file:
                    log_to_load_path = latest_log_file
                else:
                    self.ui.display_message("No log files found to load.", style="yellow")
            else:
                potential_path = Path(args.load_log)
                if potential_path.is_absolute():
                    log_to_load_path = potential_path
                else:
                    # Assume it's relative to the app's log folder
                    log_to_load_path = self.conversation_manager.log_folder / args.load_log
            
            if log_to_load_path and log_to_load_path.exists():
                success = self.conversation_manager.load_history_from_file(log_to_load_path)
                if success:
                    self.ui.display_message(f"Loaded conversation from: {log_to_load_path.name}", style="green")
                    # When history is loaded, the current_chat_session should be reset
                    # so that the loaded history is used to start a new chat session
                    # by _handle_send_prompt if the AI handler needs it.
                    self.current_chat_session = None 
                    self.ui.display_message("Active chat session has been reset to use loaded history on next interaction.", style="dim")
                else:
                    self.ui.display_message(f"Failed to load log: {log_to_load_path.name}", style="red")
            elif log_to_load_path: 
                self.ui.display_message(f"Log file not found: {log_to_load_path}", style="red")

        # Handle search method selection from args
        if args.custom_search:
            self.current_search_method = SearchMethod.CUSTOM
        elif args.vertex_ai_search: 
            self.current_search_method = SearchMethod.VERTEX_AI_SEARCH
        # Default is VERTEX_AI_SEARCH as set in __init__

        self.ui.display_message(f"Current search method: {self.current_search_method.name}", style="blue")
        
        # TODO: Handle --use-prompt if provided in args

    def run(self):
        while True:
            try:
                user_input = self.ui.get_user_input("You: ")
                command, cmd_args, raw_input = self.cli_parser.parse_command(user_input)

                if command is None and not raw_input.strip(): # Empty input
                    continue
                
                # Centralized command check
                all_known_cmds = set()
                for cmd_name_key, cmd_details in COMMAND_HELP.items():
                    all_known_cmds.add(cmd_name_key)
                    if "aliases" in cmd_details: # Add aliases if they exist
                        for alias in cmd_details["aliases"]:
                            all_known_cmds.add(alias)
                
                # If command is None but raw_input is not empty, it's a prompt
                if command is None and raw_input.strip():
                    self._handle_send_prompt(raw_input)
                    continue

                # Command handling
                if command in ["exit", "quit"]:
                    self.ui.display_message("Goodbye!", style="bold magenta")
                    # TODO: Call any cleanup methods if necessary (e.g., save unsaved data)
                    # self.db_manager.update_log_entry for current log on exit?
                    break
                elif command == "help":
                    if cmd_args:
                        self.ui.display_specific_command_help(cmd_args[0])
                    else:
                        self.ui.display_main_help_table()
                elif command == "reset":
                    self.conversation_manager.start_new_conversation("reset_session")
                    self.current_chat_session = None # Reset chat session
                    self.ui.display_message("Conversation history cleared and new chat session started!", style="green")
                elif command == "show" and cmd_args and " ".join(cmd_args) == "search method": # Handle multi-word commands
                    self.ui.display_message(f"Current search method: {self.current_search_method.name}", style="blue")
                elif command == "use" and cmd_args: # Handle "use cs", "use vertex"
                    sub_command = cmd_args[0] if cmd_args else ""
                    if sub_command == "cs":
                        self.current_search_method = SearchMethod.CUSTOM
                        self.ui.display_message("Switched to Custom Google Search.", style="green")
                    elif sub_command == "vertex": # New name for "use gs"
                        self.current_search_method = SearchMethod.VERTEX_AI_SEARCH
                        self.ui.display_message("Switched to Vertex AI Search/Grounding.", style="green")
                    else:
                        self.ui.display_message(f"Unknown 'use' subcommand: {sub_command}", style="yellow")
                elif command == "disable" and cmd_args and cmd_args[0] == "search":
                     self.current_search_method = SearchMethod.NONE 
                     self.ui.display_message("All search methods disabled.", style="green")
                
                # Log Management
                elif command == "logs":
                    self._handle_list_logs()
                elif command == "load":
                    self._handle_load_log(cmd_args)
                elif command == "edit" and cmd_args and cmd_args[0] == "log": # "edit log"
                    self._handle_edit_log_description(cmd_args[1:]) # Pass remaining args
                elif command == "view" and cmd_args and cmd_args[0] == "log": # "view log"
                    self._handle_view_log(cmd_args[1:])
                elif command == "tag" and cmd_args and cmd_args[0] == "log": # "tag log"
                    self._handle_tag_log(cmd_args[1:])
                
                # Prompt Management
                elif command == "prompts":
                    self._handle_list_prompts()
                elif command == "save" and cmd_args and cmd_args[0] == "prompt":
                    self._handle_save_prompt(cmd_args[1:])
                elif command == "use" and cmd_args and cmd_args[0] == "prompt":
                    self._handle_use_prompt(cmd_args[1:])

                # Instruction Management (Roles)
                elif command in ["instructions", "roles"]:
                    self._handle_list_instructions()
                elif command == "save" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_save_instruction(cmd_args[1:])
                elif command == "use" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_use_instruction(cmd_args[1:])
                elif command == "edit" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_edit_instruction(cmd_args[1:])
                elif command == "clear" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_clear_instruction()
                elif command == "show" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_show_instruction()
                elif command == "delete" and cmd_args and cmd_args[0] in ["instruction", "role"]:
                    self._handle_delete_instruction(cmd_args[1:])

                # Other commands
                elif command == "textbox" or command == "wm":
                    self._handle_textbox_input()
                elif command == "lookup" or command == "ql":
                    self._handle_quick_lookup(cmd_args)
                elif command == "ask" or command == "qg":
                    self._handle_quick_ask(cmd_args)
                elif command == "show" and cmd_args and cmd_args[0] == "context":
                    self._handle_show_context()
                    
                else:
                    # Check aliases from COMMAND_HELP before defaulting to prompt
                    is_alias_handled = False
                    if command in COMMAND_HELP and COMMAND_HELP[command].get("alias_for"):
                        actual_cmd_key = COMMAND_HELP[command]["alias_for"]
                        # Reconstruct the command call with the actual command
                        # This is a simplified way; a more robust alias system might re-dispatch
                        self.ui.display_message(f"Recognized '{command}' as alias for '{actual_cmd_key}'. Processing...", style="dim")
                        # Simulate re-running the command dispatch (very basic)
                        # This might need a more elegant solution or direct call to handlers
                        new_raw_input = f"{actual_cmd_key} {' '.join(cmd_args)}"
                        new_command, new_cmd_args, _ = self.cli_parser.parse_command(new_raw_input)
                        # This recursive call is dangerous, better to map to handler methods directly
                        # For now, let's just say it's an alias and if the main command is implemented, it works.
                        # The command list above should include main commands for aliases.
                        if new_command in all_known_cmds and new_command not in [command]: # Avoid simple recursion on same alias
                             self.ui.display_message(f"Alias '{command}' for '{new_command}' needs explicit handler mapping or re-parsing logic.", "yellow")
                        # Fall through to prompt or specific message for unhandled aliases for now

                    if not is_alias_handled:
                        if command in all_known_cmds:
                             self.ui.display_message(f"Command '{command}' is recognized but not yet fully implemented.", style="yellow")
                        else:
                             self._handle_send_prompt(raw_input) # Default to treating as a prompt

            except KeyboardInterrupt:
                self.ui.display_message("\nGoodbye! (Interrupted)", style="bold magenta")
                break
            except EOFError:
                self.ui.display_message("\nGoodbye! (EOF)", style="bold magenta")
                break
            except Exception as e:
                self.ui.display_message(f"An unexpected error occurred: {e}", style="bold red")
                # import traceback
                # traceback.print_exc() # For debugging

    # --- Log Management Command Handlers ---
    def _handle_list_logs(self):
        logs_data = self.db_manager.get_all_log_entries(log_root_folder=self.conversation_manager.log_folder)
        self.ui.display_logs(logs_data)

    def _handle_load_log(self, args: List[str]):
        if not args:
            target_log_id = "latest"
        else:
            target_log_id = args[0]
        
        log_to_load_path = None
        log_entry_to_load = None

        if target_log_id.lower() == "latest":
            log_to_load_path = self.conversation_manager.get_latest_log_file()
        else:
            try:
                idx = int(target_log_id)
                log_entry_to_load = self.db_manager.get_log_by_index(idx, self.conversation_manager.log_folder)
                if log_entry_to_load:
                    log_to_load_path = self.conversation_manager.log_folder / log_entry_to_load["filename"]
            except ValueError: # Not an index, treat as filename
                log_to_load_path = self.conversation_manager.log_folder / target_log_id
        
        if log_to_load_path and log_to_load_path.exists():
            success = self.conversation_manager.load_history_from_file(log_to_load_path)
            if success:
                self.current_chat_session = None # Reset chat session
                self.ui.display_message(f"Conversation history loaded from '{log_to_load_path.name}'. Chat session reset.", style="green")
            else:
                self.ui.display_message(f"Failed to load conversation history from '{log_to_load_path.name}'.", style="red")
        else:
            self.ui.display_message(f"Log file '{target_log_id}' not found.", style="red")
            
    def _handle_edit_log_description(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: edit log <index|filename>", style="yellow")
            self._handle_list_logs() # Show logs for selection
            try:
                log_id_str = self.ui.get_user_input("Enter log index or filename to edit: ")
                if not log_id_str: return
            except (EOFError, KeyboardInterrupt): return
            target_log_id = log_id_str
        else:
            target_log_id = args[0]

        log_entry = None
        filename_to_edit = None
        try:
            idx = int(target_log_id)
            log_entry = self.db_manager.get_log_by_index(idx, self.conversation_manager.log_folder)
            if log_entry: filename_to_edit = log_entry["filename"]
        except ValueError:
            filename_to_edit = target_log_id
        
        if not filename_to_edit:
            self.ui.display_message(f"Log '{target_log_id}' not found.", style="red")
            return

        try:
            new_description = self.ui.get_user_input(f"Enter new description for '{filename_to_edit}': ")
            if not new_description: # User cancelled or entered empty
                self.ui.display_message("Edit cancelled.", style="yellow")
                return
        except (EOFError, KeyboardInterrupt):
            self.ui.display_message("\nEdit cancelled.", style="yellow")
            return

        success = self.db_manager.edit_log_description(filename_to_edit, new_description)
        if success:
            self.ui.display_message(f"Description for '{filename_to_edit}' updated.", style="green")
        else:
            self.ui.display_message(f"Failed to update description for '{filename_to_edit}'.", style="red")

    def _handle_view_log(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: view log <index|filename>", style="yellow")
            return
        target_log_id = args[0]
        
        log_entry = None
        log_file_path_to_view = None
        try:
            idx = int(target_log_id)
            log_entry = self.db_manager.get_log_by_index(idx, self.conversation_manager.log_folder)
            if log_entry: log_file_path_to_view = self.conversation_manager.log_folder / log_entry["filename"]
        except ValueError:
            log_file_path_to_view = self.conversation_manager.log_folder / target_log_id
            
        if log_file_path_to_view and log_file_path_to_view.exists():
            try:
                content = log_file_path_to_view.read_text(encoding="utf-8")
                self.ui.display_panel(content, title=f"Content of {log_file_path_to_view.name}")
            except Exception as e:
                self.ui.display_message(f"Error reading log file {log_file_path_to_view.name}: {e}", style="red")
        else:
            self.ui.display_message(f"Log file '{target_log_id}' not found.", style="red")
            
    def _handle_tag_log(self, args: List[str]):
        if len(args) < 3:
            self.ui.display_message("Usage: tag log <index|filename> <tag_key> <tag_value>", style="yellow")
            return
        
        target_log_id, tag_key, tag_value = args[0], args[1], " ".join(args[2:]) # Value can have spaces
        
        log_entry = None
        filename_to_tag = None
        try:
            idx = int(target_log_id)
            log_entry = self.db_manager.get_log_by_index(idx, self.conversation_manager.log_folder)
            if log_entry: filename_to_tag = log_entry["filename"]
        except ValueError:
            filename_to_tag = target_log_id
            
        if not filename_to_tag:
            self.ui.display_message(f"Log '{target_log_id}' not found.", style="red")
            return
            
        # Ensure the file exists in the database (even if not in current FS listing for get_log_by_index)
        # update_log_tags in LogDatabase handles creating a minimal entry if needed.
        self.db_manager.update_log_tags(filename_to_tag, tag_key, tag_value)
        self.ui.display_message(f"Tag '{tag_key}:{tag_value}' added/updated for log '{filename_to_tag}'.", style="green")


    # --- Prompt Management Command Handlers ---
    def _handle_list_prompts(self):
        prompts_data = self.prompt_manager.get_all_prompts()
        self.ui.display_prompts(prompts_data)

    def _handle_save_prompt(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: save prompt <name> [description]", style="yellow")
            return
        
        name = args[0]
        description = " ".join(args[1:]) if len(args) > 1 else None

        last_user_prompt = None
        for i in range(len(self.conversation_manager.history) -1, -1, -1):
            if self.conversation_manager.history[i].startswith("You: "):
                last_user_prompt = self.conversation_manager.history[i][4:].strip()
                break
        
        if not last_user_prompt:
            self.ui.display_message("No previous user message found in history to save.", style="yellow")
            return
            
        self.prompt_manager.save_prompt_template(name, last_user_prompt, description, ai_handler=self.ai_handler)
        # Message is printed by PromptManager.save_prompt_template

    def _handle_use_prompt(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: use prompt <name|index>", style="yellow")
            return
        target_prompt_id = args[0]
        
        prompt_data = None
        prompt_text = None
        try:
            idx = int(target_prompt_id)
            prompt_data = self.prompt_manager.get_prompt_by_index(idx)
            if prompt_data: prompt_text = prompt_data.get("prompt")
        except ValueError:
            prompt_text = self.prompt_manager.load_prompt(target_prompt_id)
            if prompt_text: # If loaded by name, get full data for display
                all_prompts = self.prompt_manager.get_all_prompts()
                prompt_data = next((p for p in all_prompts if p["name"] == target_prompt_id), None)

        if not prompt_text:
            self.ui.display_message(f"Prompt '{target_prompt_id}' not found.", style="red")
            return

        self.ui.display_panel(prompt_text, title=f"Using Prompt: {prompt_data.get('name', target_prompt_id) if prompt_data else target_prompt_id}")
        try:
            specific_query = self.ui.get_user_input("Enter specific query (or press Enter to use as is): ")
        except (EOFError, KeyboardInterrupt):
            self.ui.display_message("\nUse prompt cancelled.", style="yellow")
            return
            
        final_prompt = f"{prompt_text}\n\n{specific_query}" if specific_query.strip() else prompt_text
        self._handle_send_prompt(final_prompt)

    # --- Instruction Management Command Handlers ---
    def _handle_list_instructions(self):
        instructions_data = self.instruction_manager.list_instruction_profiles()
        self.ui.display_instructions(instructions_data)

    def _handle_save_instruction(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: save instruction <name> [description]", style="yellow")
            return
        name = args[0]
        description = " ".join(args[1:]) if len(args) > 1 else "" # Description is optional in save_instruction_profile
        
        self.ui.display_message("Enter instruction text (Ctrl+D or ESC then Enter to save, Ctrl+C to cancel):")
        instruction_text = self.ui.get_multiline_input(f"Instruction for '{name}':")
        
        if instruction_text is None or not instruction_text.strip():
            self.ui.display_message("Save instruction cancelled or empty input.", style="yellow")
            return
            
        success, msg = self.instruction_manager.save_instruction_profile(name, instruction_text, description)
        self.ui.display_message(msg, style="green" if success else "red")

    def _handle_use_instruction(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: use instruction <name|index>", style="yellow")
            return
        target_id = args[0]
        
        instr_name_to_set = None
        try:
            idx = int(target_id)
            instr_data = self.instruction_manager.get_instruction_by_index(idx)
            if instr_data: instr_name_to_set = instr_data["name"]
        except ValueError:
            instr_name_to_set = target_id
            
        if not instr_name_to_set:
            self.ui.display_message(f"Instruction '{target_id}' not found.", style="red")
            return

        current_log_file = self.conversation_manager.current_log_filename.name if self.conversation_manager.current_log_filename else None
        success, msg = self.instruction_manager.set_active_instruction(instr_name_to_set, current_log_file)
        
        if success:
            self.current_chat_session = None # Reset chat session to apply new instruction
            active_text, active_name = self.instruction_manager.get_active_instruction()
            self.ui.display_message(f"{msg} Chat session reset. New instruction will apply to next interaction.", style="green")
            self.ui.display_panel(active_text, title=f"Active Instruction: {active_name}")
        else:
            self.ui.display_message(msg, style="red")
            
    def _handle_edit_instruction(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: edit instruction <name|index>", style="yellow")
            return
        target_id = args[0]

        instr_name_to_edit = None
        instr_data = None
        try:
            idx = int(target_id)
            instr_data = self.instruction_manager.get_instruction_by_index(idx)
            if instr_data: instr_name_to_edit = instr_data["name"]
        except ValueError:
            instr_name_to_edit = target_id
            # We need to load it to get current text and desc
            text, desc = self.instruction_manager.load_instruction_profile(instr_name_to_edit)
            if text is not None:
                instr_data = {"name": instr_name_to_edit, "instruction": text, "description": desc}
        
        if not instr_data or not instr_name_to_edit:
            self.ui.display_message(f"Instruction '{target_id}' not found.", style="red")
            return

        self.ui.display_message(f"Current instruction for '{instr_name_to_edit}':")
        self.ui.display_panel(instr_data["instruction"], title=f"Instruction Text for {instr_name_to_edit}")
        self.ui.display_message(f"Current description: {instr_data.get('description', '')}")

        new_text = self.ui.get_multiline_input(f"Enter new text for '{instr_name_to_edit}' (Ctrl+D or ESC+Enter to save, leave empty to keep current):", default_text=instr_data["instruction"])
        new_desc_str = self.ui.get_user_input(f"Enter new description for '{instr_name_to_edit}' (leave empty to keep current '{instr_data.get('description', '')}'): ")

        final_text = new_text if new_text is not None and new_text.strip() else instr_data["instruction"]
        final_desc = new_desc_str if new_desc_str.strip() else instr_data.get("description", "")
        
        if final_text == instr_data["instruction"] and final_desc == instr_data.get("description", ""):
            self.ui.display_message("No changes made.", style="yellow")
            return

        success, msg = self.instruction_manager.edit_instruction_profile(instr_name_to_edit, final_text, final_desc)
        self.ui.display_message(msg, style="green" if success else "red")
        if success and self.instruction_manager.active_instruction_name == instr_name_to_edit:
            self.ui.display_message("Active instruction was edited. Re-applying...", style="dim")
            self._handle_use_instruction([instr_name_to_edit]) # Re-apply to reset chat session etc.


    def _handle_clear_instruction(self):
        msg = self.instruction_manager.clear_active_instruction()
        self.current_chat_session = None # Reset chat session
        self.ui.display_message(f"{msg} Chat session reset.", style="green")

    def _handle_show_instruction(self):
        active_text, active_name = self.instruction_manager.get_active_instruction()
        if active_text and active_name:
            self.ui.display_panel(active_text, title=f"Active Instruction: {active_name}")
        else:
            self.ui.display_message("No active instruction is set.", style="yellow")

    def _handle_delete_instruction(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: delete instruction <name|index>", style="yellow")
            return
        target_id = args[0]
        
        instr_name_to_delete = None
        try:
            idx = int(target_id)
            instr_data = self.instruction_manager.get_instruction_by_index(idx)
            if instr_data: instr_name_to_delete = instr_data["name"]
        except ValueError:
            instr_name_to_delete = target_id
            
        if not instr_name_to_delete:
            self.ui.display_message(f"Instruction '{target_id}' not found.", style="red")
            return
            
        confirm = self.ui.get_user_input(f"Are you sure you want to delete instruction '{instr_name_to_delete}'? (y/n): ")
        if confirm.lower() == 'y':
            success, msg = self.instruction_manager.delete_instruction_profile(instr_name_to_delete)
            self.ui.display_message(msg, style="green" if success else "red")
            if success and self.instruction_manager.active_instruction_name is None: # If active was deleted
                self.current_chat_session = None # Reset chat
                self.ui.display_message("Active instruction was deleted. Chat session reset.", style="dim")
        else:
            self.ui.display_message("Deletion cancelled.", style="yellow")

    # --- Other Command Handlers ---
    def _handle_textbox_input(self):
        self.ui.display_message("Entering multiline textbox mode...")
        text = self.ui.get_multiline_input()
        if text is not None:
            self.ui.display_message("Multiline text captured. How would you like to use it?", style="cyan")
            action = self.ui.get_user_input("Options: 'prompt', 'save instruction <name>', 'cancel': ")
            action_cmd, *action_args = action.strip().split(" ", 2)

            if action_cmd == "prompt":
                self._handle_send_prompt(text)
            elif action_cmd == "save" and action_args and action_args[0] == "instruction":
                name_parts = action_args[1:]
                if name_parts:
                    self._handle_save_instruction(name_parts + [text]) # Pass text as part of args for simplicity, or handle differently
                else:
                    self.ui.display_message("Please provide a name for the instruction.", style="yellow")
            elif action_cmd == "cancel":
                self.ui.display_message("Textbox action cancelled.", style="yellow")
            else:
                self.ui.display_message("Unknown action. Text discarded.", style="yellow")
        else:
            self.ui.display_message("Textbox input cancelled.", style="yellow") # Already printed by UIRenderer
            
    def _handle_quick_lookup(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: lookup <query>", style="yellow")
            return
        query = " ".join(args)
        self.ui.display_message(f"Performing quick lookup (Vertex AI Search) for: '{query}'...", style="cyan")
        # This call uses the AI handler directly for a one-off grounded search
        # It bypasses conversation history and active instructions from InstructionManager for this specific call
        response_text = self.search_handler.perform_vertex_grounded_search(
            model_handler=self.ai_handler,
            query=query,
            model_name=self.grounding_model_name 
            # Not passing system_instruction_text here, default model behavior for grounding
        )
        self.ui.display_markdown(response_text)
        # Note: This response is NOT added to the main conversation log by default.

    def _handle_quick_ask(self, args: List[str]):
        if not args:
            self.ui.display_message("Usage: ask <query>", style="yellow")
            return
        query = " ".join(args)
        self.ui.display_message(f"Performing quick ask (standard model) for: '{query}'...", style="cyan")
        # This call uses the AI handler directly for a one-off, non-chat message
        # It bypasses conversation history and active instructions from InstructionManager
        response_text = self.ai_handler.generate_content_with_tools( # Using this for direct content gen
            prompt=query,
            model_name=self.current_model_name # Uses the standard model
            # No tools, no specific system instruction for a "quick ask"
        )
        self.ui.display_markdown(response_text)
        # Note: This response is NOT added to the main conversation log by default.
        
    def _handle_show_context(self):
        self.ui.display_message("--- Current Context ---", style="bold magenta")
        
        active_text, active_name = self.instruction_manager.get_active_instruction()
        if active_text and active_name:
            self.ui.display_panel(active_text, title=f"Active Instruction: {active_name} (applies on new/reset chat)")
        else:
            self.ui.display_message("No active system instruction set.", style="yellow")
            
        self.ui.display_message(f"\nSearch Method: {self.current_search_method.name}", style="blue")
        self.ui.display_message(f"Current Model: {self.current_model_name}", style="blue")
        self.ui.display_message(f"Grounding Model: {self.grounding_model_name}", style="blue")
        
        if self.current_chat_session:
            self.ui.display_message("\nAn active chat session exists.", style="dim")
            # Note: Displaying self.current_chat_session.history might be too verbose or complex here.
            # We'll rely on the conversation_manager.history for a user-friendly view.
        else:
            self.ui.display_message("\nNo active chat session (will start new on next prompt).", style="dim")

        if self.conversation_manager.history:
            self.ui.display_message("\nConversation History (from ConversationManager):", style="bold white")
            for entry in self.conversation_manager.history:
                if entry.startswith("You:"):
                    self.ui.display_message(entry, style="green")
                elif entry.startswith("AI:") or entry.startswith("Model:"): # Assuming AI response might start with Model:
                    self.ui.display_markdown(entry) # Use markdown for AI responses
                else: # Notes etc.
                    self.ui.display_message(entry, style="dim")
        else:
            self.ui.display_message("\nNo conversation history in current session.", style="yellow")
        self.ui.display_message("--- End of Context ---", style="bold magenta")


    def _handle_send_prompt(self, prompt_text: str):
        self.ui.display_message(f"Processing prompt...", style="dim") 
        
        active_instruction_text, _ = self.instruction_manager.get_active_instruction()
        
        # Get history in Vertex AI Content object format
        # This is crucial for send_message if a new chat session needs to be started.
        history_for_vertex_model = self.conversation_manager.get_history_for_model()
        
        self.conversation_manager.add_user_message(prompt_text) # Log user message
        ai_response_text = "" # Initialize
        
        is_search_command = prompt_text.lower().startswith("search ")
        
        # Determine if grounding should be used (Vertex AI Search)
        use_vertex_grounding = (
            self.current_search_method == SearchMethod.VERTEX_AI_SEARCH and 
            not is_simple_query(prompt_text) and 
            not is_search_command # "search" command itself uses custom search if SearchMethod.CUSTOM is active
        )

        # Determine if custom search should be used
        use_custom_search = (
            self.current_search_method == SearchMethod.CUSTOM and 
            is_search_command
        )

        if use_vertex_grounding:
            self.ui.display_message("Performing Vertex AI grounded search...", style="cyan")
            # Note: perform_vertex_grounded_search uses generate_content_with_tools,
            # which itself calls load_model with the system_instruction_text.
            ai_response_text = self.search_handler.perform_vertex_grounded_search(
                model_handler=self.ai_handler,
                query=prompt_text,
                model_name=self.grounding_model_name, # Use specific grounding model if different
                system_instruction_text=active_instruction_text # Pass active instruction
            )
            self.conversation_manager.add_system_note(f"Vertex AI search performed for query: '{prompt_text}'")

        elif use_custom_search:
            search_query = prompt_text[len("search "):].strip()
            if not search_query:
                self.ui.display_message("Please provide a query for the search command.", style="yellow")
                self.conversation_manager.history.pop() # Remove the "You: search " message
                return 
                
            self.ui.display_message(f"Performing custom Google search for: {search_query}...", style="cyan")
            custom_search_results = self.search_handler.perform_custom_search(query=search_query)
            
            search_context_for_display, search_context_for_model = self.search_handler.format_custom_search_results(custom_search_results)
            if custom_search_results: 
                self.ui.display_panel(search_context_for_display, title="Custom Search Results")
            else:
                self.ui.display_message("No results found from custom Google search.", style="yellow")

            self.conversation_manager.add_system_note(f"Custom search results obtained for: '{search_query}'")
            # Construct prompt for AI, including search results
            prompt_for_ai = f"Based on the following search results, please answer the query: '{search_query}'.\n\nSearch Results:\n{search_context_for_model}\n\nQuery: {search_query}"
            
            # Call send_message for standard chat interaction with the augmented prompt
            # The active_instruction_text will be used by send_message if a new chat session is started.
            ai_response_text, self.current_chat_session = self.ai_handler.send_message(
                prompt=prompt_for_ai,
                model_name=self.current_model_name,
                system_instruction=active_instruction_text, 
                chat_session=self.current_chat_session,
                conversation_history=history_for_vertex_model # Pass List[Content]
            )
        else: 
            # Standard chat, no explicit search
            # The active_instruction_text will be used by send_message if a new chat session is started.
            ai_response_text, self.current_chat_session = self.ai_handler.send_message(
                prompt=prompt_text,
                model_name=self.current_model_name,
                system_instruction=active_instruction_text, 
                chat_session=self.current_chat_session,
                conversation_history=history_for_vertex_model # Pass List[Content]
            )

        self.ui.display_markdown(ai_response_text)
        self.conversation_manager.add_ai_message(ai_response_text) # Log AI response
        
        if self.db_manager and self.conversation_manager.current_log_filename:
            try:
                self.db_manager.update_log_entry(
                    log_filename_str=str(self.conversation_manager.current_log_filename),
                    conversation_history_lines=self.conversation_manager.history,
                    instruction_manager=self.instruction_manager,
                    ai_handler=self.ai_handler
                )
            except Exception as e:
                self.ui.display_message(f"Error updating log metadata: {e}", style="yellow")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vertex AI CLI - Enhanced command-line interface.")
    parser.add_argument("--load-log", nargs="?", const="latest", default=None,
                        help="Load a conversation log. Provide filename or 'latest'.")
    parser.add_argument("--use-prompt", metavar="PROMPT_NAME", help="Use a saved prompt template at startup (Not Implemented Yet).")
    parser.add_argument("--session-name", metavar="NAME", help="Name for this session (for log file naming).")

    search_group = parser.add_argument_group('search options')
    search_method_arg = search_group.add_mutually_exclusive_group()
    search_method_arg.add_argument("--custom-search", action="store_true", help="Enable custom Google search.")
    search_method_arg.add_argument("--vertex-ai-search", action="store_true", help="Enable Vertex AI native search/grounding (default).")
    
    parsed_args = parser.parse_args()

    # Basic check for GCP_PROJECT_ID
    if not os.getenv("GCP_PROJECT_ID") or os.getenv("GCP_PROJECT_ID") == "your-gcp-project-id-placeholder":
        print("Warning: GCP_PROJECT_ID environment variable is not set or is set to placeholder.")
        print("Please set GCP_PROJECT_ID to your Google Cloud Project ID for AI features to work.")

    app = VertexCLIApplication(args=parsed_args)
    app.run()
