# Contributing to Django Reusable Comments

Thank you for your interest in contributing! Please read the full contributing guide at:

**[docs/contributing.md](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md)**

It covers:

- [Code of Conduct](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#code-of-conduct)
- [Development Setup](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#development-setup)
- [Development Workflow](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#development-workflow)
- [Code Standards](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#code-standards)
- [Testing](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#testing)
- [Pull Request Process](https://github.com/NzeStan/django-reusable-comments/blob/main/docs/contributing.md#pull-request-process)

## Quick Start

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/django-reusable-comments.git
cd django-reusable-comments

# 2. Create virtual environment and install dev dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Run tests to verify setup
pytest

# 4. Create a feature branch
git checkout -b feature/your-feature-name
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=django_comments --cov-report=html

# Specific file
pytest django_comments/tests/test_models.py
```

## Code Quality

```bash
black django_comments/   # Format
isort django_comments/   # Sort imports
ruff check django_comments/  # Lint
mypy django_comments/    # Type check
```

## Questions?

- **GitHub Issues**: [https://github.com/NzeStan/django-reusable-comments/issues](https://github.com/NzeStan/django-reusable-comments/issues)
- **GitHub Discussions**: [https://github.com/NzeStan/django-reusable-comments/discussions](https://github.com/NzeStan/django-reusable-comments/discussions)
- **Email**: nnamaniifeanyi10@gmail.com

By contributing, you agree your contributions will be licensed under the MIT License.
