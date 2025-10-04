# Contributing to Django Reusable Comments

Thank you for your interest in contributing to Django Reusable Comments! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you are expected to uphold our Code of Conduct, which requires treating all people with respect and kindness.

## Getting Started

### Prerequisites

- Python 3.8+
- Django 3.2+
- Django REST Framework 3.12+

### Setup Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/django-reusable-comments.git
   cd django-reusable-comments
   ```

3. Create a virtual environment and install development dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

4. Set up the test environment:
   ```bash
   pytest
   ```

## Development Workflow

1. Create a branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes, following our coding standards
3. Add tests for your changes
4. Run the tests to ensure they pass:
   ```bash
   pytest
   ```

5. Run code quality checks:
   ```bash
   flake8
   black .
   isort .
   ```

6. Commit your changes:
   ```bash
   git commit -m "Description of your changes"
   ```

7. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

8. Create a pull request on GitHub

## Coding Standards

We follow standard Python and Django coding practices:

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Follow [Django's coding style](https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/)

### Code Formatting

We use Black and isort to enforce consistent code formatting:

```bash
# Format code with Black
black .

# Sort imports
isort .
```

### Documentation

- Document all functions, classes, and methods using docstrings
- Update documentation when adding or changing features
- Follow [NumPy docstring style](https://numpydoc.readthedocs.io/en/latest/format.html)

## Testing

We use pytest for testing. All new code should include tests:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=django_comments

# Run specific test
pytest django_comments/tests/test_models.py::TestCommentModel::test_create_comment
```

## Pull Request Process

1. Update the documentation if necessary
2. Update the CHANGELOG.md with details of your changes
3. Make sure all tests pass
4. The PR should work for Python 3.8, 3.9, 3.10, and 3.11
5. If your PR addresses an issue, reference it in the PR description

## Release Process

1. Update version number in:
   - `django_comments/__init__.py`
   - `setup.py`
   - `CHANGELOG.md`
2. Create a new release on GitHub
3. Build and upload to PyPI:
   ```bash
   python setup.py sdist bdist_wheel
   twine upload dist/*
   ```

## Feature Requests and Bug Reports

If you have a feature request or have found a bug, please open an issue on GitHub:

- For bugs, provide detailed steps to reproduce
- For features, explain the use case and expected behavior

## Translation Guidelines

If you're contributing translations:

1. Extract messages:
   ```bash
   django-admin makemessages -l [language_code]
   ```

2. Edit the `.po` file in `django_comments/locale/[language_code]/LC_MESSAGES/django.po`

3. Compile messages:
   ```bash
   django-admin compilemessages
   ```

## Getting Help

If you need help with contributing, please open an issue or contact the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.