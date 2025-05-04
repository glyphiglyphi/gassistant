# -*- coding: utf-8 -*-
"""
The most basic test script with improved error handling to diagnose import issues.
"""
import sys
import os
import traceback

print("Python version: {}".format(sys.version))
print("Current directory: {}".format(os.path.abspath('.')))
print("Python path: {}".format(sys.path))

# First, check if the file exists
gemini_path = os.path.join(os.path.abspath('.'), 'gemini_cli_v8.py')
if os.path.exists(gemini_path):
    print("Found gemini_cli_v8.py at: {}".format(gemini_path))
else:
    print("ERROR: gemini_cli_v8.py not found at: {}".format(gemini_path))

try:
    print("\nAttempting to import gemini_cli_v8...")
    import gemini_cli_v8
    print("Successfully imported gemini_cli_v8")
    
except ImportError as e:
    print("Failed to import gemini_cli_v8: {}".format(e))
    print("Traceback:")
    traceback.print_exc()
    
    print("\nTrying to find module in more detail...")
    try:
        # Try to import specific functions to isolate the issue
        from gemini_cli_v8 import get_real_time_data
        print("Successfully imported get_real_time_data")
    except ImportError as e:
        print("Failed to import get_real_time_data: {}".format(e))
    
    sys.exit(1)
except Exception as e:
    print("Unexpected error when importing gemini_cli_v8: {}".format(e))
    print("Traceback:")
    traceback.print_exc()
    sys.exit(1)

try:
    from utils.common_types import SearchMethod
    print("\nSuccessfully imported SearchMethod from utils.common_types")
except ImportError as e:
    print("\nFailed to import SearchMethod from utils.common_types: {}".format(e))
    print("Traceback:")
    traceback.print_exc()

print("\nBasic import test completed successfully!")