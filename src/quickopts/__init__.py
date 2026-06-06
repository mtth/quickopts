"""Tiny option parser for README-style script docstrings."""

from __future__ import annotations

import dataclasses
import enum
from pathlib import Path
import re
import string
import sys
from collections.abc import Mapping, Sequence
from typing import Self


__all__ = ["ParseError", "Parsed", "Placeholder", "parse", "parse_or_exit"]


class ParseError(Exception):
    """Raised when command-line arguments cannot be parsed."""


class Placeholder(enum.Enum):
    """Built-in template values resolved by ``parse_or_exit``."""

    PROGRAM = enum.auto()
    """The display program name derived from ``argv[0]``."""


@dataclasses.dataclass(frozen=True, slots=True)
class Parsed:
    """Command, option, and positional arguments parsed from a command line."""

    command: str | None
    flags: Mapping[str, tuple[str, ...]]
    switches: Mapping[str, int]
    args: tuple[str, ...]


class _Option(enum.Enum):
    COMMAND = enum.auto()
    FLAG = enum.auto()
    SWITCH = enum.auto()


class _Parser:
    _ENTRY_RE = re.compile(r"^\s+-([A-Za-z0-9])(?P<body>.*)$")
    _SECTION_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*):\s*$")
    _DESCRIPTION_GAP_RE = re.compile(r"\s{2,}")

    def __init__(self, options: Mapping[str, _Option]) -> None:
        self.options = options

    @classmethod
    def from_doc(cls, doc: str) -> Self:
        options: dict[str, _Option] = {}
        section: str | None = None

        for line in doc.splitlines():
            if not line.strip():
                section = None
                continue

            section_match = cls._SECTION_RE.match(line)
            if section_match:
                section = section_match.group(1)
                continue

            if section not in {"Commands", "Options"}:
                continue

            entry_match = cls._ENTRY_RE.match(line)
            if not entry_match:
                continue

            name = entry_match.group(1)
            if section == "Commands":
                kind = _Option.COMMAND
            else:
                kind = cls._option_kind(entry_match.group("body"))

            previous = options.get(name)
            if previous is not None and previous is not kind:
                raise ValueError(f"conflicting definitions for -{name}")
            options[name] = kind

        return cls(options)

    @classmethod
    def _option_kind(cls, body: str) -> _Option:
        value_part = cls._DESCRIPTION_GAP_RE.split(body, maxsplit=1)[0]
        if value_part.strip():
            return _Option.FLAG
        return _Option.SWITCH

    def parse(self, argv: Sequence[str]) -> Parsed:
        command: str | None = None
        flags: dict[str, list[str]] = {}
        switches: dict[str, int] = {}
        args: list[str] = []
        parsing_options = True

        index = 0
        while index < len(argv):
            token = argv[index]

            if parsing_options and token == "--":
                parsing_options = False
                index += 1
                continue

            if parsing_options and token.startswith("-") and token != "-":
                token_index = 1
                while token_index < len(token):
                    name = token[token_index]
                    kind = self.options.get(name)
                    if kind is None:
                        raise ParseError(f"unknown option -{name}")

                    if kind is _Option.COMMAND:
                        if command is not None:
                            raise ParseError(
                                f"multiple commands: -{command} and -{name}"
                            )
                        command = name
                    elif kind is _Option.SWITCH:
                        switches[name] = switches.get(name, 0) + 1
                    elif kind is _Option.FLAG:
                        value = token[token_index + 1 :]
                        if value:
                            flags.setdefault(name, []).append(value)
                        else:
                            index += 1
                            if index >= len(argv):
                                raise ParseError(f"missing value for -{name}")
                            flags.setdefault(name, []).append(argv[index])
                        break

                    token_index += 1

                index += 1
                continue

            args.extend(argv[index:])
            break

        return Parsed(
            command=command,
            flags={name: tuple(values) for name, values in flags.items()},
            switches=switches,
            args=tuple(args),
        )


def parse(doc: str, args: Sequence[str]) -> Parsed:
    """Parse command-line arguments according to ``doc``.

    ``doc`` is scanned line by line. Section headers are lines such as
    ``Commands:`` and ``Options:``; a whitespace-only line ends the current
    section. In ``Commands:``, single-letter entries such as ``-C`` define
    commands. In ``Options:``, single-letter entries define either switches or
    flags. An option has a value when non-whitespace characters appear between
    the option name and the 2+ whitespace gap before the description; otherwise
    it is a switch.

    ``args`` is parsed as command-line tokens without the program name. Commands
    set ``Parsed.command`` and only one may appear. Switch repeat counts are
    collected in ``Parsed.switches``. Flag values are collected in
    ``Parsed.flags`` tuples. Single-dash option tokens may contain clusters such
    as ``-abc``. When a flag appears in a cluster, it consumes the rest of that
    token as its value; if no characters remain, it consumes the following arg.
    The first non-option token stops option parsing, and that token plus all
    remaining tokens are collected in ``Parsed.args``. ``--`` also stops option
    parsing and sends the remaining tokens to ``Parsed.args``.
    """

    return _Parser.from_doc(doc).parse(args)


def parse_or_exit(
    doc: str,
    *,
    help_command: str | None = "h",
    template_mapping: Mapping[str, str | Placeholder] | None = None,
    program_var: str | None = None,
    _argv: Sequence[str] | None = None,
    _exit = sys.exit,
) -> Parsed:
    """Parse command-line arguments or exit with code 2.

    This is a convenience wrapper around ``parse`` for scripts. It reads
    ``sys.argv`` as a full command-line vector, uses ``argv[0]``'s basename as
    the display program name, and parses the remaining tokens as args.

    If parsing raises ``ParseError``, the error message is prefixed with the
    program name, printed to standard error, and the process exits with status
    code 2.

    If ``help_command`` is not ``None`` and the parsed command matches it, the
    docstring is printed to standard output and the process exits with status
    code 0. ``template_mapping`` is passed to ``string.Template.substitute``
    before printing, after replacing ``Placeholder`` values with their runtime
    values. ``program_var`` is a legacy shortcut for mapping a template variable
    to ``Placeholder.PROGRAM``.

    ``_argv`` and ``_exit`` are internal hooks for tests.
    """
    argv = sys.argv if _argv is None else _argv
    arg0, *args = argv
    prog = _display_program(arg0) if _argv is None else Path(arg0).name
    try:
        q = parse(doc, args)
    except ParseError as err:
        print(f"{prog}: {err}", file=sys.stderr)
        _exit(2)
    else:
        if help_command and q.command == help_command:
            mapping = dict(template_mapping or {})
            if program_var is not None:
                mapping.setdefault(program_var, Placeholder.PROGRAM)
            if mapping or template_mapping is not None:

                def render(v: Placeholder | str) -> str:
                    match v:
                        case str():
                            return v
                        case Placeholder.PROGRAM:
                            return prog
                        case _:
                            raise ValueError(f"unknown placeholder: {v}")

                rendered = {k: render(v) for k, v in mapping.items()}
                help_msg = string.Template(doc).substitute(rendered)
            else:
                help_msg = doc
            print(help_msg)
            _exit(0)
        else:
            return q


def _display_program(arg0: str) -> str:
    orig_argv = getattr(sys, "orig_argv", ())
    try:
        module_flag = orig_argv.index("-m")
        module = orig_argv[module_flag + 1]
    except (ValueError, IndexError):
        return Path(arg0).name
    return f"{Path(orig_argv[0]).name} -m {module}"
