<!-- filepath: c:\Users\Alex\gassistant\README.md -->
# Gemini Assistant CLI

An enhanced command-line interface for interacting with Google's Gemini AI models with powerful features including conversation history management, prompt templates, web search integration, system instructions, and persistent search context.

## Features

- Interactive conversations with Google's Gemini AI models
- Web search integration that's disabled by default but can be enabled on demand
- Persistent search context for follow-up questions about search results
- Native Gemini grounding capability for improved responses
- Save and load conversation history
- System instructions for customizing AI behavior
- Create and manage reusable prompt templates
- Real-time data integration
- Rich text output with Markdown support

## Installation

### Prerequisites

- Python 3.7+
- Google Gemini API key
- Google Custom Search API key and Search Engine ID

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/gemini-assistant.git
   cd gemini-assistant
   ```

2. Install required packages:
   ```
   pip install google-generativeai colorama prompt_toolkit rich requests
   ```

3. Configure your API keys in the script (or modify to use environment variables)

## Usage

### Basic Usage

Run the script to start an interactive session:

#### Using Windows PowerShell

```
python gemini_cli_v8.py
```

#### Using WSL (Windows Subsystem for Linux)

You can run the application directly from WSL using the provided shell script:

```bash
# Make the script executable (first time only)
chmod +x run_gemini.sh

# Run the application
./run_gemini.sh
```

Alternatively, you can run it directly with Python in WSL:

```bash
python3 gemini_cli_v8.py
```

To start with a specific question:

```
python gemini_cli_v8.py "What is quantum computing?"
```

Or with WSL:

```bash
./run_gemini.sh "What is quantum computing?"
```

### Command Line Arguments

- `--session-name NAME`: Name for the current session
- `--load-log [FILENAME]`: Load a previous conversation log
- `--use-prompt PROMPT_NAME`: Start with a saved prompt template
- `--custom-search`: Enable custom Google search (disabled by default)
- `--gemini-grounding`: Enable Gemini's native grounding capability (disabled by default)

### Interactive Commands

- `exit` or `quit`: Exit the application
- `load` or `load last`: Load the most recent conversation
- `load <filename>`: Load a specific conversation
- `reset`: Clear the current conversation
- `help`: Show help information
- `prompts`: List all saved prompt templates
- `save prompt <name>`: Save the last message as a prompt template
- `save prompt <name> <description>`: Save with description
- `use prompt <name>`: Load and use a saved prompt template
- `list logs`: List all available conversation logs
- `search <query>`: Search the web and keep results in context for follow-up questions
- `clear search context`: Clear previously searched information from context
- `show search context`: Display the search information currently kept in memory
- `use cs`: Switch to custom Google search method
- `use gs`: Switch to Gemini's native grounding capability
- `disable search`: Disable all search methods
- `show search method`: Display the current search method
- `save instruction <name>`: Save a system instruction profile
- `save instruction <name> <description>`: Save with description
- `list instructions`: List all saved instruction profiles
- `use instruction <name>`: Apply a saved instruction profile to the current session
- `edit instruction <name>`: Edit an existing instruction profile
- `clear instruction`: Remove the active system instruction
- `show instruction`: Display the currently active system instruction

## Web Search Integration

The assistant offers two methods for web search integration:

1. **Custom Search** - Uses Google Custom Search API to retrieve results and presents them to both the user and the model
2. **Gemini Grounding** - Leverages Gemini's native grounding capability for more integrated search

All search results are automatically stored in context memory, allowing you to ask follow-up questions about the information without needing to search again.

### Example Using Search Context

```
You: search medellin current weather in celsius
Gemini: Performing one-time web search...
[Search results and weather information]

