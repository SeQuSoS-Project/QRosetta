# Getting help

## Where to ask

- Bugs, wrong results and install problems: open an issue with the bug report form at
  <https://github.com/SeQuSoS-Project/QRosetta/issues/new/choose>. Search the open and closed
  issues first.
- Ideas for new backends, compilers, analyses or commands: the feature request form on the same
  page.
- Vulnerabilities: never in an issue. Follow `SECURITY.md`.
- Questions that cannot be public (unpublished circuits, collaborations): email
  [info@qrosetta.dev](mailto:info@qrosetta.dev).

Before asking, check the written guide (`docs.html` on a running stack, for example
<http://localhost:8080/docs.html>), and `DESIGN_DECISIONS.md` for the rule and evidence behind
each measurement and analysis choice.

## What to attach

| Problem | Attach |
| --- | --- |
| Any | `qrosetta version --json` |
| Local stack will not build, start or answer | `qrosetta doctor --json` and `qrosetta status --json` |
| A run's result looks wrong | The circuit (`.qasm`) and the run's report (`qrosetta export report --result job:<id> -o report.json`) or RO-Crate (`qrosetta export crate --result job:<id>`, or Export RO-Crate on the page's Exports tab) |
| A backend fails the self-test | The directory `qrosetta selftest` saved under `./qrosetta-results` |
| The web page | Browser name and version, and the error from the browser console |

Remove secrets before attaching anything: passwords, tokens, `SECRET_KEY`, `.env` files and
database or S3 credentials. Reports and crates hold your circuits and results; attach them only if
they may be public.
