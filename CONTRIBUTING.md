# Contributing to tsktui

Thank you for your interest in improving `tsktui`!

## 🛠️ Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/tsktui.git
   cd tsktui
   ```

2. Create a virtual environment and install in editable mode with development dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Ensure The Sleuth Kit is installed:
   ```bash
   # macOS
   brew install sleuthkit

   # Linux
   sudo apt-get install sleuthkit
   ```

## 🧪 Running Tests

Run the test suite with `pytest`:
```bash
pytest
```

## 📝 Pull Request Guidelines

- Ensure all tests pass before submitting.
- Follow PEP 8 and use clear docstrings and type hints.
- Keep PRs focused on a single feature or bug fix.
