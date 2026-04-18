import pathlib
import sys
import unittest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import quickopts


DOC = """A cool tool

Synopsis:
  $prog [-L]
  $prog -C [-zb BRANCH]
  $prog -D VAL
  $prog -W [--] [ARGS...]

Commands:
  -C  Create a value.
  -D  Delete a value.
  -L  List all the values.
  -W  Wrap a command.
  -h  Show this message and exit.

Options:
  -b BRANCH  Name of the value's branch.
  -z         Sleep for a little while first.
"""


class ParseTest(unittest.TestCase):
    def test_parse_create_command_with_switch_and_flag(self):
        parsed = quickopts.parse(DOC, ["-C", "-z", "-b", "main"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"b": "main"}, parsed.flags)
        self.assertEqual(frozenset({"z"}), parsed.switches)
        self.assertEqual((), parsed.args)

    def test_parse_delete_command_with_positional_arg(self):
        parsed = quickopts.parse(DOC, ["-D", "value-id"])

        self.assertEqual("D", parsed.command)
        self.assertEqual(("value-id",), parsed.args)

    def test_parse_list_command(self):
        parsed = quickopts.parse(DOC, ["-L"])

        self.assertEqual("L", parsed.command)
        self.assertEqual({}, parsed.flags)
        self.assertEqual(frozenset(), parsed.switches)
        self.assertEqual((), parsed.args)

    def test_parse_help_command(self):
        parsed = quickopts.parse(DOC, ["-h"])

        self.assertEqual("h", parsed.command)

    def test_parse_wrap_command_with_double_dash(self):
        parsed = quickopts.parse(DOC, ["-W", "--", "-not-quickopts", "arg"])

        self.assertEqual("W", parsed.command)
        self.assertEqual(("-not-quickopts", "arg"), parsed.args)

    def test_parse_without_command(self):
        parsed = quickopts.parse(DOC, [])

        self.assertIsNone(parsed.command)
        self.assertEqual((), parsed.args)

    def test_repeated_flags_use_last_value(self):
        parsed = quickopts.parse(DOC, ["-b", "old", "-b", "new"])

        self.assertEqual({"b": "new"}, parsed.flags)

    def test_repeated_switches_are_deduplicated(self):
        parsed = quickopts.parse(DOC, ["-z", "-z"])

        self.assertEqual(frozenset({"z"}), parsed.switches)

    def test_positional_dash_after_double_dash(self):
        parsed = quickopts.parse(DOC, ["--", "-z", "arg"])

        self.assertEqual(("-z", "arg"), parsed.args)
        self.assertEqual(frozenset(), parsed.switches)

    def test_single_dash_is_positional_arg(self):
        parsed = quickopts.parse(DOC, ["-"])

        self.assertEqual(("-",), parsed.args)

    def test_missing_flag_value_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "missing value for -b"):
            quickopts.parse(DOC, ["-b"])

    def test_unknown_option_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "unknown option -x"):
            quickopts.parse(DOC, ["-x"])

    def test_grouped_option_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "unknown option -zb"):
            quickopts.parse(DOC, ["-zb"])

    def test_multiple_commands_raise(self):
        with self.assertRaisesRegex(quickopts.ParseError, "multiple commands"):
            quickopts.parse(DOC, ["-C", "-D"])

    def test_doc_parser_ignores_extra_prose_and_blank_lines(self):
        doc = """
Details before the sections.

Commands:
  -A  Alpha.

Options:
  -v  Verbose.
  -n NAME  Name.

More prose:
  -x  This is not an option section entry.
"""

        parsed = quickopts.parse(doc, ["-A", "-v", "-n", "Ada", "arg"])

        self.assertEqual("A", parsed.command)
        self.assertEqual({"n": "Ada"}, parsed.flags)
        self.assertEqual(frozenset({"v"}), parsed.switches)
        self.assertEqual(("arg",), parsed.args)

    def test_option_value_placeholder_can_use_arbitrary_non_space_characters(self):
        doc = """
Options:
  -p <path/to-file>  Path to write.
  -m mode=fast       Mode to use.
  -q                Quiet.
"""

        parsed = quickopts.parse(
            doc,
            ["-p", "/tmp/out.txt", "-m", "slow", "-q"],
        )

        self.assertEqual({"p": "/tmp/out.txt", "m": "slow"}, parsed.flags)
        self.assertEqual(frozenset({"q"}), parsed.switches)

    def test_option_value_is_detected_before_description_gap(self):
        doc = """
Options:
  -a VALUE  Has a value.
  -b        Has no value.
"""

        parsed = quickopts.parse(doc, ["-a", "one", "-b"])

        self.assertEqual({"a": "one"}, parsed.flags)
        self.assertEqual(frozenset({"b"}), parsed.switches)

    def test_blank_line_resets_current_section(self):
        doc = """Options:
  -a VALUE  Has a value.

  -b        This is outside the Options section.
"""

        parsed = quickopts.parse(doc, ["-a", "one"])

        self.assertEqual({"a": "one"}, parsed.flags)

        with self.assertRaisesRegex(quickopts.ParseError, "unknown option -b"):
            quickopts.parse(doc, ["-b"])

    def test_conflicting_option_definitions_raise_value_error(self):
        doc = """Commands:
  -x  Run.
Options:
  -x VALUE  Name.
"""

        with self.assertRaisesRegex(ValueError, "conflicting definitions"):
            quickopts.parse(doc, [])


if __name__ == "__main__":
    unittest.main()
