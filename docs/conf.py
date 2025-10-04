"""
Configuration file for the Sphinx documentation builder.
"""

import os
import sys
import django

# Add project to path
sys.path.insert(0, os.path.abspath('..'))

# Configure Django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'django_comments.tests.settings'
django.setup()

# Project information
project = 'Django Reusable Comments'
copyright = '2025, Your Name'
author = 'Your Name'

# The full version, including alpha/beta/rc tags
import django_comments
release = django_comments.__version__

# General configuration
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx_rtd_theme',
    'recommonmark',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# HTML output
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_title = 'Django Reusable Comments Documentation'
html_logo = None
html_favicon = None

# Extension settings
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'django': ('https://docs.djangoproject.com/en/stable/', None),
    'drf': ('https://www.django-rest-framework.org/', None),
}

# MkDocs configuration
markdown_extensions = [
    'admonition',
    'codehilite',
    'toc',
    'tables',
    'fenced_code',
]

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__, __dict__, __module__'
}

# Make sure napoleon works with Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_ivar = True
napoleon_use_rtype = True
napoleon_preprocess_types = True