# Contributing to chuk-mcp-tides

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- UV (recommended) or pip

### Getting Started

1. **Fork and Clone**

```bash
git clone https://github.com/IBM/chuk-mcp-tides.git
cd chuk-mcp-tides
```

2. **Install Dependencies**

Using UV (recommended):
```bash
uv sync --dev
```

Using pip:
```bash
pip install -e ".[dev]"
```

3. **Verify Installation**

```bash
make test
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

Follow these guidelines:

- Write clear, descriptive commit messages
- Add tests for new functionality
- Update documentation as needed
- Follow the existing code style

### 3. Test Your Changes

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run linting
make lint

# Run all checks
make check
```

### 4. Format Code

```bash
make format
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add awesome new feature"
```

Use conventional commit messages:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Style

We use Ruff for linting and formatting:

- Line length: 100 characters
- Type hints required for public APIs
- Docstrings for all public functions and classes
- Follow PEP 8 conventions

## Adding New Tools

Tools are organized by category under `src/chuk_mcp_tides/tools/`. Each category has its own directory with an `api.py` module. When adding a new tool:

1. **Add the tool function** in the appropriate `tools/<category>/api.py`
2. **Register it** in `tools/__init__.py`
3. **Add a Pydantic model** in `models/responses.py` if needed
4. **Add documentation** in `README.md`
5. **Add tests** in `tests/`

## Adding New Providers

Providers live in `src/chuk_mcp_tides/providers/`. Each provider implements the interface defined in `providers/base.py`. When adding a new provider:

1. **Create** `providers/<name>.py` implementing `TideProvider`
2. **Register it** in `providers/__init__.py`
3. **Add constants** for API endpoints in `constants.py`
4. **Add tests** covering the new provider

## Project Structure

```
chuk-mcp-tides/
├── src/
│   └── chuk_mcp_tides/
│       ├── __init__.py
│       ├── server.py              # Entry point
│       ├── async_server.py        # Async MCP server
│       ├── constants.py           # API endpoints, defaults
│       ├── core/                  # Core orchestration
│       │   ├── tide_manager.py
│       │   ├── http_client.py
│       │   ├── constituent_storage.py
│       │   ├── reference_cache.py
│       │   └── utils.py
│       ├── models/                # Pydantic response models
│       │   └── responses.py
│       ├── providers/             # Data source adapters
│       │   ├── base.py
│       │   ├── noaa.py
│       │   ├── ea.py
│       │   ├── ukho.py
│       │   └── local.py
│       └── tools/                 # MCP tool implementations
│           ├── stations/
│           ├── predictions/
│           ├── observations/
│           ├── analysis/
│           ├── flood/
│           ├── currents/
│           └── discovery/
├── tests/
├── examples/
├── pyproject.toml
├── Makefile
├── Dockerfile
└── README.md
```

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Discussions**: Ask questions or share ideas
- **Pull Requests**: Contribute code or documentation

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Help others learn and grow

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes
- Project documentation

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
