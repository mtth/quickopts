# `quickopts`

Tiny opinionated Python library for parsing script options.

## Overview

`quickopts` parses POSIX `getopts`-style command-line arguments from the same
docstring you use for help text. It supports:

- single-letter options, with clustering, so `-Cz` behaves like `-C -z` and
  `-Czbmain` behaves like `-C -z -b main`;
- positional arguments, where the first positional argument stops option
  parsing, plus `--` to stop option parsing explicitly.

It is intentionally small and does not support long options like `--flag`,
optional flag values, or validation of `Synopsis:` patterns.


## Sample usage

`quickopts` works well for single-file scripts using [PEP 723][] inline
dependency metadata. Tools such as `uv` can read the script header, create an
environment with `quickopts` installed, and then run the file directly from its
shebang.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "quickopts",
# ]
# ///

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
    q = quickopts.parse_or_exit(
        __doc__,
        template_mapping={"prog": quickopts.Placeholder.PROGRAM},
    )
    match q.command or "L":
        case "C": _create(branch=q.flags["b"], sleep="z" in q.switches)
        case "D": _delete(q.args[0])
        case "L": ...
        case "W": ...
```

## Parsing rules

`quickopts` reads option definitions from `Commands:` and `Options:` sections in
the docstring. Blank lines end the current section. `Synopsis:` is not parsed; it
is only help text.

Command entries define mutually exclusive commands. We recommend using uppercase
letters for these, other than the standard `-h` help command:

```text
Commands:
  -C  Create a value.
  -L  List all values.
  -h  Show help.
```

Option entries define either value flags or switches. In `Options:`, an entry is
a value flag when non-whitespace text appears between the option name and the
two-or-more-space gap before the description. Otherwise it is a switch. We
recommend lowercase letters in this section:

```text
Options:
  -b BRANCH  Value flag.
  -z         Switch.
```

`parse(doc, args)` parses `args` without a program name and returns a `Parsed`
object with the following attributes:

- `command`: the selected command, or `None`;
- `flags`: value flags, for example `{"b": "main"}`;
- `switches`: switch repeat counts, for example `{"z": 2}`; use
  `"z" in q.switches` to check presence;
- `args`: remaining positional arguments.

Single-dash options use POSIX `getopts`-style clustering:

| Args | Result |
| --- | --- |
| `-Cz` | command `C`, switch `z` |
| `-Cb main` | command `C`, flag `b=main` |
| `-Czbmain` | command `C`, switch `z`, flag `b=main` |
| `value -z` | args `["value", "-z"]`; `-z` is not parsed |
| `-- -z` | args `["-z"]`; `-z` is not parsed |

When a value flag appears inside a cluster, it consumes the rest of that token as
its value. If no characters remain, it consumes the following arg. Repeated value
flags use the last value. Repeated switches are counted.

`parse_or_exit(doc, template_mapping={"prog": quickopts.Placeholder.PROGRAM})`
reads `sys.argv`, prints parse errors to stderr with exit code `2`, and handles
`-h` by printing the docstring and exiting with code `0`. Template mappings use
`string.Template` substitution, and values may be literal strings or built-in
placeholders such as `quickopts.Placeholder.PROGRAM`, which resolves to the
display program name, including `python -m module` when invoked with `-m`. The
older `program_var="prog"` shortcut is still supported for compatibility.

[PEP 723]: https://peps.python.org/pep-0723/
