# Django Reusable Comments

A complete, reusable Django app for adding comment functionality to any model in your Django project.

## Features

- ✅ **Model Agnostic** - Add comments to any Django model
- ✅ **ID Flexibility** - Support for both UUID and integer primary keys
- ✅ **Highly Customizable** - Extensive settings and configuration options
- ✅ **Signals** - Robust signal system for extending functionality
- ✅ **Internationalization** - Full i18n support using gettext_lazy
- ✅ **DRF Integration** - Complete REST API via Django REST Framework
- ✅ **Testing** - Comprehensive test suite
- ✅ **Documentation** - Thorough documentation for developers
- ✅ **Logging & Error Handling** - Sophisticated error handling
- ✅ **Admin Interface** - Feature-rich admin panel

## Getting Started

To get started with Django Reusable Comments, check the [Installation](installation.md) guide.

## Package Overview

Django Reusable Comments is designed to be as flexible and reusable as possible. The package provides the following core components:

1. **Models**:
   - `Comment` - The core comment model
   - `CommentFlag` - Model for flagging inappropriate comments

2. **API**:
   - Complete REST API for creating, retrieving, updating, and deleting comments
   - Filtering and search capabilities
   - Support for nested/threaded comments

3. **Admin Interface**:
   - Custom admin views for comments
   - Moderation workflow
   - Comment flagging management

4. **Signals**:
   - Signal system for extending functionality
   - Hooks for comment lifecycle events

5. **Customization**:
   - Extensive settings and configuration options
   - Support for custom comment models

## Documentation Contents

- [Installation](installation.md) - How to install the package
- [Configuration](configuration.md) - Available settings and options
- [Advanced Usage](advanced_usage.md) - Advanced usage patterns
- [API Reference](api_reference.md) - Complete API reference
- [Contributing](contributing.md) - Guide for contributors