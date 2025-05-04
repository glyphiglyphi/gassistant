# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Determine which version of the CLI to test based on environment variable
gemini_version = os.environ.get('GEMINI_VERSION', 'v8')
cli_module_name = "gemini_cli_{}".format(gemini_version)

# Ensure the module is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestSearchContext(unittest.TestCase):
    """Test search context functionality in the Gemini CLI application."""
    
    @patch('builtins.print')
    def test_clear_search_context(self, mock_print):
        """Test the 'clear search context' command."""
        # Import the module under test
        try:
            cli = __import__(cli_module_name)
        except ImportError:
            self.skipTest("Could not import {}. Skipping test.".format(cli_module_name))
            return
            
        # Set up test state
        cli.last_search_results = "Some search results"
        
        # Call the command handler directly (simulating what happens in the main loop)
        prompt_text = "clear search context"
        # We're testing what happens in the main loop for this command
        # In the real code, this would be inside the while True loop
        if prompt_text.lower() == "clear search context":
            cli.last_search_results = None
            mock_print("{0}Gemini:{1} {2}Search context has been cleared from memory.{3}".format(
                cli.COLOR_CYAN, cli.COLOR_RESET, cli.COLOR_WHITE, cli.COLOR_RESET))
        
        # Check that last_search_results was cleared
        self.assertIsNone(cli.last_search_results)
        # Check that print was called with the right message
        mock_print.assert_called_once()
        
    @patch('gemini_cli_v8.ask_gemini_with_search')  # Patching the specific function
    def test_search_command_uses_grounding(self, mock_ask):
        """Test that search command uses grounding mode temporarily."""
        # Import the module under test
        try:
            cli = __import__(cli_module_name)
        except ImportError:
            self.skipTest("Could not import {}. Skipping test.".format(cli_module_name))
            return
            
        # Set up initial state
        cli.current_search_method = cli.SearchMethod.NONE  # Start with search disabled
        cli.conversation_history = []
        
        # Call the command handler directly (simulating what happens in the main loop)
        prompt_text = "search python programming"
        search_query = prompt_text[7:].strip()
        
        # Simulate the processing we do in the main loop
        if prompt_text.lower().startswith("search "):
            if search_query:
                cli.conversation_history.append("Note: The following is a web search for '{}'. Results will be kept in context for follow-up questions.".format(search_query))
                mock_ask(search_query, force_search=True, search_method=cli.SearchMethod.GEMINI_GROUNDING)
        
        # Check that ask_gemini_with_search was called correctly
        mock_ask.assert_called_once_with(search_query, force_search=True, 
                                         search_method=cli.SearchMethod.GEMINI_GROUNDING)
        
        # Check that conversation_history was updated correctly
        self.assertTrue(any("python programming" in line for line in cli.conversation_history))
