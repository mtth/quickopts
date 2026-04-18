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


__all__ = ["ParseError", "Parsed", "parse", "parse_or_exit"]


class ParseError(Exception):
    """Raised when command-line arguments cannot be parsed."""


@dataclasses.dataclass(frozen=True, slots=True)
class Parsed:
    command: str | None
    flags: Mapping[str, str]
    switches: frozenset[str]
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
        flags: dict[str, str] = {}
        switches: set[str] = set()
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
                        switches.add(name)
                    elif kind is _Option.FLAG:
                        value = token[token_index + 1 :]
                        if value:
                            flags[name] = value
                        else:
                            index += 1
                            if index >= len(argv):
                                raise ParseError(f"missing value for -{name}")
                            flags[name] = argv[index]
                        break

                    token_index += 1

                index += 1
                continue

            args.append(token)
            index += 1

        return Parsed(
            command=command,
            flags=flags,
            switches=frozenset(switches),
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
    set ``Parsed.command`` and only one may appear. Switches are collected in
    ``Parsed.switches``. Single-dash option tokens may contain clusters such as
    ``-abc``. When a flag appears in a cluster, it consumes the rest of that
    token as its value; if no characters remain, it consumes the following arg.
    Non-option tokens are collected in ``Parsed.args``. ``--`` stops option
    parsing and sends the remaining tokens to ``Parsed.args``.
    """

    return _Parser.from_doc(doc).parse(args)


def parse_or_exit(
    doc: str,
    *,
    help_command: str | None = "h",
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
    code 0. When ``program_var`` is set, its value in the docstring is replaced
    with the display program name before printing.

    ``_argv`` and ``_exit`` are internal hooks for tests.
    """
    argv = sys.argv if _argv is None else _argv
    arg0, *args = argv
    prog = Path(arg0).name
    try:
        q = parse(doc, args)
    except ParseError as err:
        print(f"{prog}: {err}", file=sys.stderr)
        _exit(2)
    else:
        if help_command and q.command == help_command:
            subs = {program_var: prog} if program_var else {}
            print(string.Template(doc).substitute(**subs) if subs else doc)
            _exit(0)
        else:
            return q
