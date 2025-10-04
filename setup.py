#!/usr/bin/env python
import os
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="django-reusable-comments",
    version="0.1.0",
    author="Ifeanyi Stanley Nnamani",
    author_email="nnamaniifeanyi10@gmail.com",
    description="A reusable Django comments app with DRF integration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NzeStan/django-reusable-comments",
    project_urls={
        "Bug Tracker": "https://github.com/NzeStan/django-reusable-comments/issues",
        "Documentation": "https://django-reusable-comments.readthedocs.io/",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "Django>=3.2",
        "djangorestframework>=3.12.0",
        "django-filter>=21.1",
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-django>=4.5.0',
            'pytest-cov>=3.0.0',
            'factory-boy>=3.2.0',
            'black>=22.0.0',
            'isort>=5.10.0',
            'flake8>=4.0.0',
            'mkdocs>=1.3.0',
            'mkdocs-material>=8.2.0',
        ],
    },
    zip_safe=False,
)