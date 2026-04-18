# `quickopts`

A tiny opinionated Python library for parsing script options.

## Quickstart

```python
"""A cool tool

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

import quickopts
import string
import sys


if __name__ == "__main__":
    try:
        q = quickopts.parse(__doc__)
    except quickopts.ParseError as err:
        print(err, file=sys.stderr)
        sys.exit(2)
    match q.command or "L":
        case "C":
            _create(branch=q.flags["b"], sleep="z" in q.switches)
        case "D":
            _delete(q.args[0])
        case "L": ...
        case "W": ...
        case "h": print(string.Template(__doc__).substitute(prog=sys.argv[0]))
```

## Implementation

```python
# Public API

class ParseError(Exception): ...

@dataclasses.dataclass
class Parsed(slots=True):
    command: str | None
    flags: Mapping[str, str]
    switches: frozenset[str]
    args: tuple[str, ...]

def parse(doc: str, argv: Sequence[str] | None = None) -> Parsed: ...

# Internals

class _Option(enum.Enum):
    COMMAND = enum.auto()
    FLAG = enum.auto()
    SWITCH = enum.auto()

class _Parser:
    options: Mapping[str, _Option]
    def parse(self, argv) -> Parsed: ...
```

The first version parses option definitions from the `Commands:` and `Options:`
sections. In `Options:`, an entry has a value when non-whitespace characters
appear between the option name and the 2+ whitespace gap before the description.
`Synopsis:` is descriptive and is not validated.

Folder structure:

```
src/quickopts.py
tests/test_quickopts.py
pyproject.toml
```
