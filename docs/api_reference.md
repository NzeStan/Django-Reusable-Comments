# API Reference

Complete REST API documentation for django-reusable-comments.

## API Endpoint Patterns

Django Reusable Comments provides two API patterns to suit different use cases:

### Pattern 1: Generic Comment Endpoint

**Base URL**: `/api/comments/`

**Purpose**: Full CRUD operations, admin dashboards, backend integrations, bulk actions

**Use when**:
- Building admin/moderation interfaces
- Performing bulk operations (approve/reject multiple comments)
- Backend service integrations (server-to-server)
- Analytics and reporting across all comments
- You need to filter/search comments across multiple objects

**Security model**: Standard Django REST Framework permissions. Suitable for authenticated backend services and admin interfaces.

**Example**:
```http
GET /api/comments/
POST /api/comments/
GET /api/comments/{id}/
PATCH /api/comments/{id}/
DELETE /api/comments/{id}/
```

---

### Pattern 2: Object-Specific Comment Endpoint (NEW in v1.0)

**Base URL**: `/api/{app_label}/{model}/{object_id}/comments/`

**Purpose**: Secure comment creation and listing for specific objects

**Use when**:
- Building public-facing frontends (React, Vue, vanilla JS)
- Mobile apps or untrusted clients
- You want the backend to control all metadata (content_type, object_id)
- Simpler frontend integration (frontend only needs object identifier)
- Enhanced security against impersonation attacks

**Security model**: Zero-trust architecture. The backend extracts `app_label`, `model`, and `object_id` from the URL path. Frontend clients only send comment content and optional parent ID. This prevents users from manipulating metadata to comment on unauthorized objects.

**Example**:
```http
GET /api/blog/post/123/comments/
POST /api/blog/post/123/comments/
```

---

### Choosing the Right Pattern

| Use Case | Recommended Pattern | Reason |
|----------|-------------------|---------|
| Public comment widget | Object-specific | Security, simplicity |
| Admin moderation dashboard | Generic | Need to see all comments |
| Mobile app | Object-specific | Untrusted client |
| Backend analytics | Generic | Query across objects |
| Bulk approve/reject | Generic | Operates on multiple comments |
| Server-to-server integration | Generic | Trusted environment |
| React/Vue component | Object-specific | Cleaner props, more secure |
| Comment export tool | Generic | Access all comments |

**Both patterns are fully supported and maintained.** Choose based on your security requirements and use case.

## Base URL

```
/api/comments/
```

All endpoints are relative to this base URL unless otherwise specified.

---

## Table of Contents

