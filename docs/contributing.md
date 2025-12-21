# Contributing to Django Reusable Comments

Thank you for your interest in contributing to django-reusable-comments! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)
- [Community](#community)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:
- Experience level
- Gender identity and expression
- Sexual orientation
- Disability
- Personal appearance
- Body size
- Race and ethnicity
- Age
- Religion
- Nationality

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what's best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment, trolling, or derogatory comments
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of unacceptable behavior may be reported to nnamaniifeanyi10@gmail.com. All complaints will be reviewed and investigated promptly and fairly.

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:
- Python 3.8+ installed
- Git installed and configured
- A GitHub account
- Basic knowledge of Django and Django REST Framework

### Quick Contribution Checklist

- [ ] Fork the repository
- [ ] Create a feature branch
- [ ] Make your changes
- [ ] Write/update tests
- [ ] Update documentation
- [ ] Run tests and linters
- [ ] Submit a pull request

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/django-reusable-comments.git
cd django-reusable-comments

# Add upstream remote
git remote add upstream https://github.com/NzeStan/django-reusable-comments.git
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install package in development mode with all dev dependencies
pip install -e ".[dev]"

# This installs:
# - pytest, pytest-django, pytest-cov (testing)
# - black, isort, ruff (code formatting/linting)
# - mypy, django-stubs (type checking)
# - mkdocs, mkdocs-material (documentation)
# - ipython, ipdb (debugging)
```

### 4. Setup Test Database

The test suite uses an in-memory SQLite database by default. No setup required!

```bash
# Run tests to verify setup
pytest
```

### 5. Configure Your Editor

#### VS Code

Create `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": false,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "[python]": {
        "editor.rulers": [88]
    }
}
```

#### PyCharm

1. Go to Settings → Tools → Python Integrated Tools
2. Set Default test runner to `pytest`
3. Go to Settings → Editor → Code Style → Python
4. Set line length to 88
5. Enable Black formatter integration

---

## Development Workflow

### 1. Create a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes:
git checkout -b fix/bug-description
```

### Branch Naming Conventions

- **Features**: `feature/descriptive-name`
- **Bug Fixes**: `fix/bug-description`
- **Documentation**: `docs/what-changed`
- **Tests**: `test/what-tested`
- **Refactoring**: `refactor/what-refactored`

### 2. Make Changes

Follow these practices:
- Write clear, concise commit messages
- Keep commits focused and atomic
- Reference issues in commits (e.g., "Fix #123: Description")
- Write tests for new features
- Update documentation

### 3. Run Tests and Linters

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=django_comments --cov-report=html

# Run specific test file
pytest django_comments/tests/test_models.py

# Run specific test
pytest django_comments/tests/test_models.py::TestCommentModel::test_create_comment

# Run tests in parallel (faster)
pytest -n auto

# Format code with black
black django_comments/

# Sort imports with isort
isort django_comments/

# Lint with ruff
ruff check django_comments/

# Type check with mypy
mypy django_comments/
```

### 4. Commit Changes

```bash
# Add changes
git add .

# Commit with descriptive message
git commit -m "Add feature: Description of what was added

- Detail 1
- Detail 2

Fixes #123"
```

### Good Commit Messages

```
# Good ✅
Add spam detection with ML model support

- Implement custom spam detector callback
- Add test cases for spam detection
- Update documentation with examples

Closes #45

# Bad ❌
update stuff
fixed bug
changes
```

### 5. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Then create PR on GitHub
```

---

## Code Standards

### Python Style Guide

We follow PEP 8 with some modifications:
- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes for strings
- **Imports**: Organized with isort

### Code Formatting

We use **Black** for automatic code formatting:

```bash
# Format all code
black django_comments/

# Check without modifying
black --check django_comments/
```

### Import Organization

We use **isort** to organize imports:

```python
# Standard library imports
import os
import sys
from datetime import datetime

# Third-party imports
from django.db import models
from django.contrib.auth import get_user_model
from rest_framework import serializers

# Local imports
from django_comments.models import Comment
from django_comments.utils import process_comment_content
from .utils import helper_function
```

Run isort:

```bash
isort django_comments/
```

### Linting

We use **ruff** for fast linting:

```bash
# Check for issues
ruff check django_comments/

# Auto-fix issues
ruff check --fix django_comments/
```

### Type Hints

Use type hints for function signatures:

```python
from typing import Optional, List, Tuple
from django.contrib.auth.models import User

def create_comment(
    user: User,
    content: str,
    parent: Optional['Comment'] = None
) -> Comment:
    """
    Create a new comment.
    
    Args:
        user: The comment author
        content: Comment text
        parent: Optional parent comment for replies
        
    Returns:
        Created Comment instance
    """
    comment = Comment.objects.create(
        user=user,
        content=content,
        parent=parent
    )
    return comment
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_spam_score(content: str) -> Tuple[bool, float]:
    """
    Calculate spam probability for comment content.
    
    Uses multiple signals including ML model, URL count, and
    text patterns to determine likelihood of spam.
    
    Args:
        content: The comment text to analyze
        
    Returns:
        Tuple of (is_spam, confidence_score) where:
        - is_spam: Boolean indicating if content is spam
        - confidence_score: Float between 0-1 indicating confidence
        
    Raises:
        ValueError: If content is empty
        
    Example:
        >>> is_spam, score = calculate_spam_score("Buy now! Click here!")
        >>> print(f"Spam: {is_spam}, Score: {score:.2f}")
        Spam: True, Score: 0.92
    """
    if not content:
        raise ValueError("Content cannot be empty")
    
    # Implementation...
    return is_spam, score
```

