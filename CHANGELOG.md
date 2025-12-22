# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-21

### 🎉 Initial Production Release

A complete, production-grade Django comments system with 280+ tests, comprehensive documentation, and enterprise-ready features.

### Added

#### Core Features
- **Model-Agnostic Comments** - Add comments to any Django model via ContentType
- **UUID Primary Keys** - Modern UUID-based identification system
- **Threaded Comments** - Nested replies with configurable depth limits (default: 3 levels)
- **Materialized Path** - Efficient hierarchical storage for comment threads
- **Full REST API** - Complete DRF integration with ViewSets and serializers
- **Django Admin Integration** - Feature-rich admin with bulk actions and custom filters

#### Content & Formatting (🎨)
- **Multiple Format Support**
  - Plain text (HTML escaped - safest option)
  - Markdown (CommonMark compliant with extensions)
  - HTML (sanitized with bleach for XSS protection)
- **XSS Protection** - Automatic HTML sanitization using bleach
- **Profanity Filtering** - Configurable profanity detection with actions:
  - Censor (replace with asterisks)
  - Flag (mark for review)
  - Hide (set is_public=False)
  - Delete (reject completely)
- **Comment Editing** - Time-windowed editing (default: 1 hour)
- **Edit History Tracking** - Complete revision history with CommentRevision model
- **Maximum Length Control** - Configurable content length limits (default: 3000 chars)

#### Spam Detection & Content Control (🛡️)
- **Advanced Spam Detection**
  - Word-based detection with customizable word lists
  - ML-ready custom detector callback support
  - Configurable actions (flag/hide/delete)
  - Auto-hide detected spam option
- **Flag System**
  - Multiple flag types: spam, offensive, inappropriate, harassment, other
  - Rate limiting (20 flags/day, 5 flags/hour per user)
  - Moderator notifications on flags
  - Abuse prevention mechanisms
- **Auto-Moderation**
  - Auto-hide after N flags (default: 3)
  - Auto-delete after N flags (default: 10)
  - Threshold-based moderator notifications
  - Complete moderation action logging

#### Moderation & Workflows (👮)
- **Moderation Queue**
  - Require approval before publishing (configurable)
  - Group-based permissions (Moderators, Staff)
  - Auto-approval for trusted users
  - Auto-approval after N approved comments
- **Ban System**
  - Auto-ban after rejections (default: 5)
  - Auto-ban after spam flags (default: 3)
  - Temporary bans (configurable duration)
  - Permanent bans
  - Ban/unban notifications
  - BannedUser model with reason tracking
- **Moderation Logs**
  - Complete audit trail (ModerationAction model)
  - 90-day default retention
  - Tracks all moderation actions (approve, reject, ban, unban)
  - User and timestamp tracking

#### Email Notifications (📧)
- **8 Notification Types**
  1. New comment notifications
  2. Reply notifications
  3. Approval notifications
  4. Rejection notifications
  5. Moderator alerts (for non-public comments)
  6. User ban notifications
  7. User unban notifications
  8. Flag threshold alerts
- **Beautiful HTML Templates** - Professional email designs for all notification types
- **Async Support** - Optional Celery integration with graceful fallback to sync
- **Configurable Recipients** - Per-notification-type email configuration
- **Template Customization** - Override default templates easily
- **SMTP Support** - Works with any Django email backend

#### API Features (🔌)
- **3-Tier Rate Limiting**
  - User limits (default: 100 requests/day)
  - Anonymous limits (default: 20 requests/day)
  - Burst protection (default: 5 requests/minute)
  - DRF throttling classes integration
- **Advanced Filtering**
  - Filter by user, content object, public status
  - Full-text search on content
  - Date range filtering
  - Custom ordering options
  - django-filter integration
- **Smart Pagination**
  - Standard pagination support
  - Thread-aware pagination for nested comments
  - Configurable page sizes (default: 20, max: 100)
  - Client-controlled page size
- **Bulk Operations**
  - Bulk approve/reject
  - Bulk flag/unflag
  - Bulk delete
- **Performance Optimizations**
  - select_related() for foreign keys
  - prefetch_related() for reverse relations
  - Optimized querysets with with_full_thread()

#### GDPR Compliance (⚖️)
- **Data Subject Rights**
  - Right to data portability (Article 20) - export_user_data()
  - Right to erasure (Article 17) - delete_user_data()
  - Right to be forgotten - anonymize_user_data()
- **Privacy Controls**
  - Optional IP address collection
  - Optional user agent collection
  - Auto-anonymize on user deletion
  - Configurable data retention
