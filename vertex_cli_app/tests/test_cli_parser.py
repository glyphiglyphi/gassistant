# vertex_cli_app/tests/test_cli_parser.py
import unittest
from cli.parser import CLIParser # Assumes it's discoverable (run_tests.py handles path)

class TestCLIParser(unittest.TestCase):
    def setUp(self):
        self.parser = CLIParser()

    def test_parse_simple_command(self):
        cmd, args, raw = self.parser.parse_command("help")
        self.assertEqual(cmd, "help")
        self.assertEqual(args, [])
        self.assertEqual(raw, "help")

    def test_parse_command_with_args(self):
        cmd, args, raw = self.parser.parse_command("load my_log.txt --fast")
        self.assertEqual(cmd, "load")
        self.assertEqual(args, ["my_log.txt", "--fast"]) # Adjusted expectation
        self.assertEqual(raw, "load my_log.txt --fast")

    def test_parse_command_with_quoted_args(self):
        cmd, args, raw = self.parser.parse_command('save prompt my_prompt "This is a description"')
        self.assertEqual(cmd, "save")
        self.assertEqual(args, ["prompt", "my_prompt", "This is a description"])
        self.assertEqual(raw, 'save prompt my_prompt "This is a description"')

    def test_parse_empty_input(self):
        cmd, args, raw = self.parser.parse_command("")
        self.assertIsNone(cmd)
        self.assertEqual(args, []) # CLIParser.parse_command returns empty list for args on empty cmd
        self.assertEqual(raw, "")
        
    def test_parse_input_with_only_spaces(self):
        cmd, args, raw = self.parser.parse_command("   ")
        self.assertIsNone(cmd) 
        self.assertEqual(args, []) # CLIParser.parse_command returns empty list for args on empty cmd
        self.assertEqual(raw, "   ")

    def test_parse_prompt_input(self):
        # Test input that is not a command, should be treated as a prompt
        prompt_text = "This is a test prompt, not a command."
        cmd, args, raw = self.parser.parse_command(prompt_text)
        self.assertIsNone(cmd) # No command, just raw input
        self.assertEqual(args, [])
        self.assertEqual(raw, prompt_text)

    def test_parse_command_with_leading_spaces(self):
        cmd, args, raw = self.parser.parse_command("  help  ")
        self.assertEqual(cmd, "help")
        self.assertEqual(args, [])
        self.assertEqual(raw, "  help  ")

if __name__ == '__main__':
    unittest.main()
