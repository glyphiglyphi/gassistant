# -*- coding: utf-8 -*-
"""
Simple test runner that provides detailed output about test failures.
"""
import sys
import os
import unittest
import traceback

# Make sure the parent directory is in the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

def run_test_module(module_name):
    """Run tests from a specific module with detailed output."""
    print("\n" + "=" * 70)
    print("Running tests from module: {}".format(module_name))
    print("=" * 70)
    
    try:
        # Import the test module
        __import__("tests.{}".format(module_name))
        module = sys.modules["tests.{}".format(module_name)]
        
        # Find all test classes in the module
        test_cases = []
        for item_name in dir(module):
            item = getattr(module, item_name)
            if isinstance(item, type) and issubclass(item, unittest.TestCase):
                test_cases.append(item)
        
        if not test_cases:
            print("No test cases found in module {}".format(module_name))
            return 0
        
        # Run each test case
        failures = 0
        errors = 0
        total_tests = 0
        
        for test_case in test_cases:
            print("\nRunning test case: {}".format(test_case.__name__))
            
            # Create a suite for this test case
            suite = unittest.TestLoader().loadTestsFromTestCase(test_case)
            total_tests += suite.countTestCases()
            
            # Run the tests with a custom result handler
            result = unittest.TestResult()
            suite.run(result)
            
            # Report failures and errors
            for test, err in result.failures:
                print("\n  FAIL: {}".format(test.id()))
                print("  " + "-" * 68)
                print("  {}".format(err))
                failures += 1
            
            for test, err in result.errors:
                print("\n  ERROR: {}".format(test.id()))
                print("  " + "-" * 68)
                print("  {}".format(err))
                errors += 1
            
            # Print success message if all tests passed
            if not result.failures and not result.errors:
                print("  All tests passed in {}".format(test_case.__name__))
        
        # Print summary
        print("\nSummary for {}:".format(module_name))
        print("  Tests run: {}".format(total_tests))
        print("  Failures: {}".format(failures))
        print("  Errors: {}".format(errors))
        
        return failures + errors
        
    except ImportError as e:
        print("Failed to import module '{}': {}".format(module_name, e))
        traceback.print_exc()
        return 1

def main():
    """Run selected test modules."""
    # List of test modules to run (without the 'tests.' prefix)
    test_modules = [
        "test_cli_commands",
        "test_log_management",
        "test_conversation",
        "test_search_functions",
        "test_search_context",
        "test_features", 
        "test_utils"
    ]
    
    # Count total failures and errors
    total_failures = 0
    
    for module in test_modules:
        failures = run_test_module(module)
        total_failures += failures
    
    # Print overall summary
    print("\n" + "=" * 70)
    print("Overall summary:")
    print("  Modules tested: {}".format(len(test_modules)))
    print("  Total failures/errors: {}".format(total_failures))
    print("=" * 70)
    
    return total_failures

if __name__ == "__main__":
    sys.exit(main())