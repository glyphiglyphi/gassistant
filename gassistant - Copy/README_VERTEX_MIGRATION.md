# Migration from Google Gemini to Vertex AI

This document provides information about the migration from Google Gemini to Vertex AI in the CLI application.

## Overview

The migration involved creating a new implementation (`vertex_ai_cli.py`) based on the existing Gemini implementation (`gemini_cli_v8.py`). The new implementation uses the Vertex AI API instead of the Gemini API while maintaining all the existing functionality.

## Key Changes

1. **API Changes**:
   - Replaced `google.genai` imports with `vertexai.generative_models` imports
   - Replaced `genai.Client` with `vertexai.init` and `GenerativeModel`
   - Updated model names to use Vertex AI model names
   - Modified API calls to use Vertex AI format

2. **Authentication**:
   - Vertex AI uses application default credentials or explicit credentials
   - No API key needed as it uses Google Cloud authentication
   - You need to set up a Google Cloud project and enable the Vertex AI API

3. **Model Interaction**:
   - Replaced `client.models.generate_content` with `model.generate_content`
   - Replaced `client.chats.create` with `model.start_chat`
   - Updated content format to use `Content` and `Part` classes
   - Updated grounding to use `Tool.from_google_search_retrieval()`

4. **Other Changes**:
   - Updated references to "Gemini" with "Vertex AI" in user-facing messages
   - Updated error handling to match Vertex AI error patterns
   - Simplified cleanup as Vertex AI doesn't require explicit cleanup

## How to Use

1. **Setup**:
   - Install the required packages: `pip install -r requirements.txt`
   - Set up Google Cloud authentication:
     - Create a Google Cloud project
     - Enable the Vertex AI API
     - Set up application default credentials or explicit credentials
   - Update the project ID and location in `vertex_ai_cli.py`:
     ```python
     vertexai.init(project="your-project-id", location="us-central1")
     ```

2. **Running the Application**:
   - Run the application: `python vertex_ai_cli.py`
   - Use the same commands as before (see `help` for a list of commands)

3. **Testing**:
   - The tests should work with the new implementation
   - Update the environment variable to use the new implementation: `VERTEX_VERSION=v1`

## Potential Issues

1. **Authentication**:
   - Vertex AI requires Google Cloud authentication, which is different from Gemini API key authentication
   - Make sure you have the correct permissions in your Google Cloud project

2. **Model Names**:
   - Vertex AI uses different model names than Gemini
   - The default model names in the code are set to "gemini-2.0-flash" and "gemini-1.5-flash"
   - You may need to update these to match the models available in your Google Cloud project

3. **API Differences**:
   - Some Vertex AI API features may behave slightly differently than Gemini API features
   - If you encounter issues, check the Vertex AI documentation for the specific feature

## References

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Vertex AI Python SDK](https://cloud.google.com/python/docs/reference/aiplatform/latest)
- [Vertex AI Generative Models](https://cloud.google.com/vertex-ai/docs/generative-ai/learn/models)
- [Google Cloud Authentication](https://cloud.google.com/docs/authentication)