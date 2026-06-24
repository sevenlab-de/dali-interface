# Changelog for `dali-interface`

## v1.14

- Summarize interface-specific error states into the generic `INTERFACE` status (removes `DaliStatus.GENERAL` and `DaliStatus.UNDEFINED`).
- Input lines that don't contain valid DALI frame information are ignored for "line"-based devices.

## v1.13

- Remove run-time typechecking. Instead the package relies on `mypy`'s static analysis.
- Fix type inconsistencies uncovered by `mypy`
- Prepare the package for publishing on PyPI
