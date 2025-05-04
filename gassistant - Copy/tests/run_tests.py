# filepath: c:\Users\Alex\gassistant\tests\run_tests.py
import unittest
import sys
import os

# Add parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import test modules
try:
    from tests.test_utils import TestUtilityFunctions
    from tests.test_api_integration import TestAPIIntegration
    from tests.test_features import TestFeatures, TestSystemInstructions
    from tests.test_search_context import TestSearchContext
    from tests.test_cli_commands import TestCLICommands
    from tests.test_log_management import TestLogManagement, TestLogViewing
    from tests.test_conversation import TestConversation
    from tests.test_search_functions import TestSearchFunctions
except ImportError as e:
    print("Import error: {}".format(e))
    print("Some test modules could not be imported. Check if all test files exist.")

def run_tests():
    """Run all tests and return the number of failures"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestUtilityFunctions,
        TestAPIIntegration,
        TestFeatures,
        TestSystemInstructions,
        TestSearchContext,
        TestCLICommands,
        TestLogManagement,
        TestLogViewing,
        TestConversation,
        TestSearchFunctions
    ]
    
    for test_class in test_classes:
        try:
            test_suite.addTest(unittest.makeSuite(test_class))
        except Exception as e:
            print("Warning: Could not add {} to the test suite: {}".format(test_class.__name__, e))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return the number of failures
    return len(result.failures) + len(result.errors)

if __name__ == '__main__':
    # Run the tests and exit with appropriate code
    failures = run_tests()
    sys.exit(failures)