# Agent Guidelines
===================

## Core Guidelines
* This project uses `uv` for package management. Before running any python related commands, prefix them with `uv run`. E.g., `uv run script.py`, `uv run pytest`, etc.
* Use `scratchpad-workspace` skill (if it doesn't exist, notify user and stop) for any experimental code or prototypes. This keeps the main codebase clean and stable.
* Ignore `brainstorm` and `dump` directories in the project root; they are for temporary notes and data dumps only.
* Follow modern Python type hinting practices: use built-in types (`list`, `tuple`, `dict`) instead of `typing` aliases (`List`, `Tuple`, `Dict`), and use `| None` instead of `Optional`.
* Avoid using `Any` type hint unless absolutely necessary. Use precise types to ensure clarity and maintainability.
* In Streamlit code, do not use `use_container_width`; use `width="stretch"` or `width="content"` explicitly.
* If you need to build any cli commands, use `cyclopts`
* Use `plotly` for all visualizations. Avoid using `matplotlib` or `seaborn` unless absolutely necessary.
* Use pytest for testing. DO NOT EDIT OR ADD OR REMOVE ANY TESTS UNLESS USER REQUESTS IT.
* Create tests only for the main codebase, not for any scratchpad or experimental code. Scratchpad code is for exploration and prototyping, and does not require tests.
* Run `uvx pyrefly check` to ensure code quality and consistency.
* Run `uv run pytest` to ensure all tests pass before committing any changes.
* Use `pyrefly` or `pytest` only at the end of the development cycle. For example, at the end of finishing a full todo list, or at the end of a full feature implementation, or at the end of a bug fix. Do not run these tools after every small change, as it can slow down development and create unnecessary noise.

## Code Style
* Follow PEP 8 guidelines for code formatting and style.
* Avoid unnecessary validation and error handling in the main codebase. Instead, focus on writing clean, readable and focused code.
* Avoid over-engineering and over abstraction / modularization. Again keep the code simple, readable and focused on the core functionality.
* Avoid unnecessary try-catch blocks, useless type checks, and redundant validation. Only add these when absolutely necessary for the core functionality.