from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.theme import Theme
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession, Application
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.containers import FloatContainer
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.markup import MarkdownLexer
import re

# Import COMMAND_HELP from the new location
from .command_help import COMMAND_HELP


class UIRenderer:
    """
    Handles UI rendering for the CLI application, including user input and output display.
    """

    def __init__(self):
        MATRIX_GREEN = "#00FF00" 
        custom_theme_data = {
            "markdown.text": MATRIX_GREEN,
            "markdown.paragraph": MATRIX_GREEN,
            "markdown.code": "bold white", 
            "markdown.link": f"{MATRIX_GREEN} underline",
            "markdown.list": MATRIX_GREEN,
            "prompt.text": MATRIX_GREEN,
            "panel.border": "cyan",
            "table.header": "bold cyan",
            "table.cell": MATRIX_GREEN, # Default cell style
            "help.command.name": "bold cyan",
            "help.category.title": "bold yellow",
            "help.usage": "yellow",
            "help.description": "white",
            "help.example": MATRIX_GREEN,
        }
        custom_theme = Theme(custom_theme_data)
        self.console = Console(theme=custom_theme, highlight=False)

        prompt_style = PromptStyle.from_dict({
            '': MATRIX_GREEN,
            'prompt': f'bold {MATRIX_GREEN}', 
        })
        self.prompt_session = PromptSession(style=prompt_style)
        print("UIRenderer initialized.")

    def get_user_input(self, prompt_message: str = "You: ") -> str:
        styled_prompt_message = HTML(f'<prompt>{prompt_message}</prompt>')
        try:
            return self.prompt_session.prompt(styled_prompt_message)
        except EOFError:
            return "exit"
        except KeyboardInterrupt:
             return "exit"

    def display_message(self, message: str, style: Optional[str] = None):
        default_style_key = "markdown.text" # Using a key from our theme
        self.console.print(message, style=style if style else default_style_key)

    def display_markdown(self, text: str, code_theme: str = "monokai"):
        md = Markdown(text, code_theme=code_theme, style="markdown.paragraph") # Apply base paragraph style
        self.console.print(md)

    def display_panel(self, content: Any, title: Optional[str] = None, border_style: Optional[str] = None):
        final_border_style = border_style if border_style else self.console.theme.styles.get("panel.border", "cyan")
        self.console.print(Panel(content, title=title, border_style=final_border_style, expand=False))

    def display_table(self, title: str, columns: List[Dict[str, Any]], rows: List[List[Any]]):
        table = Table(title=title, title_style=self.console.theme.styles.get("table.header", "bold white"))
        default_cell_style = self.console.theme.styles.get("table.cell", "white")
        for col_data in columns:
            header_style = col_data.get("style", self.console.theme.styles.get("table.header", "white"))
            # Use a specific cell style if provided per column, else default
            cell_style_for_col = col_data.get("cell_style", default_cell_style) 
            table.add_column(
                col_data.get("header", ""), 
                style=header_style, 
                justify=col_data.get("justify", "left"),
                style_for_cells=cell_style_for_col # This might not be a direct Table.add_column param, applied row-wise if needed
            )
        for row in rows:
            processed_row = [str(item) if not isinstance(item, Text) else item for item in row]
            # Apply cell styles here if not directly supported by add_column or if more control is needed
            table.add_row(*processed_row) # Rich handles styling of individual cells if `Text` objects with styles are passed
        self.console.print(table)

    def display_main_help_table(self):
        """
        Displays the main help table, categorized by command functionality.
        """
        # Group commands by category
        categorized_commands: Dict[str, List[Dict[str, Any]]] = {}
        for cmd_name, cmd_info in COMMAND_HELP.items():
            if cmd_info.get("alias_for"): # Skip aliases in main help table
                continue
            category = cmd_info.get("category", "General")
            if category not in categorized_commands:
                categorized_commands[category] = []
            categorized_commands[category].append({"name": cmd_name, "info": cmd_info})

        # Define preferred category order
        category_order = ["General", "AI Interaction", "Search", "Log Management", "Prompt Management", "Instruction Management", "Input", "Debugging"]
        
        help_table = Table(title="[bold magenta]Available Commands[/bold magenta]", expand=True, show_lines=False)
        help_table.add_column("Command", style="help.command.name", width=30)
        help_table.add_column("Description", style="help.description")

        for category in category_order:
            if category in categorized_commands:
                help_table.add_row("") # Spacer row
                help_table.add_row(f"[{self.console.theme.styles.get('help.category.title', 'bold yellow')}]{category}[/]", style=self.console.theme.styles.get('help.category.title', 'bold yellow'))
                for cmd_item in sorted(categorized_commands[category], key=lambda x: x["name"]):
                    cmd_name = cmd_item["name"]
                    cmd_info = cmd_item["info"]
                    # Display usage for commands that have simple usage, or just name
                    usage_display = cmd_info.get('usage', cmd_name).split('|')[0].strip() # Show primary usage
                    help_table.add_row(usage_display, cmd_info.get('description', ''))
        
        self.console.print(help_table)
        self.console.print("Type 'help <command>' for more details on a specific command.", style="italic yellow")

    def display_specific_command_help(self, command: str) -> bool:
        cmd_info = COMMAND_HELP.get(command)
        # Handle aliases correctly
        is_alias = False
        if cmd_info and cmd_info.get("alias_for"):
            actual_command_name = cmd_info["alias_for"]
            main_cmd_info = COMMAND_HELP.get(actual_command_name)
            if not main_cmd_info: # Should not happen if alias is set up correctly
                self.display_message(f"Alias '{command}' points to non-existent command '{actual_command_name}'.", style="bold red")
                return False
            cmd_info = main_cmd_info # Use the main command's info
            is_alias = True
        elif not cmd_info: # If not an alias and not found directly
             self.display_message(f"No help available for command: {command}", style="bold red")
             return False

        # At this point, cmd_info is for the main command
        title_command_name = command if not is_alias else f"{command} (alias for {cmd_info.get('usage', '').split('|')[0].strip()})"
        title = f"[bold magenta]Help: {title_command_name}[/bold magenta]"
            
        description = Text(cmd_info.get('description', 'No description available.'), style=self.console.theme.styles.get("help.description", "white"))
        usage = Text(f"\nUsage:\n  {cmd_info.get('usage', 'N/A')}", style=self.console.theme.styles.get("help.usage", "yellow"))
            
        examples_text = Text("\nExamples:\n", style="bold white")
        for ex in cmd_info.get('examples', []):
            examples_text.append(f"  • {ex}\n", style=self.console.theme.styles.get("help.example", "green"))

        panel_content = Text.assemble(description, usage, examples_text)
        self.display_panel(panel_content, title=title, border_style=self.console.theme.styles.get("panel.border", "cyan"))
        return True

    def display_logs(self, logs_data: List[Dict[str, Any]]):
        """
        Displays log entries in a formatted table.
        Sorts logs by date (newest first) and assigns 1-based index for display.
        """
        if not logs_data:
            self.display_message("No logs found.", style="yellow")
            return

        # Sort logs by 'filesystem_created_date' (newest first) for display consistency.
        # The LogDatabase.get_all_log_entries already sorts this way.
        # Assign 1-based index for display
        # logs_data is already sorted newest first by LogDatabase.get_all_log_entries
        
        table = Table(title="[bold magenta]Conversation Logs[/bold magenta]", expand=True)
        table.add_column("Index", style="bright_cyan", justify="right", width=5)
        table.add_column("Filename", style="cyan", min_width=25, overflow="fold")
        table.add_column("Size (KB)", justify="right", style="magenta", width=10)
        table.add_column("Description", style="white", min_width=30, overflow="fold")
        table.add_column("Tags", style="yellow", min_width=15, overflow="fold")
        table.add_column("Created Date", style="dim", width=20)

        for idx, log_entry in enumerate(logs_data, 1):
            table.add_row(
                str(idx),
                log_entry.get("filename", "N/A"),
                f"{log_entry.get('size_kb', 0):.1f}",
                log_entry.get("description", "No description"),
                log_entry.get("tags", ""),
                log_entry.get("filesystem_created_date", "Unknown")
            )
        self.console.print(table)

    def display_prompts(self, prompts_data: List[Dict[str, Any]]):
        """
        Displays prompt templates in a formatted table.
        Prompts are assumed to be sorted (e.g., newest first) by PromptManager.
        """
        if not prompts_data:
            self.display_message("No prompts found.", style="yellow")
            return

        table = Table(title="[bold magenta]Saved Prompt Templates[/bold magenta]", expand=True)
        table.add_column("Index", style="bright_cyan", justify="right", width=5)
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("Description", style="white", min_width=30, overflow="fold")
        table.add_column("Created", style="dim", width=20)

        # Prompts are sorted newest first by PromptManager.get_all_prompts
        for idx, prompt_info in enumerate(prompts_data, 1):
            table.add_row(
                str(idx),
                prompt_info.get("name", "N/A"),
                prompt_info.get("description", "No description"),
                prompt_info.get("created", "Unknown")
            )
        self.console.print(table)

    def display_instructions(self, instructions_data: List[Dict[str, Any]]):
        """
        Displays instruction profiles in a formatted table.
        Instructions are assumed to be sorted (e.g., oldest first by default) by InstructionManager.
        The display will show newest first by reversing the list and adjusting index.
        """
        if not instructions_data:
            self.display_message("No instruction profiles found.", style="yellow")
            return
        
        table = Table(title="[bold magenta]Saved Instruction Profiles (Roles)[/bold magenta]", expand=True)
        table.add_column("Index", style="bright_cyan", justify="right", width=5)
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("Description", style="white", min_width=30, overflow="fold")
        table.add_column("Created", style="dim", width=20)
        table.add_column("Last Used", style="dim", width=20)

        # InstructionManager.list_instruction_profiles sorts oldest first.
        # For display, usually newest first is preferred.
        # So, we iterate in reverse and calculate index accordingly.
        num_items = len(instructions_data)
        for i, instr_info in enumerate(reversed(instructions_data)):
            display_idx = num_items - i
            table.add_row(
                str(display_idx),
                instr_info.get("name", "N/A"),
                instr_info.get("description", "No description"),
                instr_info.get("created", "Unknown"),
                instr_info.get("last_used", "Never")
            )
        self.console.print(table)

    def get_multiline_input(self, prompt_message: str = "Enter text (Ctrl+D or ESC then Enter to finish):",
                            default_text: Optional[str] = None) -> Optional[str]:
        clean_prompt = re.sub(r'\x1b\[[0-9;]*m', '', prompt_message)
        result = [None]
        kb = KeyBindings()
        @kb.add('c-d')
        @kb.add('escape', 'enter')
        def _(event): result[0] = event.app.current_buffer.text; event.app.exit()
        @kb.add('c-c')
        def _(event): result[0] = None; event.app.exit()

        text_area = TextArea(lexer=PygmentsLexer(MarkdownLexer), scrollbar=True, line_numbers=True, wrap_lines=True, focus_on_click=True, text=default_text if default_text is not None else "")
        help_text_control = FormattedTextControl([("class:help", " Ctrl+D or ESC+ENTER: Save & Exit | Ctrl+C: Cancel ")])
        
        ptk_style = PromptStyle.from_dict({'help': 'bg:#333333 #ffffff', 'frame.border': '#888888'})

        application = Application(
            layout=Layout(HSplit([
                Frame(body=Window(content=FormattedTextControl(text=clean_prompt)), style='class:frame.border'),
                Frame(text_area, style='class:frame.border'),
                Window(height=1, content=help_text_control, style='class:help'),
            ])),
            key_bindings=kb, mouse_support=True, full_screen=True, style=ptk_style
        )
        application.run()

        if result[0] is not None:
            self.console.print("\n--- Your submitted text ---", style="bold cyan")
            self.display_markdown(result[0])
            self.console.print("-------------------------", style="bold cyan")
        else:
            self.display_message("Multiline input cancelled.", style="italic yellow")
        return result[0]

