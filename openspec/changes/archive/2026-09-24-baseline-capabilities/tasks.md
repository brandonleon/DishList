## 1. Review

- [x] 1.1 Read through all eight spec files against `app/main.py` and `app/cli.py` and confirm each requirement/scenario matches current behavior
- [x] 1.2 Flag any requirement that describes desired-but-not-yet-built behavior so it's moved to a follow-up change instead of the baseline

## 2. Validate

- [x] 2.1 Run `openspec validate baseline-capabilities --strict` and fix any structural issues
- [x] 2.2 Run `uv run pytest tests/` to confirm nothing about the app itself needs to change

## 3. Archive

- [x] 3.1 Run `openspec archive baseline-capabilities` to move the specs into `openspec/specs/`