### Django Best Practices

```python
# Use Django's built-in validators
from django.core.validators import MaxLengthValidator

# Use get_user_model() instead of importing User directly
from django.contrib.auth import get_user_model
User = get_user_model()

# Use gettext_lazy for i18n
from django.utils.translation import gettext_lazy as _

class Comment(models.Model):
    content = models.TextField(
        _("content"),
        help_text=_("The comment text")
    )

# Use select_related and prefetch_related
comments = Comment.objects.select_related('user').prefetch_related('children')

# Use timezone-aware datetimes
from django.utils import timezone
now = timezone.now()
```

---

## Testing

### Test Structure

```
django_comments/tests/
├── __init__.py
├── settings.py          # Test settings
├── base.py             # Base test classes
├── test_models.py      # Model tests
├── test_views.py       # API view tests
├── test_serializers.py # Serializer tests
├── test_permissions.py # Permission tests
├── test_signals.py     # Signal tests
├── test_utils.py       # Utility function tests
├── test_admin.py       # Admin interface tests
└── test_tags.py        # Template tag tests
```

### Writing Tests

Use pytest and Django test classes:

```python
# django_comments/tests/test_models.py
import pytest
from django.contrib.auth import get_user_model
from django_comments.tests.base import BaseCommentTestCase
from django_comments.models import Comment

User = get_user_model()


class TestCommentModel(BaseCommentTestCase):
    """Test Comment model functionality."""
    
    def test_create_comment(self):
        """Test creating a basic comment."""
        comment = self.create_comment(
            content="Test comment"
        )
        
        self.assertEqual(comment.content, "Test comment")
        self.assertEqual(comment.user, self.regular_user)
        self.assertTrue(comment.is_public)
        self.assertFalse(comment.is_removed)
    
    def test_comment_threading(self):
        """Test comment reply threading."""
        parent = self.create_comment(content="Parent")
        reply = self.create_comment(
            content="Reply",
            parent=parent
        )
        
        self.assertEqual(reply.parent, parent)
        self.assertEqual(reply.depth, 1)
        self.assertEqual(reply.thread_id, parent.id)
    
    def test_comment_str_representation(self):
        """Test string representation of comment."""
        comment = self.create_comment(
            content="Test comment"
        )
        
        expected = f"Comment by {comment.user.username}: {comment.content[:50]}"
        self.assertEqual(str(comment), expected)


# Using pytest markers
@pytest.mark.django_db
def test_comment_creation():
    """Test comment creation with pytest."""
    user = User.objects.create_user(
        username='testuser',
        password='testpass'
    )
    
    comment = Comment.objects.create(
        user=user,
        content="Test",
        content_type_id=1,
        object_id="1"
    )
    
    assert comment.content == "Test"
    assert comment.user == user
```

### Test Coverage

We aim for **90%+ code coverage**:

```bash
# Run with coverage
pytest --cov=django_comments --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Test Best Practices

1. **Test one thing at a time**
```python
# Good ✅
def test_comment_requires_content(self):
    """Test that comment requires content field."""
    with self.assertRaises(ValidationError):
        Comment.objects.create(user=self.user, content="")

def test_comment_requires_user(self):
    """Test that comment requires user field."""
    with self.assertRaises(IntegrityError):
        Comment.objects.create(content="Test")

# Bad ❌
def test_comment_validation(self):
    """Test all comment validation."""
    # Tests multiple things in one test
```

2. **Use descriptive test names**
```python
# Good ✅
def test_flagging_comment_creates_flag_record(self):
def test_banned_user_cannot_create_comment(self):
def test_moderator_can_approve_comment(self):

# Bad ❌
def test_flag(self):
def test_ban(self):
def test_approve(self):
```

3. **Use fixtures for common setup**
```python
# conftest.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='testuser',
        password='testpass'
    )

@pytest.fixture
def moderator(db):
    user = User.objects.create_user(
        username='moderator',
        password='testpass'
    )
    user.is_staff = True
    user.save()
    return user
```

4. **Test edge cases**
```python
def test_comment_with_max_length_content(self):
    """Test comment with maximum allowed length."""
    max_length = 3000
    long_content = "x" * max_length
    
    comment = self.create_comment(content=long_content)
    self.assertEqual(len(comment.content), max_length)

def test_comment_with_unicode_characters(self):
    """Test comment with Unicode characters."""
    unicode_content = "Hello 世界! 🎉 مرحبا"
    comment = self.create_comment(content=unicode_content)
    self.assertEqual(comment.content, unicode_content)