You: is this humidity level good?
Including previous search results in context.
[Response about whether the humidity level is appropriate]
```

The assistant automatically includes previous search results in the context for follow-up questions. You can view the current search context with `show search context` or clear it with `clear search context`.

## Advanced Prompt Templates

Here are some of the most powerful prompt templates with detailed usage guidance:

### 1. Comparative Analysis

```
Compare [concept A] and [concept B] by origins, principles, applications, and limitations. How do they interact within [field]? Include expert debates and their significance.
```

**Usage Tips:**
- For academic comparisons: Replace concepts with theories or frameworks
- For technology evaluation: Use with competing technologies
- For business analysis: Compare business models or strategies

### 2. Interdisciplinary Connections

```
How does [topic] connect with [field A], [field B], and [field C]? What insights and methods transfer between them? How does this enhance understanding?
```

**Usage Tips:**
- For research exploration: Connect emerging topics with established fields
- For educational curriculum development: Find connections between subjects
- For innovation and problem-solving: Map a challenge to diverse knowledge domains

### 3. Expert Perspectives

```
Simulate three experts' contrasting views on [topic], including agreements, disagreements, methodologies, and evidence. What insights emerge?
```

**Usage Tips:**
- For policy analysis: Use with contentious policy issues
- For technical debates: Apply to technological approaches or standards
- For philosophical exploration: Use with fundamental questions
- Specifying experts: You can optionally name specific perspectives

### 4. Learning Roadmap

```
Design a 6-month path to master [topic] with phases, resources, exercises, potential obstacles, and verification methods. How should I sequence concepts?
```

**Usage Tips:**
- For technical skills: Specify programming languages or technologies
- For academic subjects: Apply to fields of study
- For practical skills: Use for hands-on abilities
- With prerequisites: Specify your starting point
- With constraints: Add time or resource limitations

### 5. Misconception Correction

```
What are 5 common misconceptions about [topic]? For each, provide accurate understanding, evidence, and memory aids to reinforce correct information.
```

**Usage Tips:**
- For scientific topics: Address popular science myths
- For health and wellness: Correct dangerous misinformation
- For technical concepts: Clarify programming or engineering misunderstandings
- For specific audiences: Target misconceptions held by particular groups

### Additional Prompt Templates

- **Progressive Complexity**: `Explain [complex topic] for beginners using simple analogies, then gradually introduce technical terminology and advanced principles to build my understanding.`

- **Real-World Applications**: `Show 3-5 practical applications of [concept], explaining mechanisms, challenges, and future potential. How can I apply this to [my specific context]?`

- **First Principles Analysis**: `Deconstruct [concept] into its fundamental elements. How do these components interact? If rebuilding from scratch, what would be your approach?`

- **Historical Development**: `Trace [concept]'s evolution, noting key problems, figures, breakthroughs, and paradigm shifts. How might this history inform future developments?`

- **Mental Models Guide**: `What are the 3-5 key mental models for understanding [topic]? Explain each model's mechanism, application, limitations, and complementary relationships.`

- **Feynman Technique**: `Explain [concept] in detail, then help me reformulate it simply for a 12-year-old. Identify understanding gaps and suggest accurate analogies.`

- **Deeper Questions**: `What nuanced questions about [topic] reveal hidden dimensions, challenge assumptions, or reflect current expert debates? Why are these significant?`

- **Spaced Repetition Plan**: `Create a spaced review schedule for [subject] with intervals and progressive depth questions. How should I adjust based on performance?`

- **Deliberate Practice System**: `Design practice exercises for [skill] with sub-skill focus, feedback mechanisms, difficulty progression, and motivation strategies. How can I measure improvement?`

- **Interleaved Learning**: `Create a plan alternating between [related subjects] to enhance discrimination. How should I structure sessions and focus on connections?`

## Tips for Creating Effective Prompt Templates

1. **Use placeholders consistently**
   - Use square brackets for placeholders: `[topic]`, `[concept A]`
   - Be specific about what should replace the placeholder

2. **Consider complexity levels**
   - Create variations of templates for different knowledge levels
   - Add qualifiers like "for beginners" or "advanced analysis of"

3. **Specify output format**
   - Request specific sections or structures when needed
   - Example: "Organize the response with clear headings for each section"

4. **Save related templates**
   - Create families of related templates for different analysis approaches
   - Example: Save both "historical_analysis" and "future_projections" templates

5. **Test and refine**
   - Use the templates and refine them based on the quality of responses
   - Save improved versions with descriptive names

## Using System Instructions

System Instructions provide a way to set persistent behavioral directives that shape how Gemini responds across an entire conversation.

### What are System Instructions?

Unlike prompt templates (which structure individual queries), system instructions define how Gemini should behave throughout a conversation. They act as a set of guidelines or directives that influence the AI's responses consistently across multiple exchanges.

### Benefits of System Instructions

- **Consistent AI Behavior**: Maintain a specific persona, tone, or mode of interaction
- **Specialized Knowledge Contexts**: Frame the conversation within a specific domain expertise
- **Customized Response Formats**: Standardize how information is presented across responses
- **Safety and Compliance**: Add domain-specific guidelines or restrictions

### Creating System Instructions

To create a system instruction:
```
save instruction expert_programmer
```

