# API Reference

This document provides a comprehensive reference for the Django Reusable Comments REST API.

## Base URL

All API endpoints are available under the base URL of `/comments/api/` by default. You can customize this by changing the URL configuration in your project.

## Authentication

The API supports the following authentication methods:

1. **Session Authentication** - For browser-based applications
2. **Token Authentication** - For mobile or single-page applications
3. **JWT Authentication** - If you add Django REST Framework JWT

Anonymous access is allowed for some read operations if `ALLOW_ANONYMOUS` is set to `True` in your configuration.

## API Endpoints

### Comments

#### List Comments

```
GET /comments/api/comments/
```

Retrieves a paginated list of comments.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `content_type` | string | Filter by content type (e.g., 'blog.post') |
| `object_id` | string | Filter by object ID |
| `user` | integer | Filter by user ID |
| `created_after` | datetime | Filter comments created after this date/time |
| `created_before` | datetime | Filter comments created before this date/time |
| `is_public` | boolean | Filter by public status |
| `is_removed` | boolean | Filter by removed status |
| `thread_id` | string | Filter by thread ID |
| `parent` | string | Filter by parent comment ID (use 'none' for root comments) |
| `is_root` | boolean | Filter for root comments (no parent) |
| `search` | string | Search comment content |
| `ordering` | string | Field to order by (e.g., 'created_at', '-created_at') |
| `page` | integer | Page number for pagination |
| `page_size` | integer | Number of results per page |

**Response:**

```json
{
  "count": 42,
  "next": "http://example.com/comments/api/comments/?page=2",
  "previous": null,
  "results": [
    {
      "id": "123",
      "content": "This is a comment",
      "content_object_info": {
        "content_type": "blog.post",
        "object_id": "456",
        "object_repr": "Blog Post Title"
      },
      "user_info": {
        "id": 1,
        "username": "johndoe",
        "display_name": "John Doe"
      },
      "user_name": "",
      "user_email": "",
      "user_url": "",
      "parent": null,
      "children": [
        {
          "id": "124",
          "content": "This is a reply",
          "user_info": {
            "id": 2,
            "username": "janedoe",
            "display_name": "Jane Doe"
          },
          "created_at": "2025-04-26T10:30:00Z",
          "updated_at": "2025-04-26T10:30:00Z",
          "is_public": true,
          "is_removed": false,
          "flags_count": 0,
          "is_flagged": false,
          "children": []
        }
      ],
      "depth": 0,
      "thread_id": "123",
      "created_at": "2025-04-26T10:00:00Z",
      "updated_at": "2025-04-26T10:00:00Z",
      "is_public": true,
      "is_removed": false,
      "flags_count": 0,
      "is_flagged": false
    }
  ]
}
```

#### Create Comment

```
POST /comments/api/comments/
```

Creates a new comment.

**Request Body:**

```json
{
  "content_type": "blog.post",
  "object_id": "456",
  "content": "This is a new comment",
  "parent": null,
  "user_name": "Anonymous",
  "user_email": "anonymous@example.com",
  "user_url": "https://example.com"
}
```

**Notes:**

- If the user is authenticated, the `user` field will be set automatically
- If the user is anonymous, the `user_name` field is required
- The `parent` field is optional and used for threaded comments
- `user_email` and `user_url` are optional

**Response:**

```json
{
  "id": "125",
  "content": "This is a new comment",
  "content_object_info": {
    "content_type": "blog.post",
    "object_id": "456",
    "object_repr": "Blog Post Title"
  },
  "user_info": null,
  "user_name": "Anonymous",
  "user_email": "anonymous@example.com",
  "user_url": "https://example.com",
  "parent": null,
  "children": [],
  "depth": 0,
  "thread_id": "125",
  "created_at": "2025-04-26T11:00:00Z",
  "updated_at": "2025-04-26T11:00:00Z",
  "is_public": true,
  "is_removed": false,
  "flags_count": 0,
  "is_flagged": false
}
```

#### Retrieve Comment

```
GET /comments/api/comments/{id}/
```

Retrieves a specific comment by ID.

**Response:**

```json
{
  "id": "123",
  "content": "This is a comment",
  "content_object_info": {
    "content_type": "blog.post",
    "object_id": "456",
    "object_repr": "Blog Post Title"
  },
  "user_info": {
    "id": 1,
    "username": "johndoe",
    "display_name": "John Doe"
  },
  "user_name": "",
  "user_email": "",
  "user_url": "",
  "parent": null,
  "children": [],
  "depth": 0,
  "thread_id": "123",
  "created_at": "2025-04-26T10:00:00Z",
  "updated_at": "2025-04-26T10:00:00Z",
  "is_public": true,
  "is_removed": false,
  "flags_count": 0,
  "is_flagged": false
}
```

