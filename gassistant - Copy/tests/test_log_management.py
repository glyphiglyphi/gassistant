# filepath: c:\Users\Alex\gassistant\tests\test_log_management.py
# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import datetime
import sqlite3
from pathlib import Path

# Add parent directory to path so we can import the main script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from gemini_cli_v8 import (
        get_log_filename,
        save_to_file,
        get_latest_log_filename,
        load_conversation_history,
        update_log_description,
        list_logs,
        generate_ai_description,
        edit_log_description,
        setup_database,
        save_conversation_on_reset,
        view_log
    )
except ImportError as e:
    print("Warning: Could not import all modules from gemini_cli_v8: {}".format(e))

class TestLogManagement(unittest.TestCase):
    """Test log management functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_content = (
            "You: Test message 1\n"
            "AI response to message 1\n\n"
            "You: Test message 2\n"
            "AI response to message 2"
        )
        
    def tearDown(self):
        """Clean up test environment"""
        os.rmdir(self.temp_dir)
    
    @patch('gemini_cli_v8.LOG_FOLDER', Path('/fake/logs'))
    @patch('datetime.datetime')
    def test_get_log_filename(self, mock_datetime):
        """Test log filename generation with and without prefix"""
        # Setup datetime mock
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2025-04-20_12-00-00"
        mock_datetime.now.return_value = mock_now
        
        # Test without prefix
        filename = get_log_filename()
        self.assertEqual(filename, Path("/fake/logs/2025-04-20_12-00-00.txt"))
        
        # Test with prefix
        filename = get_log_filename("test_session")
        self.assertEqual(filename, Path("/fake/logs/2025-04-20_12-00-00 test_session.txt"))
    
    @patch('builtins.open', new_callable=mock_open)
    def test_save_to_file(self, mock_file):
        """Test saving conversation to log file"""
        with patch('gemini_cli_v8.log_filename', 'test_log.txt'):
            save_to_file("Test message")
        
        # Verify file was opened correctly and message was written
        mock_file.assert_called_once_with('test_log.txt', 'a', encoding='utf-8')
        mock_file().write.assert_called_once_with("Test message\n")
    
    @patch('os.listdir')
    @patch('os.path.getctime')
    def test_get_latest_log_filename(self, mock_getctime, mock_listdir):
        """Test getting the latest log filename"""
        # Mock directory listing
        mock_listdir.return_value = ['log1.txt', 'log2.txt', 'not_a_log.csv']
        
        # Mock creation times (log2 is newer)
        def mock_ctime(path):
            if 'log1' in path:
                return 1000
            return 2000
        
        mock_getctime.side_effect = mock_ctime
        
        # Call function
        with patch('gemini_cli_v8.LOG_FOLDER', '/fake/logs'):
            latest = get_latest_log_filename()
        
        # Verify correct log was selected
        self.assertEqual(latest, '/fake/logs/log2.txt')
    
    @patch('sqlite3.connect')
    @patch('gemini_cli_v8.BASE_DIR')
    def test_setup_database(self, mock_base_dir, mock_connect):
        """Test database setup function"""
        # Mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Mock path
        mock_base_dir.__truediv__.return_value = Path('/fake/path/logs.db')
        
        # Call function
        db_path = setup_database()
        
        # Verify database operations
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()
        self.assertEqual(db_path, Path('/fake/path/logs.db'))
    
    @patch('gemini_cli_v8.generate_ai_description')
    @patch('sqlite3.connect')
    @patch('gemini_cli_v8.BASE_DIR')
    def test_update_log_description(self, mock_base_dir, mock_connect, mock_generate_desc):
        """Test updating the log description"""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        mock_base_dir.__truediv__.return_value = Path('/fake/path/logs.db')
        mock_cursor.fetchone.return_value = (None,)  # No existing tags
        mock_generate_desc.return_value = "Auto-generated description"
        
        # Set global variables
        with patch('gemini_cli_v8.log_filename', '/fake/logs/test.txt'), \
             patch('gemini_cli_v8.conversation_history', ['You: Test', 'AI response']), \
             patch('gemini_cli_v8.instruction_manager.get_active_instruction', return_value=(None, None)), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.getctime', return_value=1000000):
            
            update_log_description()
        
        # Verify database operations
        self.assertEqual(mock_cursor.execute.call_count, 2)  # SELECT and INSERT/REPLACE
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data="You: Test message 1\nTest response 1\n\nYou: Test message 2\nTest response 2")
    def test_load_conversation_history(self, mock_file):
        """Test loading conversation history from a file"""
        history = load_conversation_history("mock_file.txt")
        
        # Verify the history structure
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0], "You: Test message 1")
        self.assertEqual(history[1], "Test response 1")
        self.assertEqual(history[2], "You: Test message 2")
        self.assertEqual(history[3], "Test response 2")
        
        # Verify file was opened
        mock_file.assert_called_once_with("mock_file.txt", "r", encoding="utf-8")

class TestLogViewing(unittest.TestCase):
    """Test log viewing functionality"""
    
    @patch('sqlite3.connect')
    @patch('os.listdir')
    @patch('os.path.getsize')
    @patch('os.path.getctime')
    @patch('gemini_cli_v8.BASE_DIR')
    @patch('gemini_cli_v8.LOG_FOLDER')
    @patch('rich.console.Console.print')
    def test_list_logs(self, mock_print, mock_log_folder, mock_base_dir,
                      mock_getctime, mock_getsize, mock_listdir, mock_connect):
        """Test listing available logs"""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        mock_base_dir.__truediv__.return_value = '/fake/path/logs.db'
        
        # Mock database results
        mock_cursor.fetchall.return_value = [
            ('log1.txt', 'Description 1', '2025-04-18 12:00:00', 'favorite:yes'),
            ('log2.txt', 'Description 2', '2025-04-19 12:00:00', None)
        ]
        
        # Mock file system
        mock_listdir.return_value = ['log1.txt', 'log2.txt']
        mock_getsize.return_value = 1024  # 1KB
        mock_getctime.return_value = 1000000
        
        # Call function
        logs = list_logs()
        
        # Verify database query and console output
        mock_cursor.execute.assert_called_once()
        mock_print.assert_called_once()
        
        # Verify log data
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]['filename'], 'log2.txt')  # Newest first
        self.assertEqual(logs[0]['is_favorite'], False)
        self.assertEqual(logs[1]['filename'], 'log1.txt')
        self.assertEqual(logs[1]['is_favorite'], True)
        
    @patch('builtins.open', new_callable=mock_open, read_data="You: Test message\nAI: Test response")
    @patch('os.path.exists')
    @patch('os.path.join')
    @patch('gemini_cli_v8.LOG_FOLDER')
    def test_view_log(self, mock_log_folder, mock_join, mock_exists, mock_open):
        """Test viewing a log file"""
        mock_exists.return_value = True
        mock_join.return_value = "/fake/logs/test.txt"
        
        # Test with a string filename
        with patch('builtins.print'):
            view_log("test.txt")
        
        # Verify file was opened
        mock_open.assert_called_once_with("/fake/logs/test.txt", "r", encoding="utf-8")

if __name__ == '__main__':
    unittest.main()