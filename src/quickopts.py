"""Small option parser for README-style script docstrings."""

from __future__ import annotations

import dataclasses
import enum
import re
import sys
from collections.abc import Mapping, Sequence
from typing import Self


__all__ = ["ParseError", "Parsed", "parse"]


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
                if len(token) != 2:
                    raise ParseError(f"unknown option {token}")

                name = token[1]
                kind = self.options.get(name)
                if kind is None:
                    raise ParseError(f"unknown option -{name}")

                if kind is _Option.COMMAND:
                    if command is not None:
                        raise ParseError(f"multiple commands: -{command} and -{name}")
                    command = name
                elif kind is _Option.SWITCH:
                    switches.add(name)
                elif kind is _Option.FLAG:
                    index += 1
                    if index >= len(argv):
                        raise ParseError(f"missing value for -{name}")
                    flags[name] = argv[index]

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


def parse(doc: str, argv: Sequence[str] | None = None) -> Parsed:
    """Parse command-line arguments according to ``doc``.

    ``doc`` is scanned line by line. Section headers are lines such as
    ``Commands:`` and ``Options:``; a whitespace-only line ends the current
    section. In ``Commands:``, single-letter entries such as ``-C`` define
    commands. In ``Options:``, single-letter entries define either switches or
    flags. An option has a value when non-whitespace characters appear between
    the option name and the 2+ whitespace gap before the description; otherwise
    it is a switch.

    ``argv`` is parsed as command-line tokens without the program name. Commands
    set ``Parsed.command`` and only one may appear. Flags consume the following
    token as their value, switches are collected in ``Parsed.switches``, and
    non-option tokens are collected in ``Parsed.args``. ``--`` stops option
    parsing and sends the remaining tokens to ``Parsed.args``. When ``argv`` is
    omitted, ``sys.argv[1:]`` is parsed.
    """

    if argv is None:
        argv = sys.argv[1:]
    return _Parser.from_doc(doc).parse(argv)
