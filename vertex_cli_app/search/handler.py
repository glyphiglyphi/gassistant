import json
import datetime
import os
import requests
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING

# Vertex AI specific imports for grounding
from vertexai.generative_models import Tool
# Try importing from preview, then stable if it moves
try:
    from vertexai.preview.generative_models import GoogleSearchRetrieval
except ImportError:
    # Fallback if it moves out of preview - this is speculative
    # from vertexai.generative_models import GoogleSearchRetrieval 
    # For now, if the preview path fails, we'll have an issue later if it's not there.
    # A more robust solution might involve checking SDK version or specific error handling.
    print("Warning: Could not import GoogleSearchRetrieval from vertexai.preview.generative_models.")
    print("If grounding is intended, ensure the Vertex AI SDK is up to date and the import path is correct.")
    GoogleSearchRetrieval = None 

if TYPE_CHECKING:
    from ..ai_core.handler import VertexAIHandler
    from vertexai.generative_models import Content # For type hinting in MockVertexAIHandler


# Define SEARCH_FOLDER at the module level
SEARCH_FOLDER = Path("./searches")
SEARCH_FOLDER.mkdir(exist_ok=True) # Ensure it exists when module is loaded


class SearchHandler:
    """
    Handles web search operations, including custom search and Vertex AI grounding.
    """

    def __init__(self, google_search_api_key: Optional[str] = None, google_search_cx: Optional[str] = None):
        """
        Initializes the SearchHandler.

        Args:
            google_search_api_key: Google Custom Search API key.
            google_search_cx: Google Custom Search Engine ID.
        """
        self.google_search_api_key = google_search_api_key
        self.google_search_cx = google_search_cx
        print("SearchHandler initialized.")
        if google_search_api_key and google_search_cx:
            print("Google Custom Search API key and CX are configured.")
        else:
            print("Google Custom Search API key and/or CX are NOT configured. Custom search will not work.")


    def perform_custom_search(self, query: str, num_results: int = 5, timeout: int = 10) -> List[Dict[str, str]]:
        """
        Search the web using Google Custom Search API with timeout.
        (Moved from gemini_cli_v8.py - search_web function)

        Args:
            query: The search query.
            num_results: Number of results to fetch.
            timeout: Timeout in seconds for the request.

        Returns:
            A list of search result dictionaries, or an empty list if an error occurs.
        """
        if not self.google_search_api_key or not self.google_search_cx:
            print("Error: Google Custom Search API key or CX not configured. Cannot perform search.")
            return []

        search_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': self.google_search_api_key,
            'cx': self.google_search_cx,
            'q': query,
            'num': num_results
        }

        try:
            print(f"Performing Google Custom Search for: {query}...")
            response = requests.get(search_url, params=params, timeout=timeout)
            response.raise_for_status()
            results = response.json()
            print("Search request successful.")

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            search_file = SEARCH_FOLDER / f"search_{timestamp}.json"
            try:
                with open(search_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                print(f"Search results saved to {search_file}")
            except IOError as e:
                print(f"Error saving search results to file: {e}")

            formatted_results = []
            if 'items' in results:
                for item in results['items']:
                    formatted_results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'displayLink': item.get('displayLink', '')
                    })
                return formatted_results
            else:
                print("No items found in search results.")
                return []
        except requests.exceptions.Timeout:
            print(f"Search Timeout: The search request took too long to complete (timeout: {timeout}s).")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Search Error: {str(e)}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred during custom search: {str(e)}")
            return []

    def format_custom_search_results(self, results: List[Dict[str, str]]) -> Tuple[str, str]:
        """
        Format search results for display and for use with Gemini.
        (Moved from gemini_cli_v8.py - format_search_results function)
        Removes ANSI color codes for now.

        Args:
            results: A list of search result dictionaries.

        Returns:
            A tuple containing:
                - display_text: Formatted plain text for user display.
                - gemini_text: Formatted plain text for model consumption.
        """
        if not results:
            return "No search results found.", "No search results found."

        display_text_parts = ["Web Search Results:"]
        for i, result in enumerate(results, 1):
            display_text_parts.append(f"{i}. {result.get('title', 'N/A')}")
            display_text_parts.append(f"   Link: {result.get('link', 'N/A')}")
            display_text_parts.append(f"   Snippet: {result.get('snippet', 'N/A')}\n")
        display_text = "\n".join(display_text_parts)

        gemini_text_parts = ["Web search results:"]
        for i, result in enumerate(results, 1):
            gemini_text_parts.append(f"{i}. Title: {result.get('title', 'N/A')}")
            gemini_text_parts.append(f"   URL: {result.get('link', 'N/A')}")
            gemini_text_parts.append(f"   Snippet: {result.get('snippet', 'N/A')}\n")
        gemini_text = "\n".join(gemini_text_parts)

        return display_text, gemini_text

    def perform_vertex_grounded_search(self, 
                                       model_handler: 'VertexAIHandler', 
                                       query: str, 
                                       model_name: str,
                                       system_instruction_text: Optional[str] = None) -> str:
        """
        Performs a grounded search using Vertex AI's GoogleSearchRetrieval tool.

        Args:
            model_handler: An instance of VertexAIHandler.
            query: The user's search query.
            model_name: The specific Vertex AI model to use for grounding.
            system_instruction_text: Optional system instruction for the grounding call.
                                     This will be passed to the model_handler.

        Returns:
            The model's response as a string.
        """
        if GoogleSearchRetrieval is None:
            return "Error: GoogleSearchRetrieval tool could not be imported. Grounding search unavailable."
            
        grounding_tool = Tool(google_search_retrieval=GoogleSearchRetrieval())
        
        # Pass system_instruction_text to generate_content_with_tools.
        # The VertexAIHandler's method will handle loading the model with this instruction.
        response_text = model_handler.generate_content_with_tools(
            prompt=query,
            model_name=model_name,
            tools=[grounding_tool],
            system_instruction_text=system_instruction_text
        )
        return response_text


