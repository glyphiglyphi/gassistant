# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import datetime
import tempfile
import shutil
import re
import json
from pathlib import Path

# Add parent directory to path so we can import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Regular import now that the module has a proper name
from gemini_cli_v8 import (
    is_simple_query, 
    highlight_text,
    print_wrapped_text,
    format_search_results,
    get_log_filename,
    get_real_time_data
)

# Import the InstructionManager class
from system_instructions import InstructionManager

class TestUtilityFunctions(unittest.TestCase):
    """Test the utility functions that don't require API calls"""

    def test_is_simple_query(self):
        """Test the function that detects simple queries"""
        # Test arithmetic operations - should be recognized as simple
        self.assertTrue(is_simple_query("3*3"))
        self.assertTrue(is_simple_query("5 + 2"))
        self.assertTrue(is_simple_query("calculate 10 / 2"))
        self.assertTrue(is_simple_query("what is 5*5"))
        
        # Test other simple queries
        self.assertTrue(is_simple_query("tell me a joke"))
        self.assertTrue(is_simple_query("write me a poem"))
        
        # Test queries that should not be considered simple
        self.assertFalse(is_simple_query("what is the latest news about AI"))
        self.assertFalse(is_simple_query("tell me about recent developments in quantum computing"))
        # Note: "What is AI?" is NOT considered simple in the current implementation
        self.assertFalse(is_simple_query("What is AI?"))

    def test_highlight_text(self):
        """Test text highlighting function"""
        # Test bold formatting
        bold_text = "This is **bold** text"
        highlighted = highlight_text(bold_text)
        self.assertIn("\033[1m", highlighted)  # Check for ANSI bold code
        
        # Test list formatting
        list_text = "* Item 1\n* Item 2"
        highlighted = highlight_text(list_text)
        self.assertIn("•", highlighted)  # Check for bullet point

    def test_print_wrapped_text(self):
        """Test text wrapping function"""
        long_text = "This is a very long text that should be wrapped to fit the terminal width. " * 5
        wrapped = print_wrapped_text(long_text)
        # Check that wrapped text is returned as a string
        self.assertIsInstance(wrapped, str)
        # Check that no line is longer than the terminal width (approximately)
        for line in wrapped.split('\n'):
            # Allow some margin for ANSI codes
            self.assertLessEqual(len(line), shutil.get_terminal_size().columns + 20)

    def test_format_search_results(self):
        """Test search results formatting"""
        mock_results = [
            {
                'title': 'Test Result 1',
                'link': 'https://example.com/1',
                'snippet': 'This is a test snippet 1',
                'displayLink': 'example.com'
            },
            {
                'title': 'Test Result 2',
                'link': 'https://example.com/2',
                'snippet': 'This is a test snippet 2',
                'displayLink': 'example.com'
            }
        ]
        
        # Function returns a tuple with (display_text, gemini_text)
        display_text, gemini_text = format_search_results(mock_results)
        
        # Check display format
        self.assertIn("Web Search Results:", display_text)
        self.assertIn("Test Result 1", display_text)
        self.assertIn("https://example.com/1", display_text)
        
        # Check Gemini text format
        self.assertIn("Web search results:", gemini_text)
        self.assertIn("Title: Test Result 1", gemini_text)
        self.assertIn("URL: https://example.com/1", gemini_text)

    @patch('datetime.datetime')
    def test_get_log_filename(self, mock_datetime):
        """Test log filename generation"""
        # Mock datetime to return a fixed timestamp
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        # Mock the strftime method to return a fixed string
        mock_now.strftime.return_value = "2023-01-01_12-00-00"
        
        # Test without prefix
        filename = get_log_filename()
        
        # Convert Path to string before checking substring
        filename_str = str(filename)
        self.assertIn("2023-01-01_12-00-00", filename_str)
        self.assertTrue(filename_str.endswith(".txt"))
        
        # Test with prefix
        filename = get_log_filename("test_session")
        
        # Convert Path to string before checking substring
        filename_str = str(filename)
        self.assertIn("2023-01-01_12-00-00", filename_str)
        self.assertIn("test_session", filename_str)
        self.assertTrue(filename_str.endswith(".txt"))

    def test_get_real_time_data(self):
        """Test real-time data function"""
        # This function returns the current date and time as a string
        data = get_real_time_data()
        self.assertIsInstance(data, str)
        self.assertIn("The current date and time is:", data)
        # Check format roughly matches "The current date and time is: 2023-01-01 12:00:00."
        self.assertTrue(re.match(r"The current date and time is: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.", data))

