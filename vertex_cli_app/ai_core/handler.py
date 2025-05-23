import os # For __main__ example
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part, Tool, GenerationConfig
from typing import Optional, Tuple, List, Union

class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")

from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part, Tool, GenerationConfig
from typing import Optional, Tuple, List, Union

class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")

from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part, Tool, GenerationConfig
from typing import Optional, Tuple, List, Union

class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")

import os # For __main__ example
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part, Tool, GenerationConfig
from typing import Optional, Tuple, List, Union

class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev") # Placeholder
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" # Example model
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" # Example model for summarization
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    # This test block will likely only print messages and not make actual API calls
    # unless the environment is fully configured with a valid PROJECT_ID and authentication.
    
    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        # Initialize model with a default system instruction
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            # Test with no existing chat session, no specific system instruction (uses model's default)
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1 # Pass existing session
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            # Test with no existing chat session, but with a specific system instruction for this chat
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION: # Check if PROJECT_ID and LOCATION are defined
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() : # Check if handler was successfully created
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured if you expect real API calls.")

from vertexai.generative_models import GenerativeModel, ChatSession, Content, Part, Tool, GenerationConfig
from typing import Optional, Tuple, List, Union

class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")


class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    # If specific SI for this chat differs from model's current default SI,
                    # use a temporary model instance for this chat.
                    # This does NOT change self.model or self._active_system_instruction.
                    if si_for_new_chat != self._active_system_instruction:
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                # self.load_model would have printed an error via _handle_api_error or similar
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], # Pass as a list of strings or Content objects
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    # top_p=0.95 # Add other params if needed
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text: # .text should give the full response text
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts: # Fallback
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()
            
            if not summary_text:
                # Handle cases where response might be empty or not in expected format
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")


