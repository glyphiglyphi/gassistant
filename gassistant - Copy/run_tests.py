# Run all tests for the Gemini CLI application
import os
import sys
import unittest

# Make sure the current directory is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the test modules
from tests.test_utils import TestUtilityFunctions
from tests.test_api_integration import TestAPIIntegration
from tests.test_features import TestFeatures, TestSystemInstructions
from tests.test_search_context import TestSearchContext
from tests.test_cli_commands import TestCLICommands
from tests.test_log_management import TestLogManagement, TestLogViewing
from tests.test_conversation import TestConversation
from tests.test_search_functions import TestSearchFunctions

if __name__ == '__main__':
    print("Running all tests for Gemini CLI...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
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
    
    # Add each test class to the suite, with error handling
    for test_class in test_classes:
        try:
            test_suite.addTest(unittest.makeSuite(test_class))
            print("Added {} to test suite".format(test_class.__name__))
        except Exception as e:
            print("Warning: Could not add {} to test suite: {}".format(test_class.__name__, e))
    
    # Run the tests
    print("\nStarting test run:")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\nTest Summary:")
    print("Ran {} tests".format(result.testsRun))
    print("Failures: {}".format(len(result.failures)))
    print("Errors: {}".format(len(result.errors)))
    print("Skipped: {}".format(len(result.skipped)))
    
    # Exit with appropriate code (0 for success, non-zero for failures)
    sys.exit(len(result.failures) + len(result.errors))