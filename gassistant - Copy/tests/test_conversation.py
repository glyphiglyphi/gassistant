# -*- coding: utf-8 -*-
# filepath: c:\Users\Alex\gassistant\tests\test_conversation.py
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
        ask_gemini_with_search,
        print_conversation_history,
        process_loaded_history,
        get_real_time_data,
        SearchMethod
    )
except ImportError as e:
    print("Warning: Could not import all modules from gemini_cli_v8: {}".format(e))

class TestConversation(unittest.TestCase):
    """Test conversation management functionality"""
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    @patch('gemini_cli_v8.time')
    @patch('gemini_cli_v8.save_to_file')
    def test_ask_gemini_with_search_basic(self, mock_save, mock_time, mock_console, mock_client):
        """Test basic conversation without search"""
        # Setup time mock
        mock_time.time.side_effect = [0, 1]  # Start and end times
        
        # Setup client response mock
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_chat.send_message.return_value = mock_response
        
        # Set global variables
        with patch('gemini_cli_v8.chat', mock_chat), \
             patch('gemini_cli_v8.conversation_history', []), \
             patch('gemini_cli_v8.current_search_method', SearchMethod.NONE), \
             patch('gemini_cli_v8.log_filename', 'test_log.txt'), \
             patch('builtins.print'):
            
            # Call function
            ask_gemini_with_search("Test question")
        
        # Verify conversation was updated
        mock_save.assert_called()
        
        # Verify client was called
        mock_chat.send_message.assert_called_once()
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    @patch('gemini_cli_v8.search_web')
    @patch('gemini_cli_v8.time')
    @patch('gemini_cli_v8.save_to_file')
    def test_ask_gemini_with_custom_search(self, mock_save, mock_time, mock_search, 
                                        mock_console, mock_client):
        """Test conversation with custom search"""
        # Setup time mock
        mock_time.time.side_effect = [0, 0.5, 1]  # Start, after search, end times
        
        # Setup search mock
        mock_search.return_value = [
            {
                'title': 'Test Result',
                'link': 'https://example.com',
                'snippet': 'Test snippet',
                'displayLink': 'example.com'
            }
        ]
        
        # Setup client response mock
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Test response with search context"
        mock_chat.send_message.return_value = mock_response
        
        # Set global variables
        with patch('gemini_cli_v8.chat', mock_chat), \
             patch('gemini_cli_v8.conversation_history', []), \
             patch('gemini_cli_v8.current_search_method', SearchMethod.CUSTOM), \
             patch('gemini_cli_v8.log_filename', 'test_log.txt'), \
             patch('gemini_cli_v8.format_search_results', return_value=("Display Text", "Gemini Text")), \
             patch('builtins.print'):
            
            # Call function with force search
            ask_gemini_with_search("Test question", force_search=True)
        
        # Verify search was called
        mock_search.assert_called_once()
        
        # Verify client was called with search context
        mock_chat.send_message.assert_called_once()
        
        # Verify save was called
        mock_save.assert_called()
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    @patch('gemini_cli_v8.time')
    @patch('gemini_cli_v8.save_to_file')
    def test_ask_gemini_with_grounding(self, mock_save, mock_time, mock_console, mock_client):
        """Test conversation with Gemini grounding"""
        # Setup time mock
        mock_time.time.side_effect = [0, 1]  # Start and end times
        
        # Setup client response mock
        mock_response = MagicMock()
        mock_response.text = "Test response with grounding"
        mock_client.models.generate_content.return_value = mock_response
        
        # Set global variables
        with patch('gemini_cli_v8.chat', None), \
             patch('gemini_cli_v8.conversation_history', []), \
             patch('gemini_cli_v8.current_search_method', SearchMethod.GEMINI_GROUNDING), \
             patch('gemini_cli_v8.log_filename', 'test_log.txt'), \
             patch('gemini_cli_v8.GROUNDING_MODEL_NAME', "test-grounding-model"), \
             patch('builtins.print'):
            
            # Call function
            ask_gemini_with_search("Test question", search_method=SearchMethod.GEMINI_GROUNDING)
        
        # Verify client was called with right model and tools
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args[1]
        self.assertEqual(call_args['model'], "test-grounding-model")
        # Verify config contains tools
        self.assertIn('config', call_args)
        
        # Verify save was called
        mock_save.assert_called()
    
    @patch('rich.console.Console.print')
    def test_print_conversation_history(self, mock_print):
        """Test printing conversation history"""
        # Set global variables
        with patch('gemini_cli_v8.conversation_history', [
                "You: Test question 1", 
                "AI response 1",
                "You: Test question 2",
                "AI response 2"
             ]), \
             patch('builtins.print'):
            
            print_conversation_history()
        
        # Verify console.print was called the right number of times
        self.assertEqual(mock_print.call_count, 2)  # Once for each AI response

    @patch('gemini_cli_v8.client')
    def test_process_loaded_history_standard_chat(self, mock_client):
        """Test processing loaded history for standard chat"""
        # Setup mock client
        mock_chat = MagicMock()
        mock_client.chats.create.return_value = mock_chat
        
        # Test history
        history = [
            "You: Test question 1",
            "AI response 1",
            "You: Test question 2",
            "AI response 2"
        ]
        
        # Set global variables
        with patch('gemini_cli_v8.chat', None), \
             patch('gemini_cli_v8.conversation_history', []), \
             patch('gemini_cli_v8.current_search_method', SearchMethod.NONE), \
             patch('gemini_cli_v8.current_chat_model_name', "test-model"), \
             patch('gemini_cli_v8.instruction_manager.get_active_instruction', 
                  return_value=(None, None)), \
             patch('builtins.print'):
            
            # Call function
            process_loaded_history(history)
        
        # Verify client chat creation
        mock_client.chats.create.assert_called_once()
        call_kwargs = mock_client.chats.create.call_args[1]
        self.assertEqual(call_kwargs['model'], "test-model")
        self.assertIn('history', call_kwargs)

    @patch('datetime.datetime')
    def test_get_real_time_data(self, mock_datetime):
        """Test getting real-time data string"""
        # Setup datetime mock
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-04-20 12:00:00"
        mock_datetime.now.return_value = mock_now
        
        # Call function
        result = get_real_time_data()
        
        # Verify format
        self.assertEqual(result, "The current date and time is: 2025-04-20 12:00:00.")

if __name__ == '__main__':
    unittest.main()