class VertexAIHandler:
    """
    Handles interactions with the Vertex AI platform for generative models.
    """

    def __init__(self, project_id: str, location: str):
        """
        Initializes the Vertex AI SDK and stores configuration.

        Args:
            project_id: The Google Cloud project ID.
            location: The Google Cloud location (e.g., 'us-central1').
        """
        aiplatform.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model: Optional[GenerativeModel] = None 
        self._active_system_instruction: Optional[Content] = None # Store active system instruction Content object
        print(f"Vertex AI SDK initialized for project: {project_id} in {location}")

    def load_model(self, model_name: str, system_instruction_text: Optional[str] = None) -> Optional[GenerativeModel]:
        """
        Loads a generative model from Vertex AI. If a model is already loaded and
        the model_name and system_instruction match, it returns the existing model.
        Otherwise, it attempts to load the new model with the (new) system instruction.

        Args:
            model_name: The name of the model to load (e.g., "gemini-1.0-pro").
            system_instruction_text: Optional system instruction text to set for the model.

        Returns:
            The loaded GenerativeModel instance, or None if loading fails.
        """
        new_system_instruction_content: Optional[Content] = None
        if system_instruction_text:
            new_system_instruction_content = Content(parts=[Part.from_text(system_instruction_text)])

        try:
            if (self.model and hasattr(self.model, 'model_name') and self.model.model_name == model_name and 
                self._active_system_instruction == new_system_instruction_content):
                # print(f"Model '{model_name}' is already loaded with the same system instruction.") # Less verbose
                return self.model
            
            self._active_system_instruction = new_system_instruction_content # This is the "default" SI for self.model
            
            if self._active_system_instruction:
                self.model = GenerativeModel(model_name, system_instruction=self._active_system_instruction)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} with system instruction.")
            else:
                self.model = GenerativeModel(model_name)
                print(f"VertexAIHandler: Loaded Vertex AI Model: {model_name} (no system instruction).")
            
            return self.model
        except Exception as e:
            self._handle_api_error(e)
            self.model = None 
            self._active_system_instruction = None
            return None

    def send_message(self, 
                     prompt: str, 
                     model_name: str, 
                     system_instruction: Optional[str] = None, 
                     chat_session: Optional[ChatSession] = None, 
                     conversation_history: Optional[List[Content]] = None, 
                     tools: Optional[List[Tool]] = None) -> Tuple[str, Optional[ChatSession]]:
        """
        Sends a prompt to the specified Vertex AI model using a chat session.

        Args:
            prompt: The user's prompt.
            model_name: The name of the model to use.
            system_instruction: System-level instruction text for this specific chat, if starting new.
            chat_session: An existing chat session.
            conversation_history: List of `Content` objects for new chat sessions.
            tools: Optional list of tools.

        Returns:
            A tuple containing the model's response text and the (potentially new) chat session object.
        """
        try:
            current_model_instance = self.model
            # Ensure the correct base model is loaded if name differs or no model loaded
            if not current_model_instance or current_model_instance.model_name != model_name:
                # Load with its default/globally set system instruction
                current_model_instance = self.load_model(model_name, system_instruction_text=self._active_system_instruction.parts[0].text if self._active_system_instruction else None)
            
            if not current_model_instance:
                 return "Error: Model could not be loaded for send_message.", None

            if chat_session is None:
                # New chat session
                history_for_session = conversation_history if conversation_history else []
                si_for_new_chat: Optional[Content] = self._active_system_instruction

                if system_instruction: # A specific SI string is passed for this new chat
                    si_for_new_chat = Content(parts=[Part.from_text(system_instruction)])
                    if si_for_new_chat != self._active_system_instruction:
                        # If specific SI for this chat differs from model's current default SI,
                        # use a temporary model instance for this chat.
                        # This does NOT change self.model or self._active_system_instruction.
                        temp_model_for_new_chat = GenerativeModel(model_name, system_instruction=si_for_new_chat)
                        print(f"VertexAIHandler: Starting new chat with temporary model instance for specific system instruction.")
                        chat_session = temp_model_for_new_chat.start_chat(history=history_for_session)
                    else: # Passed SI is same as model's current SI
                         chat_session = current_model_instance.start_chat(
                            history=history_for_session,
                            system_instruction=si_for_new_chat # Uses model's baked-in or the one from 'system_instruction' string
                        )
                else: # No specific SI string, use model's current default SI
                     chat_session = current_model_instance.start_chat(
                        history=history_for_session,
                        system_instruction=self._active_system_instruction 
                    )
                print(f"VertexAIHandler: Started new chat session for model '{model_name}'.")
                if chat_session.system_instruction: # Log what SI the chat session is actually using
                     print(f"VertexAIHandler: New chat using system instruction: '{chat_session.system_instruction.parts[0].text[:100]}...'")
                elif self._active_system_instruction and not system_instruction : # If it inherited from self.model
                     print(f"VertexAIHandler: New chat using system instruction from loaded model: '{self._active_system_instruction.parts[0].text[:100]}...'")
                else:
                    print("VertexAIHandler: New chat started with no specific system instruction.")
            else: 
                # Existing chat session
                print(f"VertexAIHandler: Using existing chat session for model '{model_name}'.")
                if system_instruction:
                    print("VertexAIHandler: Note - 'system_instruction' string provided with an existing chat session. "
                          "This instruction is NOT applied to the ongoing session as system instructions on existing Vertex AI chat sessions are typically immutable.")

            response = chat_session.send_message(prompt, tools=tools if tools else [])
            
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
            
            if not response_text: # Fallback
                if hasattr(response, 'text') and response.text: 
                    response_text = response.text
                else:
                    response_text = "No parsable text content in response, or response might contain non-text parts (e.g., function calls)."
            return response_text, chat_session

        except Exception as e:
            self._handle_api_error(e)
            return f"Error during send_message: {str(e)}", chat_session

    def generate_content_with_tools(self, 
                                    prompt: str, 
                                    model_name: str, 
                                    tools: Optional[List[Tool]] = None,
                                    system_instruction_text: Optional[str] = None) -> str:
        current_model = self.load_model(model_name, system_instruction_text=system_instruction_text)
        if not current_model:
            return "Error: Model not loaded."
        try:
            prompt_content = Content(parts=[Part.from_text(prompt)])
            response = current_model.generate_content(
                contents=[prompt_content], 
                tools=tools if tools else [] 
            )
            response_text = ""
            if response.candidates:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text: 
                            response_text += part.text
            if not response_text: 
                if hasattr(response, 'text') and response.text:
                     response_text = response.text
                else:
                    response_text = "No direct text content in response. Response might contain function calls or be empty."
            return response_text
        except Exception as e:
            self._handle_api_error(e)
            return f"Error during content generation with tools: {str(e)}"

    def generate_text_summary(self, model_name: str, text_to_summarize: str, 
                              prompt_instruction: str, max_output_tokens: int = 50, 
                              temperature: float = 0.3) -> Optional[str]:
        try:
            # Load the model specifically for this summarization task.
            # Pass system_instruction_text=None to ensure it doesn't use the main chat's system instruction.
            summary_model = self.load_model(model_name, system_instruction_text=None) 
            if not summary_model:
                return None

            full_prompt = f"{prompt_instruction}\n\nTEXT TO SUMMARIZE:\n{text_to_summarize}"
            
            response = summary_model.generate_content(
                [full_prompt], 
                generation_config=GenerationConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                )
            )
            summary_text = ""
            if hasattr(response, 'text') and response.text:
                summary_text = response.text.strip()
            elif response.candidates and response.candidates[0].content.parts:
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                         summary_text += part.text.strip() + " "
                 summary_text = summary_text.strip()

            if not summary_text:
                print("Warning: Text summary generation returned no content.")
                return None
            return summary_text
        except Exception as e:
            self._handle_api_error(e)
            return None

    def _handle_api_error(self, error: Exception):
        error_type = type(error).__name__
        error_message = str(error)
        print(f"VertexAIHandler: An API error occurred: [{error_type}] {error_message}")