```

### Running Specific Tests

```bash
# Run specific test file
pytest django_comments/tests/test_models.py

# Run specific test class
pytest django_comments/tests/test_models.py::TestCommentModel

# Run specific test method
pytest django_comments/tests/test_models.py::TestCommentModel::test_create_comment

# Run tests matching pattern
pytest -k "spam"

# Run tests with specific marker
pytest -m "api"

# Run in verbose mode
pytest -v

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

---

## Documentation

### Documentation Structure

```
docs/
├── index.md              # Main documentation page
├── installation.md       # Installation guide
├── configuration.md      # Configuration reference
├── api_reference.md      # API documentation
├── advanced_usage.md     # Advanced features
└── contributing.md       # This file
```

### Writing Documentation

Documentation is written in **Markdown** and built with **MkDocs**.

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material mkdocstrings[python]

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### Documentation Standards

1. **Use clear headings**
```markdown
# Main Topic

## Subtopic

### Detail

#### Sub-detail
```

2. **Include code examples**
````markdown
Example usage:

```python
from django_comments.models import Comment

comment = Comment.objects.create(
    user=user,
    content="Example"
)
```
````

3. **Add links to related docs**
```markdown
See [API Reference](api_reference.md) for endpoint details.
See [Configuration](configuration.md#spam-detection) for spam settings.
```

4. **Update CHANGELOG**
```markdown
# Changelog

## [1.1.0] - 2025-02-15

### Added
- New feature X
- Support for Y

### Fixed
- Bug in Z

### Changed
- Improved performance of A
```

---

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines (Black, isort)
- [ ] All tests pass (`pytest`)
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No linting errors (`ruff check`)
- [ ] Type hints added where applicable

### Creating a Pull Request

1. **Push your branch**
```bash
git push origin feature/your-feature-name
```

2. **Create PR on GitHub**
   - Go to the repository on GitHub
   - Click "Pull Requests" → "New Pull Request"
   - Select your branch
   - Fill out the PR template

3. **PR Title Format**
```
feat: Add spam detection with ML support
fix: Correct pagination for nested comments
docs: Update API reference with new endpoints
test: Add tests for GDPR compliance
refactor: Optimize comment query performance
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Fixes #123
Relates to #456

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Added new tests
- [ ] All tests pass
- [ ] Manual testing performed

## Screenshots (if applicable)
[Add screenshots here]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests added/updated
- [ ] CHANGELOG.md updated
```

### Review Process

1. **Automated Checks**
   - CI/CD runs tests
   - Code coverage checked
   - Linting verified

2. **Code Review**
   - Maintainers review code
   - Feedback provided
   - Changes requested if needed

3. **Approval & Merge**
   - After approval, PR will be merged
   - Your contribution will be acknowledged

### After Your PR is Merged

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Delete feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## Reporting Bugs

### Before Reporting

1. **Check existing issues** - Your bug might already be reported
2. **Update to latest version** - Bug might already be fixed
3. **Check documentation** - Might be a usage issue

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots.

**Environment:**
 - OS: [e.g. Ubuntu 20.04]
 - Python version: [e.g. 3.9]
 - Django version: [e.g. 4.2]
 - DRF version: [e.g. 3.14]
 - Package version: [e.g. 1.0.0]

**Additional context**
Any other relevant information.

**Error logs**
```
Paste error logs here
```
```

---

## Feature Requests

### Before Requesting

1. **Check existing feature requests**
2. **Check roadmap** - Might already be planned
3. **Consider if it fits the project scope**

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions you've thought about.

**Additional context**
Any other relevant information.

**Proposed API (if applicable)**
```python
# Example of how the feature would be used
```

**Willing to contribute?**
- [ ] Yes, I can implement this
- [ ] Yes, with guidance
- [ ] No, but I'd like to see it added
```

---

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community chat
- **Email**: nnamaniifeanyi10@gmail.com for private matters

### Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- GitHub contributors page

### Becoming a Maintainer

Active contributors may be invited to become maintainers. Maintainers:
- Review and merge pull requests
- Triage issues
- Help with releases
- Guide new contributors

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

If you have questions about contributing:

1. Check this guide
2. Search existing issues/discussions
3. Create a new discussion
4. Contact maintainers

**Thank you for contributing to django-reusable-comments! 🎉**

Every contribution, no matter how small, helps make this project better for everyone.

---

## Development Resources

### Useful Commands

```bash
# Quick development workflow
make install    # Install dependencies
make test       # Run tests
make lint       # Run linters
make format     # Format code
make docs       # Build documentation

# Create these in Makefile:
```

```makefile
# Makefile
.PHONY: install test lint format docs clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=django_comments

lint:
	ruff check django_comments/
	mypy django_comments/

format:
	black django_comments/
	isort django_comments/

docs:
	mkdocs serve

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage .pytest_cache/
```

### Recommended Reading

- [Django Documentation](https://docs.djangoproject.com/)
- [Django REST Framework Guide](https://www.django-rest-framework.org/)
- [Python PEP 8 Style Guide](https://pep8.org/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**Happy Contributing! 🚀**