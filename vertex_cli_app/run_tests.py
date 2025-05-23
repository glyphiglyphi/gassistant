# vertex_cli_app/run_tests.py
import os
import sys
import unittest

# Ensure the vertex_cli_app directory is in the Python path
# This allows discovering modules like vertex_cli_app.conversation.manager etc.
# And also tests within vertex_cli_app/tests/ if we place them there.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__))) 

# Placeholder for test discovery
# Later, this will discover tests from a dedicated 'tests' subdirectory.
# For now, it serves as a basic structure.

if __name__ == '__main__':
    print("Running tests for Vertex CLI Application...")
    
    # Create a TestLoader instance
    loader = unittest.TestLoader()
    
    # Discover tests. For now, assume tests will be in a 'tests' subdirectory
    # and named 'test_*.py'.
    # If we create test files directly in module directories (e.g. conversation/test_manager.py),
    # discovery might need adjustment or explicit listing.
    # For a structured approach, a dedicated 'tests' directory is common.
    
    # Let's assume a 'tests' subdirectory for now:
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir) # Create if it doesn't exist
        # Create an empty __init__.py in tests to make it a package
        with open(os.path.join(test_dir, '__init__.py'), 'w') as f:
            pass

    try:
        suite = loader.discover(start_dir=test_dir, pattern='test_*.py')
        print(f"Discovered tests from: {test_dir}")
    except ImportError as e:
        print(f"Error during test discovery (likely __init__.py missing or import error in test files): {e}")
        print(f"Ensure {test_dir} exists and contains an __init__.py file, and all test modules are importable.")
        suite = unittest.TestSuite() # Create an empty suite if discovery fails

    if suite.countTestCases() == 0:
        print("No tests discovered. Make sure test files are in 'vertex_cli_app/tests/' and named 'test_*.py'.")
        # As an example, let's add a placeholder for a test class we'll define soon
        # from tests.test_sample import TestSample # This line would be active later
        # suite.addTest(unittest.makeSuite(TestSample))


    print(f"\nStarting test run (found {suite.countTestCases()} tests):")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\nTest Summary:")
    print(f"Ran {result.testsRun} tests")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    sys.exit(len(result.failures) + len(result.errors))