if __name__ == "__main__":
    ui = UIRenderer()
    ui.display_message("Hello from UIRenderer!", style="bold green")
    ui.display_markdown("## This is Markdown\n* Bullet 1\n* Bullet 2\n```python\nprint('Hello')\n```")
    
    cols = [{"header": "Name", "style": "cyan"}, {"header": "Value", "style": "magenta"}]
    rws = [["Item 1", "10"], ["Item 2", "20"]]
    ui.display_table("Test Table", cols, rws)
    ui.display_panel("This is some panel content.", title="Important Info", border_style="green")

    print("\n--- Help Display Test ---")
    ui.display_main_help_table()
    print("\n--- Specific Command Help (search) ---")
    ui.display_specific_command_help("search")
    print("\n--- Specific Command Help (nonexistent) ---")
    ui.display_specific_command_help("blahblah")
    print("\n--- Specific Command Help (exit alias) ---")
    ui.display_specific_command_help("quit")


    print("\n--- Placeholder List Displays ---")
    dummy_logs = [{"filename": "log1.txt", "description": "Test log", "tags": "fav", "filesystem_created_date": "2023-01-01"}, {"filename": "log2.txt", "description": "Another", "tags": "", "filesystem_created_date": "2023-01-02"}]
    ui.display_logs(dummy_logs)
    dummy_prompts = [{"name": "p1", "description": "Prompt 1", "created": "2023-01-01"}, {"name": "p2", "description": "Prompt 2", "created": "2023-01-02"}]
    ui.display_prompts(dummy_prompts)
    dummy_instructions = [{"name": "role1", "description": "Be helpful", "created": "2023-01-01", "last_used": "Never"}]
    ui.display_instructions(dummy_instructions)
    
    # Interactive tests remain commented out
    # name = ui.get_user_input("Enter your name: ")
    # if name != "exit":
    #     ui.display_message(f"Hello, {name}!")
    # multiline_text = ui.get_multiline_input("Enter some long text (Ctrl+D or ESC then Enter to save):")
    # if multiline_text is not None:
    #    ui.display_markdown(f"### You entered:\n{multiline_text}")
    
    print("\nUIRenderer Test Complete. Interactive tests are commented out.")