- [Authentication](#authentication)
- [Comments API](#comments-api)
- [Flags API](#flags-api)
- [Banned Users API](#banned-users-api)
- [Content Object Comments API](#content-object-comments-api)
- [Rate Limiting](#rate-limiting)
- [Error Responses](#error-responses)
- [Pagination](#pagination)
- [Filtering](#filtering)

---

## Authentication

The API supports multiple authentication methods:

### Session Authentication
```http
GET /api/comments/
Cookie: sessionid=abc123...
```

### Token Authentication
```http
GET /api/comments/
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

### Obtaining a Token
```http
POST /api-token-auth/
Content-Type: application/json

{
    "username": "your_username",
    "password": "your_password"
}
```

Response:
```json
{
    "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

---

## Comments API

### List Comments

Retrieve a list of comments using either the generic or object-specific endpoint.

---

#### Option 1: Generic Endpoint (All Comments with Filtering)

**Endpoint**: `GET /api/comments/`

**Use case**: Admin dashboards, analytics, cross-object queries

**Authentication**: Optional (public comments visible to all)

**Query Parameters**:
- `content_type` (string): Filter by content type (e.g., "blog.post")
- `object_id` (string/integer): Filter by object ID
- `user` (integer): Filter by user ID
- `is_public` (boolean): Filter by public status
- `is_removed` (boolean): Filter by removed status
- `parent__isnull` (boolean): Get only root comments (true) or only replies (false)
- `search` (string): Full-text search in content and user fields
- `ordering` (string): Sort field (e.g., "-created_at", "updated_at")
- `page` (integer): Page number
- `page_size` (integer): Results per page

**Example Requests**:
```http
# Get all public comments
GET /api/comments/?is_public=true

# Get comments for specific object
GET /api/comments/?content_type=blog.post&object_id=123

# Search across all comments
GET /api/comments/?search=Django&ordering=-created_at

# Get root comments only
GET /api/comments/?parent__isnull=true
```

---

#### Option 2: Object-Specific Endpoint (Comments for One Object)

**Endpoint**: `GET /api/{app_label}/{model}/{object_id}/comments/`

**Example**: `GET /api/blog/post/123/comments/`

**Use case**: Public-facing comment widgets, object-specific display

**Authentication**: Optional (public comments visible to all)

**Query Parameters**:
- `ordering` (string): Sort field (e.g., "-created_at", "updated_at")
- `search` (string): Full-text search in content and user fields
- `page` (integer): Page number
- `page_size` (integer): Results per page

**Note**: This endpoint automatically filters to show only comments for the specified object. You don't need to pass `content_type` or `object_id` as query parameters.

**Example Requests**:
```http
# Get all comments for blog post 123
GET /api/blog/post/123/comments/

# With ordering
GET /api/blog/post/123/comments/?ordering=-created_at

# With search
GET /api/blog/post/123/comments/?search=great

# With pagination
GET /api/blog/post/123/comments/?page=2&page_size=20
```

**Response** (Both endpoints return the same format):
```json
{
    "count": 42,
    "next": "http://example.com/api/comments/?page=2",
    "previous": null,
    "results": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "Great article!",
            "formatted_content": "Great article!",
            "user_info": {
                "id": 5,
                "username": "john_doe",
                "display_name": "John Doe"
            },
            "created_at": "2025-01-15T14:30:00Z",
            "is_public": true
        }
    ]
}
```

---

### Create Comment

Create a new comment using either the generic or object-specific endpoint.

---

#### Option 1: Generic Endpoint (Full Control)

**Endpoint**: `POST /api/comments/`

**Use case**: Admin tools, backend services, trusted clients

**Authentication**: Required

**Request Body**:
```json
{
    "content_type": "blog.post",
    "object_id": "123",
    "content": "This is my comment",
    "parent": "550e8400-e29b-41d4-a716-446655440000"  // Optional
}
```

**Field Descriptions**:
- `content_type` (required): Content type in format "app_label.model_name"
- `object_id` (required): ID of the object being commented on
- `content` (required): Comment text (max length configured in settings)
- `parent` (optional): UUID of parent comment for replies

**Example Request**:
```http
POST /api/comments/
Authorization: Token abc123...
Content-Type: application/json

{
    "content_type": "blog.post",
    "object_id": "123",
    "content": "This is an excellent article! Thanks for sharing."
}
```

**Success Response** (201 Created):
```json
{
    "id": "660f9500-f3ac-52e5-b827-557766551111",
    "content": "This is an excellent article! Thanks for sharing.",
    "formatted_content": "This is an excellent article! Thanks for sharing.",
    "content_object_info": {
        "content_type": "blog.post",
        "object_id": "123",
        "title": "My Blog Post"
    },
    "user_info": {
        "id": 5,
        "username": "john_doe",
        "display_name": "John Doe",
        "is_moderator": false
    },
    "parent": null,
    "depth": 0,
    "created_at": "2025-01-15T15:45:00Z",
    "is_public": true
}
```

---

#### Option 2: Object-Specific Endpoint (Secure, Recommended for Public Frontends)

**Endpoint**: `POST /api/{app_label}/{model}/{object_id}/comments/`

**Example**: `POST /api/blog/post/123/comments/`

**Use case**: Public-facing apps, untrusted clients, enhanced security

**Authentication**: Required

**Request Body**:
```json
{
    "content": "This is my comment",
    "parent": "550e8400-e29b-41d4-a716-446655440000"  // Optional
}
```

**Field Descriptions**:
- `content` (required): Comment text (max length configured in settings)
- `parent` (optional): UUID of parent comment for replies

**Security Note**: The `app_label`, `model`, and `object_id` are extracted from the URL path by the backend. The frontend should only send the comment `content` and optional `parent` ID. This prevents impersonation attacks where users could manipulate metadata to comment on unauthorized objects.

**Example Request**:
```http
POST /api/blog/post/123/comments/
Authorization: Token abc123...
Content-Type: application/json

{
    "content": "This is an excellent article! Thanks for sharing."
}
```

**Success Response**: Same as Option 1 (201 Created with full comment object)

---

**Error Responses** (Both endpoints):

400 Bad Request - Validation errors:
```json
{
    "content": ["This field is required."],
    "content_type": ["Invalid content type format."]
}
```

403 Forbidden - User is banned:
```json
{
    "detail": "You are banned from commenting until 2025-02-15.",
    "banned_until": "2025-02-15T00:00:00Z",
    "reason": "Repeated spam"
}
```

---

### Retrieve Comment

Get a single comment by ID.

**Endpoint**: `GET /api/comments/{id}/`

**Authentication**: Not required (for public comments)

**Example Request**:
```http
GET /api/comments/550e8400-e29b-41d4-a716-446655440000/
```

**Response**: Same format as individual comment in list response.

---

### Update Comment

Update a comment (partial or full update).

**Endpoint**: `PATCH /api/comments/{id}/` or `PUT /api/comments/{id}/`

**Authentication**: Required (owner or moderator)

**Permissions**:
- Comment owner can edit within configured time window
- Moderators can always edit

**Request Body**:
```json
{
    "content": "Updated comment content"
}
```

**Example Request**:
```http
PATCH /api/comments/550e8400-e29b-41d4-a716-446655440000/
Authorization: Token abc123...
Content-Type: application/json

{
    "content": "Updated: This is even better!"
}
```

**Success Response** (200 OK):
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "content": "Updated: This is even better!",
    "updated_at": "2025-01-15T16:00:00Z",
    ...
}
```

**Error Responses**:

403 Forbidden - Edit window expired:
```json
{
    "detail": "You can only edit comments within 1 hour of posting."
}
```

403 Forbidden - Not owner:
```json
{
    "detail": "You can only edit your own comments."
}
```

---

### Delete Comment

Delete (soft delete) a comment.

**Endpoint**: `DELETE /api/comments/{id}/`

**Authentication**: Required (owner or moderator)

**Example Request**:
```http
DELETE /api/comments/550e8400-e29b-41d4-a716-446655440000/
Authorization: Token abc123...
```

**Success Response** (204 No Content): Empty response

**Note**: This performs a soft delete by setting `is_removed=True`. The comment remains in the database but is hidden from public view.

---

### Approve Comment

Approve a comment (moderators only).

**Endpoint**: `POST /api/comments/{id}/approve/`

**Authentication**: Required (moderator permission)

**Permissions**: `django_comments.can_moderate_comments`

**Example Request**:
```http
POST /api/comments/550e8400-e29b-41d4-a716-446655440000/approve/
Authorization: Token abc123...
```

**Success Response** (200 OK):
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "is_public": true,
    "approved_at": "2025-01-15T16:30:00Z",
    "approved_by": {
        "id": 1,
        "username": "moderator",
        "display_name": "Moderator"
    }
}
```

---

### Reject Comment

Reject a comment (moderators only).

**Endpoint**: `POST /api/comments/{id}/reject/`

**Authentication**: Required (moderator permission)

**Request Body** (optional):
```json
{
    "reason": "Spam content"
}
```

**Example Request**:
```http
POST /api/comments/550e8400-e29b-41d4-a716-446655440000/reject/
Authorization: Token abc123...
Content-Type: application/json

{
    "reason": "Contains spam links"
}
```

**Success Response** (200 OK):
```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "is_public": false,
    "is_removed": true,
    "rejected_at": "2025-01-15T16:45:00Z",
    "rejected_by": {
        "id": 1,
        "username": "moderator"
    },
    "rejection_reason": "Contains spam links"
}
```

---

### Flag Comment

Flag a comment for moderation.

**Endpoint**: `POST /api/comments/{id}/flag/`

**Authentication**: Required

**Request Body**:
```json
{
    "flag": "spam",
    "reason": "This appears to be spam advertising"
}
```

**Flag Types**:
- `spam` - Spam or promotional content
- `inappropriate` - Inappropriate content
- `harassment` - Harassment or bullying
- `other` - Other reasons

**Example Request**:
```http
POST /api/comments/550e8400-e29b-41d4-a716-446655440000/flag/
Authorization: Token abc123...
Content-Type: application/json

{
    "flag": "spam",
    "reason": "Advertising casino websites"
}
```

**Success Response** (201 Created):
```json
{
    "id": "770f0600-g4bd-63f6-c938-668877662222",
    "comment": "550e8400-e29b-41d4-a716-446655440000",
    "flag": "spam",
    "reason": "Advertising casino websites",
    "created_at": "2025-01-15T17:00:00Z",
    "user_info": {
        "id": 5,
        "username": "john_doe"
    }
}
```

**Error Responses**:

400 Bad Request - Already flagged:
```json
{
    "detail": "You have already flagged this comment."
}
```

429 Too Many Requests - Rate limit exceeded:
```json
{
    "detail": "Flag rate limit exceeded. Try again in 1 hour."
}
```

---

### Bulk Approve

Approve multiple comments at once (moderators only).

**Endpoint**: `POST /api/comments/bulk_approve/`

**Authentication**: Required (moderator permission)

**Request Body**:
```json
{
    "comment_ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660f9500-f3ac-52e5-b827-557766551111",
        "770f0600-g4bd-63f6-c938-668877662222"
    ]
}
```

**Limits**: Maximum 100 IDs per request

**Example Request**:
```http
POST /api/comments/bulk_approve/
Authorization: Token abc123...
Content-Type: application/json

{
    "comment_ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660f9500-f3ac-52e5-b827-557766551111"
    ]
}
```

**Success Response** (200 OK):
```json
{
    "approved": 2,
    "failed": 0,
    "results": {
        "550e8400-e29b-41d4-a716-446655440000": "approved",
        "660f9500-f3ac-52e5-b827-557766551111": "approved"
    }
}
```

---

### Bulk Reject

Reject multiple comments at once (moderators only).

**Endpoint**: `POST /api/comments/bulk_reject/`

**Authentication**: Required (moderator permission)

**Request Body**:
```json
{
    "comment_ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660f9500-f3ac-52e5-b827-557766551111"
    ],
    "reason": "Spam comments"
}
```

**Response**: Same format as bulk approve

---

### Bulk Delete

Delete multiple comments at once (moderators only).

**Endpoint**: `POST /api/comments/bulk_delete/`

**Authentication**: Required (moderator permission)

**Request Body**:
```json
{
    "comment_ids": [
        "550e8400-e29b-41d4-a716-446655440000",
        "660f9500-f3ac-52e5-b827-557766551111"
    ]
}
```

**Response**: Same format as bulk approve

---

### Edit History

Get the edit history of a comment.

**Endpoint**: `GET /api/comments/{id}/history/`

**Authentication**: Required (owner or moderator)

**Example Request**:
```http
GET /api/comments/550e8400-e29b-41d4-a716-446655440000/history/
Authorization: Token abc123...
```

**Response**:
```json
[
    {
        "id": 1,
        "comment": "550e8400-e29b-41d4-a716-446655440000",
        "previous_content": "Original comment text",
        "edited_at": "2025-01-15T16:00:00Z",
        "edited_by": {
            "id": 5,
            "username": "john_doe"
        }
    }
]
```

---

### User Stats

Get comment statistics for the authenticated user.

**Endpoint**: `GET /api/comments/user_stats/`

**Authentication**: Required

**Example Request**:
```http
GET /api/comments/user_stats/
Authorization: Token abc123...
```

**Response**:
```json
{
    "total_comments": 42,
    "public_comments": 40,
    "flagged_comments": 1,
    "rejected_comments": 1,
    "approved_comments": 38,
    "last_comment_at": "2025-01-15T17:30:00Z"
}
```

---

## Flags API

### List Flags

Get a list of all comment flags (moderators only).

**Endpoint**: `GET /api/flags/`

**Authentication**: Required (moderator permission)

**Query Parameters**:
- `comment` (uuid): Filter by comment ID
- `user` (integer): Filter by user who flagged
- `flag` (string): Filter by flag type (spam, inappropriate, etc.)
- `is_reviewed` (boolean): Filter by review status
- `ordering` (string): Sort field

**Example Request**:
```http
GET /api/flags/?flag=spam&is_reviewed=false
Authorization: Token abc123...
```

**Response**:
```json
{
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "770f0600-g4bd-63f6-c938-668877662222",
            "comment": "550e8400-e29b-41d4-a716-446655440000",
            "flag": "spam",
            "reason": "Advertising content",
            "created_at": "2025-01-15T17:00:00Z",
            "is_reviewed": false,
            "reviewed_at": null,
            "reviewed_by": null,
            "review_action": null,
            "user_info": {
                "id": 5,
                "username": "john_doe"
            }
        }
    ]
}
```

---

### Review Flag

Mark a flag as reviewed (moderators only).

**Endpoint**: `POST /api/flags/{id}/review/`

**Authentication**: Required (moderator permission)

**Request Body**:
```json
{
    "action": "dismissed",  // or "actioned"
    "notes": "Reviewed and found not spam"
}
```

**Example Request**:
```http
POST /api/flags/770f0600-g4bd-63f6-c938-668877662222/review/
Authorization: Token abc123...
Content-Type: application/json

{
    "action": "dismissed",
    "notes": "False positive - legitimate comment"
}
```

**Success Response** (200 OK):
```json
{
    "id": "770f0600-g4bd-63f6-c938-668877662222",
    "is_reviewed": true,
    "reviewed_at": "2025-01-15T18:00:00Z",
    "reviewed_by": {
        "id": 1,
        "username": "moderator"
    },
    "review_action": "dismissed",
    "review_notes": "False positive - legitimate comment"
}
```

---

## Banned Users API

### List Banned Users

Get a list of banned users (moderators only).

**Endpoint**: `GET /api/banned-users/`

**Authentication**: Required (moderator permission)

**Query Parameters**:
- `user` (integer): Filter by user ID
- `is_active` (boolean): Filter by active bans
- `ordering` (string): Sort field

**Example Request**:
```http
GET /api/banned-users/?is_active=true
Authorization: Token abc123...
```

**Response**:
```json
{
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "user": {
                "id": 10,
                "username": "spammer"
            },
            "banned_by": {
                "id": 1,
                "username": "moderator"
            },
            "reason": "Repeated spam",
            "created_at": "2025-01-10T00:00:00Z",
            "banned_until": "2025-02-10T00:00:00Z",
            "is_active": true,
            "is_permanent": false
        }
    ]
}
```

---

### Ban User

Ban a user from commenting (moderators only).

**Endpoint**: `POST /api/banned-users/`

**Authentication**: Required (moderator permission)

**Request Body**:
```json
{
    "user": 10,
    "reason": "Repeated violations of community guidelines",
    "banned_until": "2025-03-15T00:00:00Z"  // null for permanent
}
```

**Example Request**:
```http
POST /api/banned-users/
Authorization: Token abc123...
Content-Type: application/json

{
    "user": 10,
    "reason": "Spam",
    "banned_until": null
}
```

**Success Response** (201 Created):
```json
{
    "id": 3,
    "user": {
        "id": 10,
        "username": "problem_user"
    },
    "banned_by": {
        "id": 1,
        "username": "moderator"
    },
    "reason": "Spam",
    "created_at": "2025-01-15T18:30:00Z",
    "banned_until": null,
    "is_active": true,
    "is_permanent": true
}
```

---

### Unban User

Remove a user ban (moderators only).

**Endpoint**: `DELETE /api/banned-users/{id}/`

**Authentication**: Required (moderator permission)

**Example Request**:
```http
DELETE /api/banned-users/3/
Authorization: Token abc123...
```

**Success Response** (204 No Content): Empty response

---

## Content Object Comments API

### Get Comments for Object

Get all comments for a specific content object.

**Endpoint**: `GET /api/content/<content_type>/<object_id>/comments/`

**Authentication**: Not required

**Path Parameters**:
- `content_type`: Content type in format "app_label.model_name"
- `object_id`: ID of the object

**Query Parameters**: Same as regular comments list

**Example Request**:
```http
GET /api/content/blog.post/123/comments/?ordering=-created_at
```

**Response**: Same format as comments list

---

## Rate Limiting

The API implements 3-tier rate limiting:

### User Rate Limits
Authenticated users:
- **Daily Limit**: 100 requests/day (configurable)
- **Burst Limit**: 5 requests/minute (configurable)

### Anonymous Rate Limits
Unauthenticated users:
- **Daily Limit**: 20 requests/day (configurable)
- **Burst Limit**: 5 requests/minute (configurable)

### Rate Limit Headers

Responses include rate limit information:
```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642348800
```

### Rate Limit Exceeded Response

```json
{
    "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

**Status Code**: 429 Too Many Requests

---

## Error Responses

### Standard Error Format

```json
{
    "detail": "Error message here"
}
```

### Validation Errors

```json
{
    "field_name": [
        "Error message for this field"
    ],
    "another_field": [
        "First error",
        "Second error"
    ]
}
```

### Common Status Codes

- **200 OK**: Request succeeded
- **201 Created**: Resource created successfully
- **204 No Content**: Request succeeded (no content to return)
- **400 Bad Request**: Validation error or malformed request
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Permission denied
- **404 Not Found**: Resource not found
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

---

## Pagination

### Default Pagination

The API uses cursor pagination by default:

```json
{
    "count": 100,
    "next": "http://example.com/api/comments/?page=2",
    "previous": null,
    "results": [...]
}
```

### Page Size Control

Control page size with `page_size` parameter:

```http
GET /api/comments/?page_size=50
```

**Limits**:
- Default: 20 items
- Maximum: 100 items

### Navigating Pages

```http
# First page
GET /api/comments/?page=1

# Next page
GET /api/comments/?page=2

# Specific page with custom size
GET /api/comments/?page=3&page_size=30
```

---

## Filtering

### By Content Object

```http
GET /api/comments/?content_type=blog.post&object_id=123
```

### By User

```http
GET /api/comments/?user=5
```

### By Status

```http
GET /api/comments/?is_public=true
GET /api/comments/?is_removed=false
```

### By Parent (Thread Filtering)

```http
# Get root comments only
GET /api/comments/?parent__isnull=true

# Get replies to specific comment
GET /api/comments/?parent=550e8400-e29b-41d4-a716-446655440000
```

### Full-Text Search

```http
GET /api/comments/?search=keyword
```

Searches in:
- Comment content
- User name
- Username
- User first/last name

### Ordering

```http
# Newest first
GET /api/comments/?ordering=-created_at

# Oldest first
GET /api/comments/?ordering=created_at

# Most recently updated
GET /api/comments/?ordering=-updated_at
```

### Combined Filters

```http
GET /api/comments/?content_type=blog.post&object_id=123&is_public=true&ordering=-created_at&search=keyword&page_size=50
```

---

## Response Field Reference

### Comment Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique comment identifier |
| `content` | String | Raw comment content |
| `formatted_content` | String | Formatted/sanitized content for display |
| `content_object_info` | Object | Information about commented object |
| `user_info` | Object | Comment author information |
| `parent` | UUID | Parent comment ID (null for root) |
| `children` | Array | Nested child comments |
| `depth` | Integer | Comment depth in thread |
| `thread_id` | UUID | Root comment ID for this thread |
| `children_count` | Integer | Number of direct replies |
| `created_at` | DateTime | Creation timestamp |
| `updated_at` | DateTime | Last update timestamp |
| `is_public` | Boolean | Public/approved status |
| `is_removed` | Boolean | Soft delete status |
| `flags_count` | Integer | Number of user flags |
| `is_flagged` | Boolean | Whether user has flagged this comment |
| `revisions_count` | Integer | Number of edits |
| `moderation_actions_count` | Integer | Number of moderation actions |

### User Info Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | User ID |
| `username` | String | Username |
| `display_name` | String | Full name or username |
| `is_moderator` | Boolean | Moderator permission status |

### Content Object Info

| Field | Type | Description |
|-------|------|-------------|
| `content_type` | String | Content type (app_label.model) |
| `object_id` | String | Object ID |
| `title` | String | Object title (if available) |

---

## Examples

### Complete Workflow Example

---

#### Using Generic Endpoint (Backend/Admin Use Case)
```javascript
// 1. Authenticate
const authResponse = await fetch('/api-token-auth/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'user',
        password: 'pass'
    })
});
const { token } = await authResponse.json();

// 2. Create comment
const commentResponse = await fetch('/api/comments/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
        content_type: 'blog.post',
        object_id: '123',
        content: 'Great article!'
    })
});
const comment = await commentResponse.json();

// 3. List comments for object
const listResponse = await fetch(
    '/api/comments/?content_type=blog.post&object_id=123&ordering=-created_at'
);
const { results } = await listResponse.json();

// 4. Reply to comment
const replyResponse = await fetch('/api/comments/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
        content_type: 'blog.post',
        object_id: '123',
        content: 'Thanks!',
        parent: comment.id
    })
});
```

---

#### Using Object-Specific Endpoint (Frontend Use Case)
```javascript
// 1. Authenticate (same as above)
const authResponse = await fetch('/api-token-auth/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'user',
        password: 'pass'
    })
});
const { token } = await authResponse.json();

