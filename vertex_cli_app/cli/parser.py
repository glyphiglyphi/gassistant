from typing import Optional, List, Tuple

class CLIParser:
    """
    Parses user input from the command line into commands and arguments.
    """

    def __init__(self):
        """
        Initializes the CLIParser.
        Currently, no specific initialization is needed.
        """
        # In the future, this could load known commands, aliases, etc.
        print("CLIParser initialized.")

    def parse_command(self, user_input: str) -> Tuple[Optional[str], Optional[List[str]], str]:
        """
        Parses the raw user input string into a command and its arguments.

        Args:
            user_input: The raw string input from the user.

        Returns:
            A tuple containing:
            - command (Optional[str]): The detected command (first word), or None if input is empty.
            - args_list (Optional[List[str]]): A list of arguments, or None if input is empty.
            - raw_user_input (str): The original user input string.
        """
        stripped_input = user_input.strip()
        if not stripped_input:
            return None, None, user_input # Return original input as raw

        parts = stripped_input.split()
        command = parts[0]
        args_list = parts[1:] if len(parts) > 1 else [] # Ensure args_list is empty list if no args
        
        return command, args_list, user_input


if __name__ == "__main__":
    parser = CLIParser()
    
    test_inputs = [
        "help",
        "load my_log.txt",
        "search what is AI?",
        "use prompt story_template --arg value",
        "complex command with many arguments here and there",
        "",
        "   leading and trailing spaces   "
    ]
    print("--- CLIParser Test ---")
    for ti in test_inputs:
        cmd, args, raw = parser.parse_command(ti)
        # For consistent test output, show raw as it was passed if cmd is None
        print(f"Input: '{raw if cmd else ti}' -> Command: {cmd}, Args: {args}")

    print("\n--- Test with specific examples from problem ---")
    example1 = "load my_log.txt --with-history"
    cmd, args, raw = parser.parse_command(example1)
    # Expected: command="load", args=["my_log.txt", "--with-history"]
    print(f"Input: '{raw}' -> Command: {cmd}, Args: {args}")
    assert cmd == "load"
    assert args == ["my_log.txt", "--with-history"]

    example2 = ""
    cmd, args, raw = parser.parse_command(example2)
    # Expected: command=None, args=None
    print(f"Input: '{example2}' -> Command: {cmd}, Args: {args}") # Show original empty string for clarity
    assert cmd is None
    assert args is None
    
    print("\nCLIParser Test Complete.")
