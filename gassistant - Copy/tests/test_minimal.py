# -*- coding: utf-8 -*-
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import datetime
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import specific functions without importing the entire module
try:
    from utils.common_types import get_real_time_data, get_formatted_datetime_info, SearchMethod
except ImportError as e:
    print("Error importing from common_types: {}".format(e))

class TestMinimalFunctions(unittest.TestCase):
    """Test a minimal set of functions with few dependencies."""
    
    def test_get_formatted_datetime_info(self):
        """Test the datetime formatting function."""
        try:
            result = get_formatted_datetime_info()
            
            # Check that it's a string
            self.assertIsInstance(result, str)
            
            # Check format roughly matches "Mon 2023-01-01 12:00:00"
            pattern = r"[A-Z][a-z]{2} \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
            self.assertTrue(re.match(pattern, result))
            
            print("get_formatted_datetime_info test passed!")
        except Exception as e:
            self.fail("get_formatted_datetime_info raised exception: {}".format(e))
    
    def test_search_method_enum(self):
        """Test that the SearchMethod enum works correctly."""
        # Check that enum values are as expected
        self.assertEqual(SearchMethod.NONE.value, 0)
        self.assertEqual(SearchMethod.CUSTOM.value, 1)
        self.assertEqual(SearchMethod.GEMINI_GROUNDING.value, 2)
        
        # Check conversion to string
        self.assertEqual(str(SearchMethod.NONE), "SearchMethod.NONE")
        
        print("SearchMethod enum test passed!")
    
    @patch('datetime.datetime')
    def test_get_real_time_data(self, mock_datetime):
        """Test the real-time data function."""
        # Mock datetime to return a fixed timestamp
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2023-01-01 12:00:00"
        mock_datetime.now.return_value = mock_now
        
        # Call function
        result = get_real_time_data()
        
        # Verify format
        self.assertEqual(result, "The current date and time is: 2023-01-01 12:00:00.")
        
        print("get_real_time_data test passed!")

if __name__ == "__main__":
    unittest.main()