// 2. Create comment (simpler - backend handles metadata)
const commentResponse = await fetch('/api/blog/post/123/comments/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
        content: 'Great article!'
    })
});
const comment = await commentResponse.json();

// 3. List comments for object (simpler URL)
const listResponse = await fetch(
    '/api/blog/post/123/comments/?ordering=-created_at'
);
const { results } = await listResponse.json();

// 4. Reply to comment
const replyResponse = await fetch('/api/blog/post/123/comments/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
        content: 'Thanks!',
        parent: comment.id
    })
});
```

---

### Client Libraries

---

#### Python

**Generic Endpoint:**
```python
import requests

API_URL = 'http://example.com/api/comments/'
TOKEN = 'your-token-here'

# Create comment
response = requests.post(
    API_URL,
    headers={'Authorization': f'Token {TOKEN}'},
    json={
        'content_type': 'blog.post',
        'object_id': '123',
        'content': 'Great article!'
    }
)
comment = response.json()

# List comments
response = requests.get(
    API_URL,
    params={
        'content_type': 'blog.post',
        'object_id': '123',
        'ordering': '-created_at'
    }
)
comments = response.json()['results']
```

**Object-Specific Endpoint (Recommended for security):**
```python
import requests

TOKEN = 'your-token-here'

# Create comment
response = requests.post(
    'http://example.com/api/blog/post/123/comments/',
    headers={'Authorization': f'Token {TOKEN}'},
    json={
        'content': 'Great article!'
    }
)
comment = response.json()

