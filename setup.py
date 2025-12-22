#!/usr/bin/env python
"""
Setup configuration for django-reusable-comments package.
"""
import os
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="django-reusable-comments",
    version="1.0.0",
    author="Ifeanyi Stanley Nnamani",
    author_email="nnamaniifeanyi10@gmail.com",
    description="A production-grade reusable Django comments app with REST API, moderation, spam detection, and GDPR compliance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NzeStan/django-reusable-comments",
    project_urls={
        "Bug Tracker": "https://github.com/NzeStan/django-reusable-comments/issues",
        "Documentation": "https://django-reusable-comments.readthedocs.io/",
        "Repository": "https://github.com/NzeStan/django-reusable-comments",
        "Changelog": "https://github.com/NzeStan/django-reusable-comments/blob/main/CHANGELOG.md",
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords=["django", "comments", "rest-framework", "api", "moderation", "spam-detection", "gdpr"],
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "Django>=3.2",
        "djangorestframework>=3.14.0",
        "django-filter>=23.0",
        "bleach>=6.0.0",
    ],
    extras_require={
        'markdown': [
            'markdown>=3.4.0',
        ],
        'celery': [
            'celery>=5.3.0',
            'redis>=4.5.0',
        ],
        'dev': [
            # Testing
            'pytest>=7.4.0',
            'pytest-django>=4.7.0',
            'pytest-cov>=4.1.0',
            'pytest-xdist>=3.5.0',
            'pytest-sugar>=0.9.7',
            'factory-boy>=3.3.0',
            'Faker>=20.0.0',
            'freezegun>=1.4.0',
            'responses>=0.24.0',
            # Code Quality
            'black>=23.0.0',
            'isort>=5.13.0',
            'ruff>=0.1.0',
            'mypy>=1.7.0',
            'django-stubs>=4.2.0',
            'djangorestframework-stubs>=3.14.0',
            # Documentation
            'mkdocs>=1.5.0',
            'mkdocs-material>=9.5.0',
            'mkdocstrings[python]>=0.24.0',
            # Development Tools
            'ipython>=8.18.0',
            'ipdb>=0.13.13',
            'django-debug-toolbar>=4.2.0',
            'django-extensions>=3.2.0',
        ],
    },
    zip_safe=False,
)