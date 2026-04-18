# `quickopts`

A small opinionated Python library for parsing script options.

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
    q = quickopts.parse(__doc__)
    match q.command or "L":
        case "C":
            _create(branch=q.flags["b"], sleep="z" in q.switches)
        case "D":
            _delete(q.args[0])
        case "L": ...
        case "W": ...
        case "h": print(string.Template(__doc__).format(prog=sys.argv[0]))
```

## Implementation

```python
# Public API

@dataclasses.dataclass
class Parsed(slots=True):
    command: str | None
    flags: Mapping[str, str]
    switches: frozenset[str]

def parse(doc: str, argv=sys.argv) -> Parsed: ...

# Internals

class _Option(enum):
    COMMAND = enum.auto()
    FLAG = enum.auto()
    SWITCH = enum.auto()

class _Parser:
    options: Mapping[str, _Option]
    def parse(self, argv) -> Parsed: ...
```
