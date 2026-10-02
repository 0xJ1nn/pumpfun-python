# Contributing to pumpfun-python

## Development Setup

```bash
git clone https://github.com/0xJ1nn/pumpfun-python.git
cd pumpfun-python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Code Quality

```bash
ruff check .
mypy pumpfun/
```

## Pull Requests

1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a PR
