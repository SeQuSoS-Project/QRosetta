## What and why

<!-- What changes for a user, and the issue it closes (Closes #N). -->

## Tests run

- [ ] Unit suite, from `rosetta-api/`: `PYTHONPATH=.:../shared pytest tests/unit/ -n auto`
- [ ] `./scripts/check_frontend_types.sh` (page or JavaScript changes)
- [ ] Live-stack checks in `tests/integration/` (runner, compiler or dispatch changes; name which)
- [ ] New tests for the change, or the reason there are none:

## Rules and records

- [ ] No measurement rule changed, or `DESIGN_DECISIONS.md` has an entry with the rule and its evidence
- [ ] Code inside `compile_fn`/`execute_fn` or a timed window is unchanged, or the PR shows identical
      outputs on the corpus and an old-vs-new timing comparison
- [ ] Analysis output is byte-identical (`scripts/harness_bench/equivalence.py`), or `ANALYSIS_VERSION`
      is raised with the reason
- [ ] `CHANGELOG.md` has a line under `[Unreleased]` for a user-visible change
- [ ] New dependencies are pinned with `==` and their `requirements.lock` is updated
- [ ] No credentials, `.env` files or private notes in the diff
