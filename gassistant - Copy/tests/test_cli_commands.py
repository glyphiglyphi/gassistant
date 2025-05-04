# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
from pathlib import Path

# Add parent directory to path so we can import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gemini_cli_v8 import (
        display_help,
        list_logs,
        show_command_help,
        quick_lookup, 
        quick_ask,
        switch_search_method,
        SearchMethod,
        reset_log_database,
        get_multiline_input,
        generate_description_for_log,
        edit_log_description,
        generate_ai_description
    )
except ImportError as e:
    print("Warning: Could not import all modules from gemini_cli_v8: {}".format(e))

class TestCLICommands(unittest.TestCase):
    """Test the CLI command handling functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment"""
        os.rmdir(self.temp_dir)
    
    @patch('rich.console.Console.print')
    def test_display_help(self, mock_print):
        """Test help display command"""
        display_help()
        # Verify that print was called at least once
        mock_print.assert_called()
    
    @patch('rich.console.Console.print')
    def test_show_command_help(self, mock_print):
        """Test showing help for a specific command"""
        # Test with valid command
        result = show_command_help("search")
        self.assertTrue(result)
        mock_print.assert_called()
        
        # Reset mock and test with invalid command
        mock_print.reset_mock()
        result = show_command_help("not_a_real_command")
        self.assertFalse(result)
        mock_print.assert_not_called()
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    def test_quick_lookup(self, mock_console, mock_client):
        """Test quick lookup command"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Call function
        with patch('builtins.print'):
            quick_lookup("test query")
        
        # Verify client was called with correct model
        mock_client.models.generate_content.assert_called_once()
        args = mock_client.models.generate_content.call_args[1]
        self.assertIn("model", args)
        self.assertIn("contents", args)
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    def test_quick_ask(self, mock_console, mock_client):
        """Test quick ask command"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Call function
        with patch('builtins.print'):
            quick_ask("test query")
        
        # Verify client was called with correct model
        mock_client.models.generate_content.assert_called_once()
        args = mock_client.models.generate_content.call_args[1]
        self.assertIn("model", args)
        self.assertIn("contents", args)
    
    def test_switch_search_method(self):
        """Test switching between search methods"""
        # Initialize search method variables
        with patch('gemini_cli_v8.current_search_method', SearchMethod.NONE), \
             patch('gemini_cli_v8.chat', None):
            
            # Test switching to CUSTOM
            result = switch_search_method(SearchMethod.CUSTOM)
            self.assertIn("custom", result.lower())
            
            # Test switching to GROUNDING
            result = switch_search_method(SearchMethod.GEMINI_GROUNDING)
            self.assertIn("grounding", result.lower())
            
            # Test disabling search
            result = switch_search_method(SearchMethod.NONE)
            self.assertIn("disabled", result.lower())

    @patch('sqlite3.connect')
    @patch('gemini_cli_v8.BASE_DIR')
    @patch('gemini_cli_v8.LOG_FOLDER')
    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.unlink')
    @patch('shutil.copy2')
    def test_reset_log_database(self, mock_copy, mock_unlink, mock_exists, 
                              mock_mkdir, mock_log_folder, mock_base_dir, mock_connect):
        """Test resetting the log database"""
        # Mock necessary behavior
        mock_exists.return_value = True
        mock_log_folder.glob.return_value = [Path("log1.txt"), Path("log2.txt")]
        mock_base_dir.__truediv__.return_value = Path("/fake/path")
        mock_connect.return_value = MagicMock()
        
        # Call function
        with patch('gemini_cli_v8.setup_database'):
            log_count = reset_log_database()
        
        # Verify database operations and file operations
        self.assertEqual(log_count, 2)
        self.assertEqual(mock_copy.call_count, 2)
        self.assertEqual(mock_unlink.call_count, 3)  # 2 logs + 1 database

if __name__ == '__main__':
    unittest.main()