# List comments
response = requests.get(
    'http://example.com/api/blog/post/123/comments/',
    params={
        'ordering': '-created_at'
    }
)
comments = response.json()['results']
```

---

#### JavaScript (Axios)

**Generic Endpoint:**
```javascript
import axios from 'axios';

const api = axios.create({
    baseURL: 'http://example.com/api',
    headers: {
        'Authorization': 'Token your-token-here'
    }
});

// Create comment
const { data: comment } = await api.post('/comments/', {
    content_type: 'blog.post',
    object_id: '123',
    content: 'Great article!'
});

// List comments
const { data } = await api.get('/comments/', {
    params: {
        content_type: 'blog.post',
        object_id: '123',
        ordering: '-created_at'
    }
});
const comments = data.results;
```

**Object-Specific Endpoint (Recommended for public apps):**
```javascript
import axios from 'axios';

const api = axios.create({
    baseURL: 'http://example.com/api',
    headers: {
        'Authorization': 'Token your-token-here'
    }
});

// Create comment
const { data: comment } = await api.post('/blog/post/123/comments/', {
    content: 'Great article!'
});

// List comments
const { data } = await api.get('/blog/post/123/comments/', {
    params: {
        ordering: '-created_at'
    }
});
const comments = data.results;
```

---

## Webhooks (Future Feature)

Webhook support is planned for future releases. This will allow you to receive real-time notifications when:
- Comments are created
- Comments are flagged
- Auto-moderation triggers
- Users are banned

Stay tuned for updates!

---

## API Versioning

The current API is v1 (implicit). Future breaking changes will be introduced through versioned endpoints:

```
/api/v2/comments/  # Future version
```

The v1 API will remain stable and supported for the foreseeable future.

---

**Need help with the API?**  
Check the [Advanced Usage Guide](advanced_usage.md) for integration patterns and examples.