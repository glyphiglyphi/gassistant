"""
Import helper for Vertex AI CLI versions.
This file allows tests to import the current version of Vertex AI functions without hardcoding.
"""
import os
import importlib

# Get the current version to test (default to v1 if not specified)
VERTEX_VERSION = os.environ.get('VERTEX_VERSION', 'v1')
vertex_module_name = f"vertex_ai_cli"

# Import the specified module
try:
    vertex_module = importlib.import_module(vertex_module_name)
    
    # Export the common elements
    search_web = vertex_module.search_web
    ask_gemini_with_search = vertex_module.ask_gemini_with_search
    client = vertex_module.client
    SearchMethod = vertex_module.SearchMethod
    
except ImportError as e:
    raise ImportError(f"Failed to import {vertex_module_name}. Make sure this version exists: {e}")