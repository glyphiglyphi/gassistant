import json
import datetime
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

class PromptManager:
    """
    Manages prompt templates stored as JSON files.
    """

    def __init__(self, prompt_folder_path: Path):
        """
        Initializes the PromptManager.

        Args:
            prompt_folder_path: Path to the directory where prompt templates are stored.
        """
        self.prompt_folder = prompt_folder_path
        self.prompt_folder.mkdir(parents=True, exist_ok=True)
        print(f"PromptManager initialized. Prompt folder: {self.prompt_folder.resolve()}")

    def _generate_ai_description_for_prompt(self, prompt_text: str, ai_handler: Any) -> str:
        """
        Generates a concise description for a prompt template using an AI model.
        Placeholder implementation.
        (Adapted from generate_ai_prompt_description in gemini_cli_v8.py)

        Args:
            prompt_text: The text of the prompt template.
            ai_handler: An AI handler instance (currently unused, for future AI integration).

        Returns:
            A short description for the prompt.
        """
        # TODO: Integrate with VertexAIHandler.generate_content_for_text_summary
        #       or a similar method tailored for prompt description generation.
        #       The original used: client.models.generate_content(model="gemini-2.0-flash", ...)
        if ai_handler: # Placeholder for future use
            print(f"AI Handler provided, would attempt to generate description for: '{prompt_text[:50]}...'")
            # For now, return a more dynamic placeholder if AI handler is present
            return f"AI-generated desc for: {prompt_text[:20]}..." 
        return "Default prompt description"

    def save_prompt_template(self, name: str, prompt_text: str, 
                             description: Optional[str] = None, ai_handler: Optional[Any] = None):
        """
        Save a prompt template to the prompts folder.
        (Adapted from save_prompt_template in gemini_cli_v8.py)

        Args:
            name: The name of the prompt template (will be used as filename).
            prompt_text: The text content of the prompt.
            description: Optional description. If None, one will be generated.
            ai_handler: Optional AI handler for generating description if needed.
        """
        if description is None:
            generated_description = self._generate_ai_description_for_prompt(prompt_text, ai_handler)
            print(f"No description provided for '{name}', using generated: '{generated_description}'")
            final_description = generated_description
        else:
            final_description = description
            
        prompt_data = {
            "prompt": prompt_text,
            "description": final_description,
            "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        file_path = self.prompt_folder / f"{name}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(prompt_data, f, indent=2)
            print(f"Prompt template '{name}' saved to {file_path}")
            return file_path
        except IOError as e:
            print(f"Error saving prompt template '{name}' to {file_path}: {e}")
            return None

    def get_all_prompts(self) -> List[Dict[str, str]]:
        """
        List all saved prompt templates.
        (Adapted from list_prompts in gemini_cli_v8.py)

        Returns:
            A list of dictionaries, each containing prompt info.
        """
        prompts = []
        if not self.prompt_folder.exists() or not self.prompt_folder.is_dir():
            print(f"Prompt folder not found: {self.prompt_folder}")
            return []
            
        for file_name in os.listdir(self.prompt_folder):
            if file_name.endswith(".json"):
                file_path = self.prompt_folder / file_name
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        prompts.append({
                            "name": file_name[:-5],  # Remove .json extension
                            "description": data.get("description", "No description"),
                            "created": data.get("created", "Unknown")
                        })
                except Exception as e:
                    print(f"Error loading prompt file '{file_name}': {e}")
        
        # Sort by creation date (newest first for typical display)
        try:
            prompts.sort(
                key=lambda x: datetime.datetime.strptime(x["created"], "%Y-%m-%d %H:%M:%S") if x["created"] != "Unknown" else datetime.datetime.min,
                reverse=True
            )
        except (ValueError, KeyError) as e:
            print(f"Warning: Error sorting prompts by date: {e}")
            
        return prompts

    def load_prompt(self, name: str) -> Optional[str]:
        """
        Load a prompt template by name.
        (Adapted from load_prompt_template in gemini_cli_v8.py)

        Args:
            name: Name of the prompt template (filename without .json).

        Returns:
            The prompt text string, or None if not found or error.
        """
        file_path = self.prompt_folder / f"{name}.json"
        if not file_path.exists():
            print(f"Prompt template '{name}' not found at {file_path}")
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("prompt")
        except Exception as e:
            print(f"Error loading prompt template '{name}' from {file_path}: {e}")
            return None

    def get_prompt_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific prompt by its 1-based display index.
        The index corresponds to the order in get_all_prompts (newest first).
        """
        all_prompts = self.get_all_prompts() # This returns newest first
        if 1 <= index <= len(all_prompts):
            # get_all_prompts returns newest first, so index 1 is all_prompts[0]
            return all_prompts[index - 1]
        return None

if __name__ == "__main__":
    prompt_dir = Path("./test_prompts_prompt_manager") # Unique name for this test
    manager = PromptManager(prompt_folder_path=prompt_dir)


    # Mock AI Handler for description generation
    class MockAIHandler:
        def generate_text_summary(self, text_to_summarize: str):
            print(f"MockAIHandler: Generating summary for: '{text_to_summarize[:30]}...'")
            return f"Mock AI desc for: {text_to_summarize[:30]}"

    mock_ai = MockAIHandler()

    print("\n--- Test: Saving Prompts ---")
    manager.save_prompt_template("test_prompt1", "This is the first test prompt.", ai_handler=mock_ai)
    manager.save_prompt_template("test_prompt2", "Another prompt for testing.", description="Custom desc", ai_handler=mock_ai)
    manager.save_prompt_template("test_prompt0", "Oldest prompt for sorting test.", ai_handler=mock_ai) # Saved last, but should appear last if sorted oldest first internally before reversing for display
    
    # To ensure 'test_prompt0' is older for consistent get_by_index testing, we might need to manipulate 'created' or save it first.
    # For simplicity, we rely on the current save order and the sort in get_all_prompts.
    # If get_all_prompts sorts newest first, then test_prompt0 (saved last) would be index 1.

    all_prompts = manager.get_all_prompts()
    print("\nAll prompts (newest first by get_all_prompts):")
    for idx, p_info in enumerate(all_prompts):
        print(f"{idx+1}. {p_info}")

    print("\n--- Test: Loading Prompts ---")
    prompt_content = manager.load_prompt("test_prompt1")
    if prompt_content: print(f"\nContent of test_prompt1: {prompt_content}")
    
    prompt_content_custom = manager.load_prompt("test_prompt2")
    if prompt_content_custom: print(f"\nContent of test_prompt2: {prompt_content_custom}")

    prompt_not_exist = manager.load_prompt("non_existent_prompt")
    if prompt_not_exist is None: print("\nSuccessfully handled loading a non-existent prompt (returned None).")

    print("\n--- Test: Get Prompt by Index ---")
    # get_all_prompts returns newest first. So index 1 should be 'test_prompt0'
    prompt_at_idx_1 = manager.get_prompt_by_index(1)
    print(f"Prompt at index 1: {prompt_at_idx_1['name'] if prompt_at_idx_1 else 'Not found'}")
    assert prompt_at_idx_1 and prompt_at_idx_1["name"] == "test_prompt0"
    
    prompt_at_idx_3 = manager.get_prompt_by_index(3) # Should be test_prompt1
    print(f"Prompt at index 3: {prompt_at_idx_3['name'] if prompt_at_idx_3 else 'Not found'}")
    assert prompt_at_idx_3 and prompt_at_idx_3["name"] == "test_prompt1"
    
    prompt_at_idx_invalid = manager.get_prompt_by_index(99)
    assert prompt_at_idx_invalid is None
    print(f"Prompt at index 99: {'Not found' if prompt_at_idx_invalid is None else 'Found unexpectedly'}")

    # import shutil
    # if prompt_dir.exists(): shutil.rmtree(prompt_dir)
    # print(f"\nCleaned up test directory: {prompt_dir}")
        
    print("\n--- PromptManager Test Complete ---")