class TestInstructionManager(unittest.TestCase):
    """Tests for the InstructionManager class"""
    
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.test_dir)
        self.instruction_manager = InstructionManager(self.base_dir)
        
    def tearDown(self):
        # Clean up the temporary test directory
        shutil.rmtree(self.test_dir)
    
    def test_initialization(self):
        """Test that the instruction folder is created upon initialization"""
        instruction_folder = self.base_dir / "instructions"
        self.assertTrue(instruction_folder.exists())
        self.assertTrue(instruction_folder.is_dir())
        
    def test_save_instruction_profile(self):
        """Test saving an instruction profile"""
        name = "test_instruction"
        instruction_text = "You are a helpful assistant."
        description = "Test description"
        
        # Save the instruction profile
        file_path = self.instruction_manager.save_instruction_profile(name, instruction_text, description)
        
        # Check that the file exists
        self.assertTrue(file_path.exists())
        
        # Check the content of the saved file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data["instruction"], instruction_text)
            self.assertEqual(data["description"], description)
            self.assertIn("created", data)
            self.assertIn("last_used", data)
    
    def test_list_instruction_profiles(self):
        """Test listing instruction profiles"""
        # Save a couple of test profiles
        self.instruction_manager.save_instruction_profile("profile1", "Instruction 1", "Description 1")
        self.instruction_manager.save_instruction_profile("profile2", "Instruction 2", "Description 2")
        
        # List the profiles
        profiles = self.instruction_manager.list_instruction_profiles()
        
        # Check that both profiles are listed
        self.assertEqual(len(profiles), 2)
        
        # Check that the profile information is correct
        profile_names = [p["name"] for p in profiles]
        self.assertIn("profile1", profile_names)
        self.assertIn("profile2", profile_names)
        
        # Check descriptions
        for profile in profiles:
            if profile["name"] == "profile1":
                self.assertEqual(profile["description"], "Description 1")
            elif profile["name"] == "profile2":
                self.assertEqual(profile["description"], "Description 2")
    
    def test_load_instruction_profile(self):
        """Test loading an instruction profile"""
        # Save a test profile
        name = "test_load"
        instruction_text = "You are a helpful assistant."
        description = "Test load description"
        self.instruction_manager.save_instruction_profile(name, instruction_text, description)
        
        # Load the profile
        loaded_instruction, loaded_description = self.instruction_manager.load_instruction_profile(name)
        
        # Check that the loaded data matches what was saved
        self.assertEqual(loaded_instruction, instruction_text)
        self.assertEqual(loaded_description, description)
    
    def test_load_nonexistent_profile(self):
        """Test loading a profile that doesn't exist"""
        instruction, description = self.instruction_manager.load_instruction_profile("nonexistent")
        self.assertIsNone(instruction)
        self.assertIsNone(description)
    
    def test_edit_instruction_profile(self):
        """Test editing an instruction profile"""
        # Save a test profile
        name = "test_edit"
        instruction_text = "You are a helpful assistant."
        description = "Original description"
        self.instruction_manager.save_instruction_profile(name, instruction_text, description)
        
        # Edit the profile
        new_instruction = "You are a very helpful assistant."
        new_description = "Updated description"
        success, message = self.instruction_manager.edit_instruction_profile(name, new_instruction, new_description)
        
        # Check that the edit was successful
        self.assertTrue(success)
        
        # Load the profile and check that it was updated
        loaded_instruction, loaded_description = self.instruction_manager.load_instruction_profile(name)
        self.assertEqual(loaded_instruction, new_instruction)
        self.assertEqual(loaded_description, new_description)
    
    def test_apply_instruction(self):
        """Test applying an instruction to a chat session"""
        # Mock the needed objects
        mock_chat = MagicMock()
        mock_client = MagicMock()
        mock_client.chats.create.return_value = "new_chat_object"
        current_chat_model_name = "test-model"
        conversation_history = ["You: Hello", "Hi there!"]
        mock_search_method = MagicMock()
        mock_search_method.name = "CUSTOM"  # Not GEMINI_GROUNDING
        
        # Save a test profile
        name = "test_apply"
        instruction_text = "You are a helpful assistant."
        self.instruction_manager.save_instruction_profile(name, instruction_text, "Test description")
        
        # Apply the instruction
        success, message, new_chat = self.instruction_manager.apply_instruction(
            instruction_text, name, mock_chat, mock_client, 
            current_chat_model_name, conversation_history, mock_search_method
        )
        
        # Check that the instruction was applied successfully
        self.assertTrue(success)
        self.assertEqual(new_chat, "new_chat_object")
        self.assertEqual(self.instruction_manager.active_instruction, instruction_text)
        self.assertEqual(self.instruction_manager.active_instruction_name, name)
        
        # Check that the client's chats.create method was called with the correct arguments
        mock_client.chats.create.assert_called_once()
        call_args = mock_client.chats.create.call_args[1]
        self.assertEqual(call_args["model"], current_chat_model_name)
        self.assertIsNotNone(call_args["history"])
        self.assertEqual(call_args["system_instruction"], instruction_text)
    
    def test_apply_instruction_grounding_mode(self):
        """Test applying an instruction in grounding mode"""
        # Mock the needed objects
        mock_chat = None
        mock_client = MagicMock()
        current_chat_model_name = "test-model"
        conversation_history = ["You: Hello", "Hi there!"]
        mock_search_method = MagicMock()
        mock_search_method.name = "GEMINI_GROUNDING"
        
        # Save a test profile
        name = "test_grounding"
        instruction_text = "You are a helpful assistant."
        self.instruction_manager.save_instruction_profile(name, instruction_text, "Test description")
        
        # Apply the instruction
        success, message, new_chat = self.instruction_manager.apply_instruction(
            instruction_text, name, mock_chat, mock_client, 
            current_chat_model_name, conversation_history, mock_search_method
        )
        
        # Check that the instruction was applied successfully
        self.assertTrue(success)
        self.assertIsNone(new_chat)  # No chat object is created in grounding mode
        self.assertEqual(self.instruction_manager.active_instruction, instruction_text)
        self.assertEqual(self.instruction_manager.active_instruction_name, name)
        
        # Ensure client.chats.create was not called
        mock_client.chats.create.assert_not_called()
    
    def test_clear_instruction(self):
        """Test clearing the active instruction"""
        # Set an active instruction
        self.instruction_manager.active_instruction = "You are a helpful assistant."
        self.instruction_manager.active_instruction_name = "test_clear"
        
        # Clear the instruction
        success, message = self.instruction_manager.clear_instruction()
        
        # Check that the instruction was cleared
        self.assertTrue(success)
        self.assertIsNone(self.instruction_manager.active_instruction)
        self.assertIsNone(self.instruction_manager.active_instruction_name)

if __name__ == "__main__":
    unittest.main()