if __name__ == "__main__":
    # Imports for mock testing
    from vertexai.generative_models import Content, Part # Add this for MockVertexAIHandler

    GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "YOUR_API_KEY")
    GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX", "YOUR_CX")
    
    print("--- SearchHandler Test ---")

    if GOOGLE_SEARCH_API_KEY != "YOUR_API_KEY" and GOOGLE_SEARCH_CX != "YOUR_CX":
        print("\n--- Test 1: Custom Search (using configured API keys) ---")
        search_handler = SearchHandler(google_search_api_key=GOOGLE_SEARCH_API_KEY, google_search_cx=GOOGLE_SEARCH_CX)
        
        print("\nTest Case 1.1: Valid search query 'latest AI research'")
        results = search_handler.perform_custom_search("latest AI research", num_results=2)
        if results:
            display, gemini_text_format = search_handler.format_custom_search_results(results)
            print("\nDisplay Format:\n", display)
            print("\nGemini Text Format:\n", gemini_text_format)
        else:
            print("No search results for 'latest AI research'. This might be due to API key issues or network.")

        print("\nTest Case 1.2: Empty search query ''")
        results_empty = search_handler.perform_custom_search("", num_results=2)
        if not results_empty:
            print("Search with empty query returned no results, as expected.")
        else:
            print("Search with empty query returned unexpected results:", results_empty)
    else:
        print("\n--- Test 1: Custom Search (Skipped) ---")
        print("Skipping custom search test as GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_CX are not set.")
        print("To run this test, set these environment variables or replace placeholders in the script.")
    
    print("\n--- Vertex Grounded Search Test (Conceptual) ---")
    # Mock VertexAIHandler setup for testing SearchHandler structure
    class MockVertexAIHandler:
        def __init__(self, project_id, location):
            print(f"MockVertexAIHandler initialized for {project_id} at {location}")
            self.model = None
            self.model_name_loaded = None # Track loaded model name for mock

        def load_model(self, model_name: str, system_instruction_text: Optional[str] = None): # Updated mock
            print(f"MockVertexAIHandler: Loading model {model_name}")
            if system_instruction_text:
                print(f"MockVertexAIHandler: With system instruction: {system_instruction_text[:50]}...")
            
            # Mock a model object that has a generate_content method
            class MockModel:
                def __init__(self, name):
                    self.model_name = name

                def generate_content(self, contents: List[Content], tools: Optional[List[Tool]] = None):
                    prompt_text = contents[0].parts[0].text if contents and contents[0].parts else "NO_PROMPT"
                    print(f"MockModel ({self.model_name}): Generating content for query: '{prompt_text}'")
                    tool_response_text = ""
                    if tools:
                        print(f"MockModel: Tools provided. Example tool: {type(tools[0].google_search_retrieval)}")
                        # Simulate a response that might come from a model after using a tool
                        tool_response_text = f"Mocked grounded response to: {prompt_text}"
                    else:
                        tool_response_text = f"Mocked response without tools to: {prompt_text}"
                    
                    # Simulate the structure of a GenerateContentResponse object
                    class MockPart:
                        def __init__(self, text): self.text = text
                    class MockContent:
                        def __init__(self, text): self.parts = [MockPart(text)]
                    class MockCandidate:
                        def __init__(self, text): self.content = MockContent(text)
                    class MockResponse:
                        def __init__(self, text): 
                            self.text = text # Direct text attribute
                            self.candidates = [MockCandidate(text)] # Candidates list
                    
                    return MockResponse(tool_response_text)

            self.model = MockModel(model_name)
            self.model_name_loaded = model_name # Track the name
            return self.model

        def generate_content_with_tools(self, prompt: str, model_name: str, tools: Optional[List[Tool]] = None, system_instruction_text: Optional[str] = None) -> str:
            # This mock directly calls the mock model's generate_content
            # Ensure model is "loaded" with the correct name and system instruction
            self.load_model(model_name, system_instruction_text=system_instruction_text)

            print(f"MockVertexAIHandler: Calling generate_content_with_tools for model {model_name} with prompt '{prompt}'")
            
            # Simulate what the real method would do:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response_obj = self.model.generate_content(contents=[prompt_content], tools=tools)
            
            # Extract text from response (simplified for mock)
            response_text = ""
            if hasattr(response_obj, 'text') and response_obj.text:
                response_text = response_obj.text
            elif response_obj.candidates:
                for candidate in response_obj.candidates:
                    for part_obj in candidate.content.parts: # Renamed to part_obj to avoid conflict
                        if hasattr(part_obj, 'text'):
                            response_text += part_obj.text
            return response_text if response_text else "Mocked empty response"


        def _handle_api_error(self, e):
            print(f"MockVertexAIHandler: API Error: {e}")

    # Instantiate mock handler and search handler
    mock_vertex_handler = MockVertexAIHandler(project_id="mock-project", location="mock-location")
    search_handler_for_vertex = SearchHandler(google_search_api_key="", google_search_cx="") # Not needed for this test

    # Test grounded search
    grounded_query = "What is the latest news on Vertex AI?"
    # Assume a model name that would be used for grounding
    grounding_model_name = "gemini-1.0-pro-001" 
    
    response = search_handler_for_vertex.perform_vertex_grounded_search(
        model_handler=mock_vertex_handler,
        query=grounded_query,
        model_name=grounding_model_name,
        system_instruction_text="Be very concise." # Test with system instruction
    )
    print(f"Grounded search response: {response}")
    
    print("\n--- SearchHandler Test Complete ---")
