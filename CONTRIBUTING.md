# Contributing to ContextGraph Integrations

We love contributions! This document explains how to contribute.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/akz4ol/contextgraph-integrations.git
cd contextgraph-integrations

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dev dependencies for the integration you're working on
cd langchain  # or crewai
pip install -e ".[dev]"
```

## Running Tests

```bash
cd langchain  # or crewai
pytest
```

## Adding a New Integration

1. Create a new directory: `mkdir myframework`
2. Add the required files:
   - `myframework/contextgraph_myframework.py` - Main integration code
   - `myframework/setup.py` - Package setup
   - `myframework/README.md` - Documentation
   - `myframework/tests/` - Test directory
3. Update the root README.md to include your integration
4. Submit a PR

## Code Style

- Use [Black](https://github.com/psf/black) for formatting
- Use [isort](https://pycqa.github.io/isort/) for imports
- Add type hints where possible
- Include docstrings for public APIs

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit with a clear message
6. Push to your fork
7. Open a Pull Request

## Questions?

- Open an issue for bugs or feature requests
- Email blog.mot2gmob@gmail.com for other questions
