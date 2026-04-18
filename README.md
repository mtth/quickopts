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


if __name__ == "__main__":
    q = quickopts.parse_or_exit(__doc__, program_var="prog")
    match q.command or "L":
        case "C":
            _create(branch=q.flags["b"], sleep="z" in q.switches)
        case "D":
            _delete(q.args[0])
        case "L": ...
        case "W": ...
```