- **Retention Policies**
  - Automatic comment cleanup after N days
  - Auto-anonymization of old comments
  - Management command: cleanup_comments
- **Data Export**
  - Complete user data export as JSON
  - Includes comments, flags, bans, moderation actions
  - Privacy-compliant format

#### Developer Experience (🔧)
- **60+ Configuration Settings** - Complete customization via DJANGO_COMMENTS_CONFIG
- **Comprehensive Signal System**
  - comment_created, comment_updated, comment_deleted
  - comment_flagged, comment_approved, comment_rejected
  - user_banned, user_unbanned
  - Extensible hook points for custom logic
- **Template Tags** - Convenient template tags with built-in caching
  - get_comments_for
  - get_root_comments_for
  - get_comment_count
  - show_comments
  - format_comment
- **Management Commands**
  - cleanup_comments - Remove old non-public comments
  - anonymize_old_comments - GDPR retention compliance
- **Full Internationalization (i18n)**
  - gettext_lazy throughout
  - English locale files included
  - Translation-ready strings
- **Comprehensive Logging**
  - Configurable logger name
  - Detailed error tracking
  - Debug information for development

#### Testing & Quality (🧪)
- **280+ Comprehensive Tests**
  - Unit tests for all models
  - Integration tests for workflows
  - API endpoint tests
  - Admin interface tests
  - Signal tests
  - Edge case coverage
- **High Test Coverage** - 90%+ code coverage
- **CI/CD Ready** - GitHub Actions workflow included
- **Code Quality Tools**
  - Black for formatting
  - isort for import sorting
  - Ruff for linting
  - mypy for type checking

#### Documentation (📚)
- **Complete Documentation**
  - Installation guide
  - Configuration reference (60+ settings)
  - API reference
  - Advanced usage guide
  - Contributing guide
- **Real-World Examples**
  - Blog comments
  - Product reviews
  - Discussion forums
  - News article comments
- **Best Practices** - Security, performance, and scalability guides

### Technical Details

#### Dependencies
- Django 3.2, 4.0, 4.1, 4.2, 5.0
- Python 3.8, 3.9, 3.10, 3.11, 3.12
- Django REST Framework 3.14.0+
- django-filter 23.0+
- bleach 6.0.0+

#### Optional Dependencies
- markdown 3.4.0+ (for Markdown support)
- celery 5.3.0+ (for async notifications)
- redis 4.5.0+ (for Celery broker)

#### Database Support
- PostgreSQL (recommended)
- MySQL/MariaDB
- SQLite (development only)
- Oracle

### Performance
- Optimized queries with select_related/prefetch_related
- Built-in caching support (Redis recommended)
- Async notification support via Celery
- Materialized path for efficient thread queries
- Database indexes on frequently queried fields

### Security
- XSS protection via bleach sanitization
- Rate limiting on API endpoints
- CSRF protection (Django standard)
- SQL injection protection (Django ORM)
- Safe HTML rendering in templates
- Configurable allowed HTML tags
- Spam detection to prevent abuse

### Migration Path
- No breaking changes from 0.x (this is first stable release)
- Comprehensive migration guide included
- Backward compatible configuration

---

## [Unreleased]

### Planned for v1.1
- [ ] GraphQL API support
- [ ] Real-time notifications with WebSockets
- [ ] Advanced analytics and reporting dashboard
- [ ] Comment reactions (likes, upvotes, downvotes)
- [ ] Media attachments (images, files)
- [ ] Vote-based sorting (Reddit-style)

### Planned for v1.2
- [ ] Multi-language comment moderation
- [ ] Enhanced AI-based spam detection
- [ ] Comment pinning and highlighting
- [ ] Import/export tools for migration
- [ ] Enhanced admin dashboard with charts

### Future Considerations
- Vue.js/React frontend components library
- Comment voting and reputation system
- Badge system for active commenters
- User reputation scoring
- Advanced analytics dashboard
- Mobile SDK (iOS/Android)

---

## Links

- **Homepage**: https://github.com/NzeStan/django-reusable-comments
- **Documentation**: https://django-reusable-comments.readthedocs.io/
- **Issue Tracker**: https://github.com/NzeStan/django-reusable-comments/issues
- **PyPI**: https://pypi.org/project/django-reusable-comments/

---

## Credits

**Author**: Ifeanyi Stanley Nnamani  
**Email**: nnamaniifeanyi10@gmail.com  
**License**: MIT

Special thanks to all contributors and the Django community!