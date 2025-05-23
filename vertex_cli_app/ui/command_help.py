COMMAND_HELP = {
    "help": {
        "description": "Display help information about commands.",
        "usage": "help [command]",
        "examples": [
            "help - Show all available commands.",
            "help search - Show detailed help for the search command."
        ],
        "category": "General"
    },
    "exit": {
        "description": "Exit the application.",
        "usage": "exit | quit",
        "examples": [
            "exit - Close the CLI application."
        ],
        "category": "General"
    },
    "quit": { # Alias for exit
        "description": "Exit the application.",
        "usage": "quit | exit",
        "examples": [
            "quit - Close the CLI application."
        ],
        "category": "General"
    },
    "search": {
        "description": "Perform a web search (custom Google Search or Vertex AI Grounding). Results are kept in context for follow-up questions if applicable.",
        "usage": "search <query>",
        "examples": [
            "search latest AI research papers",
            "search current weather in London"
        ],
        "category": "Search" # New category
    },
    "logs": {
        "description": "Show all available conversation logs with their descriptions.",
        "usage": "logs",
        "examples": [
            "logs - Display all saved conversation logs."
        ],
        "category": "Log Management"
    },
    "load": {
        "description": "Load a conversation history from a log file.",
        "usage": "load [filename|index] [--with-history]",
        "examples": [
            "load - Load the most recent conversation.",
            "load 3 - Load conversation from log with index 3.",
            "load 2023-11-24_14-22-33.txt - Load a specific log file.",
            "load --with-history - Load the most recent log and print its history."
        ],
        "category": "Log Management"
    },
    "prompts": {
        "description": "List all saved prompt templates.",
        "usage": "prompts",
        "examples": [
            "prompts - Show all available prompt templates with descriptions."
        ],
        "category": "Prompt Management"
    },
    "save prompt": {
        "description": "Save the last user message as a reusable prompt template.",
        "usage": "save prompt <name> [description]",
        "examples": [
            "save prompt story_helper - Save last prompt with default description.",
            "save prompt code_review A template for reviewing Python code - Save with custom description."
        ],
        "category": "Prompt Management"
    },
    "use prompt": {
        "description": "Load and use a saved prompt template.",
        "usage": "use prompt <name|index>",
        "examples": [
            "use prompt story_helper - Apply the story_helper template to your next message.",
            "use prompt 3 - Apply prompt with index 3."
        ],
        "category": "Prompt Management"
    },
    # Renaming 'roles' and 'instructions' to 'instructions' for consistency with InstructionManager
    "instructions": {
        "description": "List all saved instruction profiles (AI roles/behaviors).",
        "usage": "instructions | roles",
        "examples": [
            "instructions - Display all saved instruction profiles."
        ],
        "category": "Instruction Management"
    },
    "roles": { # Alias
        "description": "List all saved instruction profiles (AI roles/behaviors).",
        "usage": "roles | instructions",
        "examples": [
            "roles - Display all saved instruction profiles."
        ],
        "category": "Instruction Management"
    },
    "save instruction": {
        "description": "Save a system instruction profile for future use.",
        "usage": "save instruction <name> [description]",
        "examples": [
            "save instruction python_expert - Saves the instruction you enter.",
            "save instruction sql_tutor SQL expertise role - Saves with custom description."
        ],
        "category": "Instruction Management"
    },
    "use instruction": {
        "description": "Apply a saved instruction profile to the current session.",
        "usage": "use instruction <name|index>",
        "examples": [
            "use instruction python_expert - Apply the Python expert instruction.",
            "use instruction 3 - Apply instruction with index 3."
        ],
        "category": "Instruction Management"
    },
     "edit instruction": {
        "description": "Edit an existing instruction profile.",
        "usage": "edit instruction <name|index>",
        "examples": [
            "edit instruction python_expert"
        ],
        "category": "Instruction Management"
    },
    "clear instruction": {
        "description": "Remove the active system instruction.",
        "usage": "clear instruction | clear role",
        "examples": [
            "clear instruction - Return to default AI behavior."
        ],
        "category": "Instruction Management"
    },
    "show instruction": {
        "description": "Display the currently active system instruction.",
        "usage": "show instruction | show role",
        "examples": [
            "show instruction - See what instruction is currently active."
        ],
        "category": "Instruction Management"
    },
    "delete instruction": {
        "description": "Delete a saved instruction profile.",
        "usage": "delete instruction <name|index>",
        "examples": [
            "delete instruction python_expert - Delete the Python expert instruction profile."
        ],
        "category": "Instruction Management"
    },
    "show search method": {
        "description": "Display the current search method being used.",
        "usage": "show search method",
        "examples": [
            "show search method - See which search capability is active."
        ],
        "category": "Search"
    },
    "use cs": {
        "description": "Switch to custom Google search method.",
        "usage": "use cs",
        "examples": [
            "use cs - Enable custom search API for better control over search results."
        ],
        "category": "Search"
    },
    "use gs": {
        "description": "Switch to Vertex AI's native grounding capability.",
        "usage": "use gs",
        "examples": [
            "use gs - Enable Vertex AI's built-in search capabilities."
        ],
        "category": "Search"
    },
    "disable search": {
        "description": "Disable all search methods.",
        "usage": "disable search",
        "examples": [
            "disable search - Turn off all search functionality."
        ],
        "category": "Search"
    },
    "reset": {
        "description": "Clear the current conversation history and start a new chat session.",
        "usage": "reset",
        "examples": [
            "reset - Start a fresh conversation while maintaining settings."
        ],
        "category": "General"
    },
    "reset database": {
        "description": "Archive logs and reset the log database.",
        "usage": "reset database",
        "examples": [
            "reset database - Move all logs to archive folder and create a new database."
        ],
        "category": "General"
    },
    "textbox": {
        "description": "Open a flexible multiline text editor for writing structured content.",
        "usage": "textbox | wm",
        "examples": [
            "textbox - Open the multiline editor.",
            "wm - Shortcut to open the editor."
        ],
        "category": "Input" # New category
    },
    "lookup": {
        "description": "Perform a quick web search without affecting conversation history (uses Vertex Grounding).",
        "usage": "lookup <query> | ql <query>",
        "examples": [
            "lookup current weather in Berlin",
            "ql latest AI news"
        ],
        "category": "Search"
    },
    "ask": { # This was using standard Gemini model before, now it might be Vertex standard
        "description": "Ask a quick question without affecting conversation history (uses standard Vertex model).",
        "usage": "ask <query> | qg <query>",
        "examples": [
            "ask what is the capital of France",
            "qg explain quantum computing"
        ],
        "category": "AI Interaction" # New category
    },
    "edit log": { # Renamed from "edit description" for clarity
        "description": "Edit the description of a selected log file.",
        "usage": "edit log [index|filename]",
        "examples": [
            "edit log - Prompts to select a log and update its description.",
            "edit log 3",
            "edit log my_log.txt"
        ],
        "category": "Log Management"
    },
    "show context": {
        "description": "Display the current context window being sent to the AI (for debugging).",
        "usage": "show context",
        "examples": [
            "show context - Show conversation history and other contextual info."
        ],
        "category": "Debugging" # New category
    },
    "tag log": { # Replaces favorite/unfavorite with a more generic tagging
        "description": "Add or update a tag for a log file.",
        "usage": "tag log <index|filename> <tag_key> <tag_value>",
        "examples": [
            "tag log 3 status reviewed",
            "tag log my_log.txt project alpha"
        ],
        "category": "Log Management"
    },
    "view log": {
        "description": "View the contents of a log file without loading it into your active conversation.",
        "usage": "view log <index|filename>",
        "examples": [
            "view log 3 - View the conversation history in log with index 3.",
            "view log 2023-04-18_22-57-12.txt - View a specific log file."
        ],
        "category": "Log Management"
    },
    # Aliases for consistency or previous commands that are now changed
    "save role": { # Alias for "save instruction"
        "description": "Alias for 'save instruction'. Save a system instruction profile.",
        "usage": "save role <name> [description]",
        "examples": [ "save role python_expert" ],
        "category": "Instruction Management",
        "alias_for": "save instruction"
    },
     "use role": { # Alias for "use instruction"
        "description": "Alias for 'use instruction'. Apply a saved instruction profile.",
        "usage": "use role <name|index>",
        "examples": [ "use role python_expert" ],
        "category": "Instruction Management",
        "alias_for": "use instruction"
    },
    "clear role": { # Alias for "clear instruction"
        "description": "Alias for 'clear instruction'. Remove the active system instruction.",
        "usage": "clear role",
        "examples": [ "clear role" ],
        "category": "Instruction Management",
        "alias_for": "clear instruction"
    },
    "show role": { # Alias for "show instruction"
        "description": "Alias for 'show instruction'. Display the currently active system instruction.",
        "usage": "show role",
        "examples": [ "show role" ],
        "category": "Instruction Management",
        "alias_for": "show instruction"
    },
    "delete role": { # Alias for "delete instruction"
        "description": "Alias for 'delete instruction'. Delete a saved instruction profile.",
        "usage": "delete role <name|index>",
        "examples": [ "delete role python_expert" ],
        "category": "Instruction Management",
        "alias_for": "delete instruction"
    },
     "edit role": { # Alias for "edit instruction"
        "description": "Alias for 'edit instruction'. Edit an existing instruction profile.",
        "usage": "edit role <name|index>",
        "examples": [ "edit role python_expert" ],
        "category": "Instruction Management",
        "alias_for": "edit instruction"
    },
}
# Note: Some commands from original COMMAND_HELP like 'favorite', 'unfavorite', 
# 'edit description' (now 'edit log'), 'generate description' might be handled differently
# or integrated into other commands in the new structure.
# 'clear search context' and 'show search context' might be debug tools or less prominent.
# The category field is added to help structure the help display.
# Aliases are marked with 'alias_for' for clarity.
