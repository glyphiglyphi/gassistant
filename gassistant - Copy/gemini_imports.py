"""
Import helper for Gemini CLI versions.
This file allows tests to import the current version of gemini functions without hardcoding.
"""
import os
import importlib

# Get the current version to test (default to v7 if not specified)
GEMINI_VERSION = os.environ.get('GEMINI_VERSION', 'v8')
gemini_module_name = f"gemini_cli_{GEMINI_VERSION}"

# Import the specified module
try:
    gemini_module = importlib.import_module(gemini_module_name)
    
    # Export the common elements
    search_web = gemini_module.search_web
    ask_gemini_with_search = gemini_module.ask_gemini_with_search
    client = gemini_module.client
    SearchMethod = gemini_module.SearchMethod
    
except ImportError as e:
    raise ImportError(f"Failed to import {gemini_module_name}. Make sure this version exists: {e}")
