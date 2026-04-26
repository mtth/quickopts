import contextlib
import io
import pathlib
import sys
import unittest
import unittest.mock


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
        self.assertEqual({"z": 1}, parsed.switches)
        self.assertEqual((), parsed.args)

    def test_parse_delete_command_with_positional_arg(self):
        parsed = quickopts.parse(DOC, ["-D", "value-id"])

        self.assertEqual("D", parsed.command)
        self.assertEqual(("value-id",), parsed.args)

    def test_parse_list_command(self):
        parsed = quickopts.parse(DOC, ["-L"])

        self.assertEqual("L", parsed.command)
        self.assertEqual({}, parsed.flags)
        self.assertEqual({}, parsed.switches)
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

    def test_repeated_switches_are_counted(self):
        parsed = quickopts.parse(DOC, ["-z", "-z"])

        self.assertEqual({"z": 2}, parsed.switches)

    def test_switch_mapping_supports_key_membership(self):
        parsed = quickopts.parse(DOC, ["-z"])

        self.assertIn("z", parsed.switches)
        self.assertNotIn("x", parsed.switches)

    def test_positional_dash_after_double_dash(self):
        parsed = quickopts.parse(DOC, ["--", "-z", "arg"])

        self.assertEqual(("-z", "arg"), parsed.args)
        self.assertEqual({}, parsed.switches)

    def test_clustered_options_after_double_dash_are_positional(self):
        parsed = quickopts.parse(DOC, ["--", "-Cz"])

        self.assertIsNone(parsed.command)
        self.assertEqual(("-Cz",), parsed.args)

    def test_single_dash_is_positional_arg(self):
        parsed = quickopts.parse(DOC, ["-"])

        self.assertEqual(("-",), parsed.args)

    def test_first_positional_arg_stops_option_parsing(self):
        parsed = quickopts.parse(DOC, ["pos", "-z", "-b", "main"])

        self.assertEqual({}, parsed.switches)
        self.assertEqual({}, parsed.flags)
        self.assertEqual(("pos", "-z", "-b", "main"), parsed.args)

    def test_missing_flag_value_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "missing value for -b"):
            quickopts.parse(DOC, ["-b"])

    def test_unknown_option_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "unknown option -x"):
            quickopts.parse(DOC, ["-x"])

    def test_clustered_command_and_switch(self):
        parsed = quickopts.parse(DOC, ["-Cz"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"z": 1}, parsed.switches)

    def test_clustered_repeated_switches_are_counted(self):
        parsed = quickopts.parse(DOC, ["-zz"])

        self.assertEqual({"z": 2}, parsed.switches)

    def test_clustered_command_and_repeated_switches_are_counted(self):
        parsed = quickopts.parse(DOC, ["-Czz"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"z": 2}, parsed.switches)

    def test_clustered_command_and_flag_with_next_token_value(self):
        parsed = quickopts.parse(DOC, ["-Cb", "main"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"b": "main"}, parsed.flags)

    def test_clustered_command_switch_and_flag_with_attached_value(self):
        parsed = quickopts.parse(DOC, ["-Czbmain"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"z": 1}, parsed.switches)
        self.assertEqual({"b": "main"}, parsed.flags)

    def test_flag_consumes_rest_of_cluster_as_value(self):
        doc = """
Commands:
  -C  Create.
Options:
  -a VALUE  Value.
  -b        Switch.
  -c        Switch.
"""

        parsed = quickopts.parse(doc, ["-Cabc"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"a": "bc"}, parsed.flags)
        self.assertEqual({}, parsed.switches)

    def test_unknown_option_inside_cluster_raises(self):
        with self.assertRaisesRegex(quickopts.ParseError, "unknown option -x"):
            quickopts.parse(DOC, ["-Czx"])

    def test_multiple_commands_raise(self):
        with self.assertRaisesRegex(quickopts.ParseError, "multiple commands"):
            quickopts.parse(DOC, ["-C", "-D"])

    def test_multiple_commands_inside_cluster_raise(self):
        with self.assertRaisesRegex(quickopts.ParseError, "multiple commands"):
            quickopts.parse(DOC, ["-CD"])

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
        self.assertEqual({"v": 1}, parsed.switches)
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
        self.assertEqual({"q": 1}, parsed.switches)

    def test_option_value_is_detected_before_description_gap(self):
        doc = """
Options:
  -a VALUE  Has a value.
  -b        Has no value.
"""

        parsed = quickopts.parse(doc, ["-a", "one", "-b"])

        self.assertEqual({"a": "one"}, parsed.flags)
        self.assertEqual({"b": 1}, parsed.switches)

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

    def test_parse_or_exit_returns_parsed_args(self):
        parsed = quickopts.parse_or_exit(DOC, _argv=["tool", "-C", "-b", "main"])

        self.assertEqual("C", parsed.command)
        self.assertEqual({"b": "main"}, parsed.flags)

    def test_parse_or_exit_prints_error_and_exits_with_code_2(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                quickopts.parse_or_exit(DOC, _argv=["tool", "-x"])

        self.assertEqual(2, raised.exception.code)
        self.assertEqual("tool: unknown option -x\n", stderr.getvalue())

    def test_parse_or_exit_prints_help_and_exits_with_code_0(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                quickopts.parse_or_exit(DOC, program_var="prog", _argv=["tool", "-h"])

        self.assertEqual(0, raised.exception.code)
        self.assertIn("tool [-L]", stdout.getvalue())

    def test_parse_or_exit_template_mapping_supports_program_placeholder(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                quickopts.parse_or_exit(
                    DOC,
                    template_mapping={"prog": quickopts.Placeholder.PROGRAM},
                    _argv=["tool", "-h"],
                )

        self.assertEqual(0, raised.exception.code)
        self.assertIn("tool [-L]", stdout.getvalue())

    def test_parse_or_exit_template_program_uses_module_invocation(self):
        stdout = io.StringIO()

        with unittest.mock.patch.object(sys, "argv", ["/path/foo/bar.py", "-h"]):
            with unittest.mock.patch.object(
                sys,
                "orig_argv",
                ["python", "-m", "foo.bar", "-h"],
                create=True,
            ):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as raised:
                        quickopts.parse_or_exit(
                            DOC,
                            template_mapping={"prog": quickopts.Placeholder.PROGRAM},
                        )

        self.assertEqual(0, raised.exception.code)
        self.assertIn("python -m foo.bar [-L]", stdout.getvalue())

    def test_parse_or_exit_template_program_uses_package_module_invocation(self):
        stdout = io.StringIO()

        with unittest.mock.patch.object(sys, "argv", ["/path/foo/__main__.py", "-h"]):
            with unittest.mock.patch.object(
                sys,
                "orig_argv",
                ["python", "-m", "foo", "-h"],
                create=True,
            ):
                with contextlib.redirect_stdout(stdout):
                    with self.assertRaises(SystemExit) as raised:
                        quickopts.parse_or_exit(
                            DOC,
                            template_mapping={"prog": quickopts.Placeholder.PROGRAM},
                        )

        self.assertEqual(0, raised.exception.code)
        self.assertIn("python -m foo [-L]", stdout.getvalue())

    def test_parse_or_exit_error_uses_module_invocation(self):
        stderr = io.StringIO()

        with unittest.mock.patch.object(sys, "argv", ["/path/foo/bar.py", "-x"]):
            with unittest.mock.patch.object(
                sys,
                "orig_argv",
                ["python", "-m", "foo.bar", "-x"],
                create=True,
            ):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as raised:
                        quickopts.parse_or_exit(DOC)

        self.assertEqual(2, raised.exception.code)
        self.assertEqual("python -m foo.bar: unknown option -x\n", stderr.getvalue())

    def test_parse_or_exit_template_mapping_supports_literal_strings(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                quickopts.parse_or_exit(
                    DOC,
                    template_mapping={"prog": "custom-tool"},
                    _argv=["tool", "-h"],
                )

        self.assertEqual(0, raised.exception.code)
        self.assertIn("custom-tool [-L]", stdout.getvalue())

    def test_parse_or_exit_template_mapping_takes_precedence_over_program_var(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as raised:
                quickopts.parse_or_exit(
                    DOC,
                    template_mapping={"prog": "custom-tool"},
                    program_var="prog",
                    _argv=["tool", "-h"],
                )

        self.assertEqual(0, raised.exception.code)
        self.assertIn("custom-tool [-L]", stdout.getvalue())
        self.assertNotIn("  tool [-L]", stdout.getvalue())

    def test_parse_or_exit_template_mapping_uses_strict_substitution(self):
        with self.assertRaises(KeyError):
            quickopts.parse_or_exit(
                "$missing\n\nCommands:\n  -h  Show help.\n",
                template_mapping={},
                _argv=["tool", "-h"],
            )


if __name__ == "__main__":
    unittest.main()