if __name__ == "__main__":
    PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gcp-project-id-vertex-genai-dev")
    LOCATION = os.getenv("GCP_LOCATION", "us-central1")
    MODEL_NAME = "gemini-1.0-pro-001" 
    SUMMARY_MODEL_NAME = "gemini-1.0-pro-001" 
    
    print(f"--- VertexAIHandler Test (with Summarizer) ---")
    print(f"Attempting to use Project ID: {PROJECT_ID}, Location: {LOCATION}, Model: {MODEL_NAME}")

    try:
        handler = VertexAIHandler(project_id=PROJECT_ID, location=LOCATION)
        model = handler.load_model(MODEL_NAME, system_instruction_text="You are a generally helpful assistant.")
        
        if model:
            print(f"\n--- Test 1: Simple prompt using send_message (chat) ---")
            response_text, chat_session_1 = handler.send_message(
                prompt="Hello, Vertex AI! What is your name?", 
                model_name=MODEL_NAME
            )
            print(f"Vertex AI Response 1: {response_text}")

            if chat_session_1:
                print(f"\n--- Test 2: Follow-up in same chat session ---")
                response_text_2, _ = handler.send_message(
                    prompt="What can you do?", 
                    model_name=MODEL_NAME, 
                    chat_session=chat_session_1
                )
                print(f"Vertex AI Response 2: {response_text_2}")
            
            print(f"\n--- Test 3: New chat with specific system instruction via send_message ---")
            response_text_3, _ = handler.send_message(
                prompt="Explain quantum computing in simple terms.",
                model_name=MODEL_NAME,
                system_instruction="You are a science communicator for beginners." 
            )
            print(f"Vertex AI Response 3 (science comm): {response_text_3}")

            print(f"\n--- Test 4: generate_text_summary ---")
            sample_text_for_summary = (
                "The James Webb Space Telescope (JWST) is a space telescope designed primarily to conduct infrared astronomy. "
                "As the largest optical telescope in space, its high resolution and sensitivity allow it to view objects too old, "
                "distant, or faint for the Hubble Space Telescope."
            )
            summary_instruction = "Generate a very brief (3-5 word) title for the following text:"
            
            summary = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME, 
                text_to_summarize=sample_text_for_summary,
                prompt_instruction=summary_instruction
            )
            if summary:
                print(f"Generated Summary/Title: '{summary}'")
            else:
                print("Summary generation failed or returned None.")

            print(f"\n--- Test 5: generate_text_summary (concise instruction) ---")
            summary_concise = handler.generate_text_summary(
                model_name=SUMMARY_MODEL_NAME,
                text_to_summarize="Quantum computing is a multidisciplinary field comprising aspects of computer science, physics, and mathematics that utilizes quantum mechanics to solve complex problems faster than classical computers.",
                prompt_instruction="Summarize this in exactly one sentence.",
                max_output_tokens=100
            )
            if summary_concise:
                print(f"Generated Concise Summary: '{summary_concise}'")
            else:
                print("Concise summary generation failed.")
        else:
            print(f"Model '{MODEL_NAME}' could not be loaded. Skipping tests.")

    except ImportError as ie:
        print(f"ImportError: {ie}. Make sure google-cloud-aiplatform and other dependencies are installed.")
    except Exception as e:
        print(f"\n--- An error occurred during the VertexAIHandler test ---")
        # Ensure handler exists before trying to use its method, or create a dummy one
        if 'handler' not in locals() and PROJECT_ID and LOCATION:
            handler = VertexAIHandler(PROJECT_ID, LOCATION) 
        if 'handler' in locals() :
             handler._handle_api_error(e)
        else:
            print(f"Unhandled error (handler not initialized or missing): {e}")
        print("\nPlease ensure GCP environment variables (GCP_PROJECT_ID, GCP_LOCATION) are set and ADC is configured.")