#### Update Comment

```
PUT /comments/api/comments/{id}/
PATCH /comments/api/comments/{id}/
```

Updates a specific comment. Only the comment owner, moderators, or staff can update a comment.

**Request Body (PATCH example):**

```json
{
  "content": "This is an updated comment"
}
```

**Response:**

```json
{
  "id": "123",
  "content": "This is an updated comment",
  "content_object_info": {
    "content_type": "blog.post",
    "object_id": "456",
    "object_repr": "Blog Post Title"
  },
  "user_info": {
    "id": 1,
    "username": "johndoe",
    "display_name": "John Doe"
  },
  "user_name": "",
  "user_email": "",
  "user_url": "",
  "parent": null,
  "children": [],
  "depth": 0,
  "thread_id": "123",
  "created_at": "2025-04-26T10:00:00Z",
  "updated_at": "2025-04-26T11:30:00Z",
  "is_public": true,
  "is_removed": false,
  "flags_count": 0,
  "is_flagged": false
}
```

#### Delete Comment

```
DELETE /comments/api/comments/{id}/
```

Deletes a specific comment. Only the comment owner, moderators, or staff can delete a comment.

**Response:**

```
204 No Content
```

#### Flag Comment

```
POST /comments/api/comments/{id}/flag/
```

Flags a comment as inappropriate. Authenticated users only.

**Request Body:**

```json
{
  "flag_type": "spam",
  "reason": "This comment contains spam content"
}
```

**Available Flag Types:**

- `spam` - Spam content
- `offensive` - Offensive content
- `inappropriate` - Generally inappropriate content
- `other` - Other reason (please specify in the reason field)

**Response:**

```json
{
  "id": "789",
  "flag_type": "spam",
  "reason": "This comment contains spam content",
  "created_at": "2025-04-26T12:00:00Z"
}
```

#### Approve Comment

```
POST /comments/api/comments/{id}/approve/
```

Approves a comment (makes it public). Only moderators or staff can approve comments.

**Response:**

```json
{
  "detail": "Comment approved successfully."
}
```

#### Reject Comment

```
POST /comments/api/comments/{id}/reject/
```

Rejects a comment (makes it non-public). Only moderators or staff can reject comments.

**Response:**

```json
{
  "detail": "Comment rejected successfully."
}
```

### Comments for Specific Objects

#### List Comments for an Object

```
GET /comments/api/content/{content_type}/{object_id}/comments/
```

Retrieves comments for a specific object.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `thread_type` | string | Comment threading type ('flat', 'root', or 'tree') |
| `thread_id` | string | For 'tree' thread_type, get comments for a specific thread |
| `ordering` | string | Field to order by (e.g., 'created_at', '-created_at') |
| `page` | integer | Page number for pagination |
| `page_size` | integer | Number of results per page |

**Response:**

Similar to the List Comments endpoint, but filtered to the specific object.

## Error Responses

The API returns standard HTTP status codes and error messages:

### 400 Bad Request

```json
{
  "detail": "Error message",
  "errors": {
    "field_name": [
      "Error description"
    ]
  }
}
```

### 401 Unauthorized

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found

```json
{
  "detail": "Not found."
}
```

### 429 Too Many Requests

```json
{
  "detail": "Request was throttled. Expected available in 60 seconds."
}
```

## Pagination

All list endpoints are paginated by default. The default page size is 20, but can be customized in the settings.

Pagination response format:

```json
{
  "count": 42,
  "next": "http://example.com/api/resource/?page=2",
  "previous": null,
  "results": [
    // Resource objects
  ]
}
```

## Filtering and Sorting

The API supports filtering using query parameters and sorting using the `ordering` parameter.

Example for filtering:

```
GET /comments/api/comments/?content_type=blog.post&is_public=true&ordering=-created_at
```

## Rate Limiting

The API has rate limiting to prevent abuse. The default limit is 100 requests per day per user or IP address, but this can be customized in the settings.

When rate limited, the API will return a 429 status code with a message indicating when you can retry.

## Versioning

The API currently does not use explicit versioning, but future versions may include versioning via URL prefix or Accept headers.