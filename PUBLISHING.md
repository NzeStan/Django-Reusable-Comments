# Publishing to PyPI

This guide outlines the steps to publish django-reusable-comments to PyPI.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **TestPyPI Account** (optional but recommended): https://test.pypi.org/account/register/
3. **Install build tools**:
   ```bash
   pip install --upgrade pip
   pip install --upgrade build twine
   ```

## Pre-Release Checklist

### 1. Update Version Numbers

Update version in these files:
- [ ] `setup.py` (line 14)
- [ ] `pyproject.toml` (line 6)
- [ ] `setup.cfg` (line 2)
- [ ] `django_comments/__init__.py` (add `__version__ = "1.0.0"`)
- [ ] `CHANGELOG.md` (update release date)

### 2. Run All Tests

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=django_comments --cov-report=html

# Run linters
black django_comments/
isort django_comments/
ruff check django_comments/
mypy django_comments/
```

Ensure all tests pass before proceeding!

### 3. Update Documentation

- [ ] Update README.md with latest features
- [ ] Update CHANGELOG.md with release notes
- [ ] Verify all documentation links work
- [ ] Update installation instructions if needed

### 4. Check Package Files

Verify these files are current:
- [ ] LICENSE (copyright year)
- [ ] README.md (badges, links, examples)
- [ ] CHANGELOG.md (version, date, features)
- [ ] MANIFEST.in (includes all necessary files)
- [ ] requirements files (if any)

### 5. Clean Build Artifacts

```bash
# Remove old build artifacts
rm -rf build/ dist/ *.egg-info/
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

## Building the Package

### 1. Build Distribution Files

```bash
# Build source distribution and wheel
python -m build

# This creates:
# - dist/django-reusable-comments-1.0.0.tar.gz (source distribution)
# - dist/django_reusable_comments-1.0.0-py3-none-any.whl (wheel)
```

### 2. Verify Build Contents

```bash
# Check the contents of the source distribution
tar -tzf dist/django-reusable-comments-1.0.0.tar.gz

# Install locally to test
pip install dist/django_reusable_comments-1.0.0-py3-none-any.whl

# Run a quick smoke test
python -c "import django_comments; print(django_comments.__version__)"
```

## Testing on TestPyPI (Recommended)

### 1. Upload to TestPyPI

```bash
# Upload to TestPyPI first
python -m twine upload --repository testpypi dist/*

# You'll be prompted for:
# Username: __token__
# Password: your-testpypi-token
```

### 2. Test Installation from TestPyPI

```bash
# Create a fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    django-reusable-comments

# Test the package
python -c "from django_comments.models import Comment; print('Success!')"
```

### 3. Verify on TestPyPI

Visit: https://test.pypi.org/project/django-reusable-comments/

Check:
- [ ] Description renders correctly
- [ ] Links work
- [ ] Classifiers are correct
- [ ] Version is correct

## Publishing to PyPI (Production)

### 1. Create API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: "django-reusable-comments"
4. Scope: "Project: django-reusable-comments"
5. Copy the token (starts with `pypi-`)

### 2. Configure `.pypirc` (Optional)

Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TESTPYPI-TOKEN-HERE
```

**Security**: Never commit `.pypirc` to version control!

### 3. Upload to PyPI

```bash
# Upload to PyPI
python -m twine upload dist/*

# You'll be prompted for credentials if not using .pypirc:
# Username: __token__
# Password: pypi-YOUR-TOKEN-HERE
```

### 4. Verify Publication

Visit: https://pypi.org/project/django-reusable-comments/

Check:
- [ ] Package is live
- [ ] Description renders correctly
- [ ] All metadata is correct
- [ ] Download works

### 5. Test Installation

```bash
# In a fresh environment
pip install django-reusable-comments

# Verify it works
python -c "import django_comments; print(f'Version: {django_comments.__version__}')"
```

## Post-Release Steps

### 1. Create GitHub Release

1. Go to https://github.com/NzeStan/django-reusable-comments/releases
2. Click "Create a new release"
3. Tag: `v1.0.0`
4. Title: `Release 1.0.0`
5. Description: Copy from CHANGELOG.md
6. Attach build artifacts (optional)
7. Publish release

### 2. Update Documentation

```bash
# If using ReadTheDocs, trigger a build
# Visit https://readthedocs.org/projects/django-reusable-comments/builds/
```

### 3. Announce Release

- [ ] Tweet about the release
- [ ] Post on Django Forum
- [ ] Post on Reddit (r/django)
- [ ] Update project homepage
- [ ] Email announcement list (if any)

### 4. Monitor Issues

- Watch for installation issues
- Respond to GitHub issues promptly
- Monitor PyPI download stats

## Version Bumping (For Next Release)

### For Patch Release (1.0.1)
```bash
# Bug fixes only, backward compatible
# Update version in all files
# Update CHANGELOG.md
```

### For Minor Release (1.1.0)
```bash
# New features, backward compatible
# Update version in all files
# Update CHANGELOG.md
# Update documentation
```

### For Major Release (2.0.0)
```bash
# Breaking changes
# Update version in all files
# Write migration guide
# Update CHANGELOG.md
# Major documentation update
```

## Troubleshooting

### Upload Fails with "File already exists"

```bash
# You cannot re-upload the same version
# Bump the version number and rebuild
```

### Import Error After Installation

```bash
# Check MANIFEST.in includes all necessary files
# Verify package structure with:
python -m zipfile -l dist/django_reusable_comments-1.0.0-py3-none-any.whl
```

### Description Not Rendering on PyPI

```bash
# Validate README.md
python -m readme_renderer README.md -o /tmp/readme.html

# Check for Markdown issues
# Ensure long_description_content_type = "text/markdown" is set
```

### Twine Upload Authentication Issues

```bash
# Use token authentication
twine upload -u __token__ -p pypi-YOUR-TOKEN-HERE dist/*

# Or set environment variables
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-YOUR-TOKEN-HERE
twine upload dist/*
```

## Security Best Practices

1. **Never commit tokens** to version control
2. **Use API tokens** instead of passwords
3. **Scope tokens** to specific projects
4. **Rotate tokens** regularly
5. **Enable 2FA** on PyPI account
6. **Sign releases** with GPG (optional)

## Resources

- PyPI Help: https://pypi.org/help/
- Packaging Tutorial: https://packaging.python.org/tutorials/packaging-projects/
- Twine Documentation: https://twine.readthedocs.io/
- Python Packaging Guide: https://packaging.python.org/

## Quick Reference Commands

```bash
# Complete release workflow
rm -rf build/ dist/ *.egg-info/
pytest
python -m build
twine check dist/*
twine upload --repository testpypi dist/*  # Test first
twine upload dist/*  # Production release
```

---

**Ready to publish?** Follow this checklist step by step and you'll have a successful release!