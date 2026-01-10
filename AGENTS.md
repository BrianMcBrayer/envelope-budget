# AGENTS.md

## TDD Workflow

Use test-driven development for all functional changes:

1. Write the test first.
2. Run the test and confirm it fails for the expected reason.
3. Implement the smallest code change to make the test pass.
4. Run the test suite again and confirm it passes.

## Expectations

- Do not skip the failing-test step.
- Capture the exact command you ran for tests in your response.
- If a test is too slow to run fully, run the smallest relevant subset and explain why.
- Act with agency: verify your work by running the relevant commands (tests, CLI, or app start) instead of assuming it works.
- Write robust tests that cover happy paths, edge cases, and error handling for any behavior you change or add.
- Use both unit tests and integration tests for functional changes; include end-to-end CLI coverage when the CLI is touched.
- Always run and verify anything you implement or configure (builds, containers, commands, scripts), and report the exact commands executed and results.

## Package Management (uv)

- Use `uv` for all dependency and environment management.
- Add/update/remove dependencies via `uv add` / `uv remove` instead of manual edits to `pyproject.toml`.
- After dependency changes, run `uv lock`.
- Use `uv run` for running tools (e.g., `uv run --extra dev pytest`).
- Avoid `pip` or ad-hoc virtualenvs.

## Release Flow (GitHub CLI)

When asked to "create a new release":

1. Fetch tags: `git fetch --tags`.
2. Determine the next release number by incrementing the latest tag (currently patch-based, e.g., `0.0.4` -> `0.0.5`).
3. Create the release with generated notes: `gh release create <tag> --title "<tag>" --generate-notes`.
4. Report the release URL.
