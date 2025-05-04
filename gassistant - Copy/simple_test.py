# -*- coding: utf-8 -*-
"""
A very simple test runner to diagnose issues with the test suite.
"""
import sys
import os

# Add the project root directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_simple_test():
    """Run a very simple test to check if imports are working."""
    print("Running simple import test...")
    try:
        from gemini_cli_v8 import (
            get_log_filename,
            save_to_file,
            get_real_time_data
        )
        print("✓ Successfully imported basic functions from gemini_cli_v8")
    except ImportError as e:
        print("✗ Failed to import from gemini_cli_v8: {}".format(e))
        return False
    
    # Try importing system_instructions
    try:
        from system_instructions import InstructionManager
        print("✓ Successfully imported InstructionManager from system_instructions")
    except ImportError as e:
        print("✗ Failed to import InstructionManager: {}".format(e))
        return False
    
    # Test basic functionality
    try:
        current_time = get_real_time_data()
        print("✓ get_real_time_data() works: {}".format(current_time))
    except Exception as e:
        print("✗ Error calling get_real_time_data(): {}".format(e))
        return False
    
    # Test SearchMethod enum
    try:
        from gemini_cli_v8 import SearchMethod
        print("✓ SearchMethod enum values:")
        for method in SearchMethod:
            print("  - {}: {}".format(method.name, method.value))
    except Exception as e:
        print("✗ Error with SearchMethod enum: {}".format(e))
        return False
    
    # Overall success
    print("\nAll simple tests passed successfully!")
    return True

if __name__ == "__main__":
    success = run_simple_test()
    sys.exit(0 if success else 1)