Then enter your instruction, ending with a line containing only "END":
```
You are an expert programmer specializing in Python. 
Always include code examples with your explanations.
Format code using proper markdown code blocks.
Point out potential issues with the code and suggest improvements.
END
```

### Example System Instructions

1. **Expert Programming Assistant**:
   ```
   You are an expert programmer specializing in Python, JavaScript, and system design.
   - For code questions, provide working examples with comments explaining the logic
   - When explaining concepts, use analogies to real-world situations
   - Always mention potential edge cases or performance considerations
   - Format code blocks properly with appropriate syntax highlighting
   - If suggesting multiple approaches, explain the trade-offs between them
   ```

2. **Academic Writing Coach**:
   ```
   You are an academic writing coach specializing in clear, concise academic prose.
   - Help organize ideas into logical structures
   - Suggest clearer phrasing while maintaining academic rigor
   - Identify areas where evidence or citations may be needed
   - Use simple language to explain complex concepts when appropriate
   - Always consider the target audience of the academic writing
   ```

3. **Debug Assistant**:
   ```
   You are a specialized debugging assistant. Your primary goal is to help diagnose and fix issues in code.
   - Always start by confirming your understanding of the problem
   - Look for common issues first before exploring more complex possibilities
   - Suggest specific tests or logging statements to isolate the issue
   - When providing a fix, explain why the issue occurred
   - Recommend preventative measures to avoid similar bugs in the future
   ```

### Command Reference for System Instructions

- `save instruction <name>`: Save a new system instruction profile
- `save instruction <name> <description>`: Save with an optional description
- `list instructions`: Show all available instruction profiles
- `use instruction <name>`: Apply a saved instruction profile to the current session
- `edit instruction <name>`: Modify an existing instruction profile
- `clear instruction`: Remove the active system instruction
- `show instruction`: Display the currently active system instruction

### Example Usage Session

```
You: use instruction expert_programmer

Gemini: System instruction 'expert_programmer' applied to the current session.
Description: Python programming expert that provides detailed code examples

You: Explain how to create a simple web server in Python

Gemini Response
─────────────────────────────────────────────────────────────────────────────
# Creating a Simple Web Server in Python

Python makes it easy to create a basic web server with just a few lines of code. I'll show you how to do this using the built-in `http.server` module.

## Using the Built-in HTTP Server

Here's a simple example:

[Code example showing basic HTTP server implementation]

This code will serve files from the directory where you run the script.

## Important considerations:
[Security and performance considerations]

## A more robust example with custom routing
[More advanced implementation example]

Would you like me to explain any specific part of these examples in more detail?
─────────────────────────────────────────────────────────────────────────────

You: clear instruction

Gemini: Active system instruction cleared. Chat session has been reset.
```

This example demonstrates how the expert_programmer instruction creates responses with technical details and code examples. For actual code implementations, refer to the documentation website or source code.

### Another Example: Academic Writing Coach

```
You: use instruction academic_writing

// ...rest of the example
```

## Testing

The application comes with a comprehensive test suite to ensure functionality remains intact as the codebase evolves.

### Running Tests

To run all tests:

```bash
python -m pytest tests/
```

Or use the test runner script:

```bash
python tests/run_tests.py
```

### Testing Different Versions

The test suite supports testing different versions of the Gemini CLI application. By default, tests run against version 7 (`gemini_cli_v7.py`), but you can specify a different version using the `GEMINI_VERSION` environment variable:

```bash
# Test the default version (v7)
python -m pytest tests/

# Test a specific version (e.g., v8)
GEMINI_VERSION=v8 python -m pytest tests/

# On Windows Command Prompt
set GEMINI_VERSION=v8
python -m pytest tests/

# On Windows PowerShell
$env:GEMINI_VERSION="v8"
python -m pytest tests/

# On WSL (Windows Subsystem for Linux)
export GEMINI_VERSION=v8
python3 -m pytest tests/
```

This allows you to maintain multiple versions of the application while ensuring all features work correctly across versions.

### Test Coverage

The test suite covers:

1. **Utility Functions**: Text formatting, pattern detection, file operations
2. **API Integration**: Web search and Gemini API interactions (with mocks)
3. **Core Features**: Conversation history, prompt templates, search methods

### Adding Tests

When adding new features, please add corresponding tests in the appropriate test file:

- `tests/test_utils.py`: For utility functions
- `tests/test_api_integration.py`: For API interactions
- `tests/test_features.py`: For core application features

### Continuous Integration

GitHub Actions automatically runs tests on push to main branch and on pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
