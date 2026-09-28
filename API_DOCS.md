# NotifyFlow API Documentation & Reference Manual

## Base URL
```
http://localhost:8000
```
Interactive Swagger UI is available at `/docs` and ReDoc at `/redoc`.

---

## 1. Notifications

### 1.1 Send Transactional Email Notification
Asynchronously validates, caches, and enqueues a transactional email notification request to RabbitMQ.

- **Endpoint**: `POST /api/notifications/email`
- **Status Code**: `202 Accepted`
- **Rate Limit**: Default `60` requests per minute per IP address.

#### Request Headers
| Header | Type | Description |
|---|---|---|
| `Content-Type` | string | `application/json` (Required) |
| `X-Forwarded-For` | string | Client IP (Optional, extracted automatically) |

#### Request Body
```json
{
  "recipient_email": "john.doe@example.com",
  "template_id": "order-confirmation",
  "dynamic_data": {
    "order_id": "ORD-12345",
    "customer_name": "John Doe",
    "product_name": "NotifyFlow Enterprise Suite",
    "total_amount": "$499.00",
    "shipping_address": "123 Innovation Drive, Silicon Valley, CA",
    "delivery_date": "October 5, 2026"
  }
}
```

#### Successful Response (`202 Accepted`)
```json
{
  "notification_id": "c71a39f6-6c7b-4d51-8e54-bf63c631a54b",
  "status": "queued",
  "message": "Notification request accepted and queued for asynchronous processing.",
  "recipient_email": "john.doe@example.com",
  "template_id": "order-confirmation",
  "timestamp": "2026-09-28T12:00:00.000000Z"
}
```

#### Response Headers
| Header | Description |
|---|---|
| `X-RateLimit-Limit` | Maximum requests allowed per window (e.g. 60) |
| `X-RateLimit-Remaining` | Remaining requests allowed in current window |
| `X-RateLimit-Reset` | Time in seconds until quota resets |
| `X-Process-Time-Ms` | API latency in milliseconds (e.g. `2.15`) |

#### Error Responses
- **`400 Bad Request`**: Template does not exist.
  ```json
  {
    "detail": "Email template 'invalid-template' was not found in the system."
  }
  ```
- **`422 Unprocessable Entity`**: Invalid email or missing required fields.
  ```json
  {
    "detail": [
      {
        "type": "value_error",
        "loc": ["body", "recipient_email"],
        "msg": "value is not a valid email address"
      }
    ]
  }
  ```
- **`429 Too Many Requests`**: Rate limit exceeded.
  ```json
  {
    "detail": {
      "error": "Rate limit exceeded",
      "message": "Maximum allowed requests (60 per minute) exceeded. Please retry in 42 seconds.",
      "limit": 60,
      "current_count": 61,
      "reset_in_seconds": 42
    }
  }
  ```

#### cURL Example
```bash
curl -X POST "http://localhost:8000/api/notifications/email" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "john.doe@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-12345",
      "customer_name": "John Doe",
      "product_name": "NotifyFlow Pro",
      "total_amount": "$299.00"
    }
  }'
```

---

## 2. Health & Monitoring

### 2.1 Health Check
Verifies connectivity and operational state for the API service, PostgreSQL database, Redis cache, and RabbitMQ broker.

- **Endpoint**: `GET /health`
- **Status Codes**: `200 OK` (Healthy) | `503 Service Unavailable` (Degraded/Unhealthy)

#### Response Example (`200 OK`)
```json
{
  "status": "healthy",
  "timestamp": "2026-09-28T12:00:00.000000Z",
  "services": {
    "database": {
      "status": "healthy",
      "details": "PostgreSQL connection active"
    },
    "redis": {
      "status": "healthy",
      "details": "Redis cache connected"
    },
    "rabbitmq": {
      "status": "healthy",
      "details": "RabbitMQ channel open"
    }
  }
}
```

---

## 3. Template Management

### 3.1 List All Templates
- **Endpoint**: `GET /api/templates`
- **Status**: `200 OK`

### 3.2 Get Template By ID
- **Endpoint**: `GET /api/templates/{template_id}`
- **Status**: `200 OK` | `404 Not Found`

### 3.3 Create Template
- **Endpoint**: `POST /api/templates`
- **Status**: `201 Created`
```json
{
  "id": "welcome-newsletter",
  "name": "Welcome Newsletter",
  "subject_template": "Welcome to our newsletter, {{ user_name }}!",
  "body_template": "Hi {{ user_name }},\n\nThanks for subscribing!",
  "language": "en"
}
```

### 3.4 Update Template
- **Endpoint**: `PUT /api/templates/{template_id}`
- **Status**: `200 OK`

### 3.5 Delete Template
- **Endpoint**: `DELETE /api/templates/{template_id}`
- **Status**: `204 No Content`

---

## 4. User Preferences Management

### 4.1 Get Preferences
- **Endpoint**: `GET /api/preferences/{email}`
- **Status**: `200 OK`
```json
{
  "user_id": "usr-001",
  "email": "john.doe@example.com",
  "email_opt_out": false,
  "preferred_language": "en"
}
```

### 4.2 Update Preferences
- **Endpoint**: `PUT /api/preferences/{email}`
- **Status**: `200 OK`
```json
{
  "email_opt_out": true,
  "preferred_language": "es"
}
```
