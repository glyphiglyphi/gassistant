# filepath: c:\Users\Alex\gassistant\tests\test_search_functions.py
# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import json
from pathlib import Path

# Add parent directory to path so we can import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gemini_cli_v8 import (
        search_web,
        format_search_results,
        is_simple_query,
        quick_lookup,
        quick_ask
    )
except ImportError as e:
    print("Warning: Could not import all modules from gemini_cli_v8: {}".format(e))

class TestSearchFunctions(unittest.TestCase):
    """Test search functionality"""
    
    @patch('requests.get')
    @patch('gemini_cli_v8.SEARCH_FOLDER', Path('/fake/searches'))
    def test_search_web(self, mock_get):
        """Test web search function"""
        # Setup response mock
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'items': [
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
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Call function
        with patch('builtins.open', mock_open()) as m:
            results = search_web("test query", num_results=2, timeout=5)
        
        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args[1]
        self.assertEqual(call_args['params']['q'], 'test query')
        self.assertEqual(call_args['params']['num'], 2)
        self.assertEqual(call_args['timeout'], 5)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['title'], 'Test Result 1')
        self.assertEqual(results[0]['link'], 'https://example.com/1')
    
    @patch('requests.get')
    def test_search_web_error(self, mock_get):
        """Test web search error handling"""
        # Mock an API error
        mock_get.side_effect = Exception("Test error")
        
        # Call the search function
        results = search_web("test query")
        
        # Verify empty results on error
        self.assertEqual(results, [])
    
    def test_format_search_results(self):
        """Test search results formatting"""
        # Sample search results
        results = [
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
        
        # Call function
        display_text, gemini_text = format_search_results(results)
        
        # Verify display format
        self.assertIn("Web Search Results:", display_text)
        self.assertIn("Test Result 1", display_text)
        self.assertIn("https://example.com/1", display_text)
        
        # Verify Gemini format
        self.assertIn("Web search results:", gemini_text)
        self.assertIn("Title: Test Result 1", gemini_text)
        self.assertIn("URL: https://example.com/1", gemini_text)
        self.assertIn("Snippet: This is a test snippet 1", gemini_text)
    
    def test_format_search_results_empty(self):
        """Test search results formatting with empty results"""
        # Call function with empty results
        result = format_search_results([])
        
        # Verify result is a message
        self.assertEqual(result, "No search results found.")
    
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
        self.assertFalse(is_simple_query("What is AI?"))
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    @patch('gemini_cli_v8.types')  # Add patch for the types module
    def test_quick_lookup(self, mock_types, mock_console, mock_client):
        """Test quick lookup feature"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Test lookup response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Setup mock types for search tools
        mock_tool = MagicMock()
        mock_tool_config = MagicMock()
        mock_types.Tool.return_value = mock_tool
        mock_types.ToolConfig.return_value = mock_tool_config
        
        # Call function
        with patch('builtins.print'):
            quick_lookup("test query")
        
        # Verify client call with model
        mock_client.models.generate_content.assert_called_once()
        # We only verify the model is called, not checking for tools since they might be mocked differently
        self.assertEqual(mock_client.models.generate_content.call_count, 1)
    
    @patch('gemini_cli_v8.client')
    @patch('gemini_cli_v8.console')
    def test_quick_ask(self, mock_console, mock_client):
        """Test quick ask feature"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = "Test ask response"
        mock_client.models.generate_content.return_value = mock_response
        
        # Call function
        with patch('builtins.print'):
            quick_ask("test query")
        
        # Verify client call with correct model
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args[1]
        self.assertEqual(call_args["model"], "gemini-2.0-flash")

if __name__ == '__main__':
    unittest.main()