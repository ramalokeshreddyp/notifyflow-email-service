# NotifyFlow - Event-Driven Transactional Email Notification Service API

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600.svg?logo=rabbitmq&logoColor=white)](https://www.rabbitmq.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-29%20Passed-brightgreen.svg)]()

> A high-throughput, event-driven backend service for transactional email notifications. Decouples notification dispatch using **RabbitMQ message queuing**, optimizes read latencies and rate limits with **Redis caching**, persists schemas and audit state in **PostgreSQL**, and renders dynamic content with **Jinja2**.

---

## 📑 Table of Contents
- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Quick Start with Docker Compose](#-quick-start-with-docker-compose)
- [Environment Variables](#-environment-variables)
- [API Endpoints Reference](#-api-endpoints-reference)
- [Automated Testing](#-automated-testing)
- [Database Seed Data](#-database-seed-data)
- [Error Handling & Fault Tolerance](#-error-handling--fault-tolerance)
- [License](#-license)

---

## 🎯 Overview

Synchronous notification delivery creates latency bottlenecks and introduces external dependencies into critical business operations (e.g., checkout or signup flows). **NotifyFlow** solves this by:
1. Instantly accepting incoming requests and publishing durable events onto RabbitMQ.
2. Returning an `HTTP 202 Accepted` response with sub-millisecond API latency.
3. Asynchronously processing events in dedicated Worker instances: retrieving templates, verifying user preferences, rendering content, and simulating dispatch with full poison-message safety.
4. Caching templates and user preferences in Redis to protect database load during traffic spikes.
5. Protecting API infrastructure against bursts via Redis-backed rate limiting per IP.

---

## 🏛 System Architecture

```mermaid
flowchart LR
    Client["Client Request\n(Checkout / Auth)"] -->|POST /api/notifications/email| API["API Service\n(FastAPI Producer)"]
    
    subgraph In-Memory Cache & Limits
        Redis[("Redis 7\n(Templates, Prefs, Rate Limits)")]
    end
    
    subgraph Persistent Storage
        Postgres[("PostgreSQL 16\n(Templates & Preferences)")]
    end
    
    subgraph AMQP Message Broker
        Exchange{"Topic Exchange\n(notifications_exchange)"}
        Queue[("Durable Queue\n(email_notifications)")]
        DLQ[("Dead Letter Queue\n(email_notifications_dlq)")]
    end
    
    subgraph Worker Pool
        Worker["Worker Service\n(Consumer & Jinja2 Renderer)"]
    end
    
    API -->|1. Check Rate Limit| Redis
    API -->|2. Check/Warm Cache| Redis
    Redis -.->|Cache Miss| Postgres
    API -->|3. Publish Event| Exchange
    API -->|4. 202 Accepted| Client
    Exchange -->|notification.email| Queue
    Queue -->|Consume| Worker
    Worker -->|Fetch Template/Prefs| Redis
    Worker -->|Log Rendered Output| Logs[("Console / Delivery Logs")]
    Worker -.->|Poison / Corrupted| DLQ
```

For comprehensive sequence diagrams and architectural design choices, see [ARCHITECTURE.md](file:///c:/Users/lokes/Desktop/Gpp-40/ARCHITECTURE.md).

---

## ✨ Key Features

- ⚡ **Non-Blocking Asynchronous API**: Returns `202 Accepted` immediately upon queuing.
- 📬 **Reliable Message Queuing**: Durable exchanges, persistent messages (`delivery_mode=2`), and manual worker acknowledgments prevent message loss.
- 🚀 **Redis Cache-Aside Architecture**: Caches templates (`template:<id>`) and user preferences (`user_prefs:<email>`) with automated cache warming and invalidation.
- 🛡️ **Distributed Rate Limiting**: Enforces rate limiting per IP using atomic Redis operations (`X-RateLimit-*` and `Retry-After` headers).
- 🧩 **Dynamic Template Engine**: Jinja2 templating with custom formatting filters (currency, defaults, safe escaping).
- 🔕 **User Preference & Opt-Out Enforcement**: Automatically respects user opt-out preferences and bypasses dispatch without crashing or blocking queues.
- 🛑 **Poison Message Protection**: Traps malformed messages and missing templates, logging detailed alerts and routing to Dead Letter Queues (DLQ).
- 🐳 **Full Docker Orchestration**: All 5 services (`api`, `worker`, `rabbitmq`, `redis`, `postgres`) run seamlessly via `docker-compose up` with built-in health checks.

---

## 🛠 Technology Stack

| Layer | Component | Description |
|---|---|---|
| **API Framework** | FastAPI (Python 3.11+) | High-performance asynchronous REST API with OpenAPI/Swagger |
| **Validation** | Pydantic v2 & EmailValidator | Strict schema validation and serialization |
| **Message Broker** | RabbitMQ 3.13 | AMQP 0-9-1 broker with Management Web UI |
| **Broker Client** | aio-pika | Asynchronous, non-blocking AMQP client |
| **Cache & Rate Limit** | Redis 7 (Alpine) | In-memory key-value store with atomic pipelines |
| **Database** | PostgreSQL 16 (Alpine) | Relational database with automatic `init-db.sql` seeding |
| **ORM / Driver** | SQLAlchemy 2.0 & asyncpg | Asynchronous PostgreSQL connection pool |
| **Template Engine** | Jinja2 | Sandboxed template engine for email subjects and bodies |
| **Testing** | Pytest & Pytest-asyncio | Full unit and integration test suites |

---

## 📂 Project Structure

```
notifyflow-email-service/
├── .env.example                 # Documented environment variables template
├── .env                         # Default environment configuration
├── .gitignore                   # Git ignore rules
├── docker-compose.yml           # Multi-container orchestration with health checks
├── pytest.ini                   # Pytest configuration
├── README.md                    # Project documentation
├── ARCHITECTURE.md              # Detailed architecture & sequence diagrams
├── API_DOCS.md                  # Comprehensive API reference & cURL examples
├── database/
│   └── init-db.sql              # Database schema & initial seed data
├── api/
│   ├── Dockerfile               # API service Docker build
│   ├── requirements.txt         # API service dependencies
│   └── src/
│       ├── main.py              # FastAPI application entrypoint
│       ├── config.py            # Pydantic Settings configuration
│       ├── database.py          # SQLAlchemy async engine & sessionmaker
│       ├── models/
│       │   ├── db_models.py     # SQLAlchemy ORM models
│       │   └── schemas.py       # Pydantic request/response schemas
│       ├── services/
│       │   ├── cache_service.py # Redis template & preference caching
│       │   ├── rate_limiter.py  # Redis IP-based rate limiting
│       │   └── rabbitmq_service.py # RabbitMQ durable publisher
│       └── routes/
│           ├── health.py        # System health check endpoint
│           ├── notifications.py # POST /api/notifications/email
│           ├── templates.py     # Template CRUD endpoints
│           └── preferences.py   # User preferences endpoints
├── worker/
│   ├── Dockerfile               # Worker service Docker build
│   ├── requirements.txt         # Worker dependencies
│   └── src/
│       ├── consumer.py          # RabbitMQ consumer & dispatch simulator
│       ├── config.py            # Worker settings
│       ├── database.py          # Worker async DB session
│       ├── models.py            # Worker ORM models
│       ├── cache_service.py     # Worker Redis cache client
│       └── template_engine.py   # Jinja2 template rendering engine
└── tests/
    ├── conftest.py              # Pytest fixtures & in-memory test setup
    ├── unit/
    │   ├── test_api_validation.py      # Request validation tests
    │   ├── test_rate_limiter.py       # Rate limiting tests
    │   ├── test_caching.py            # Redis cache hit/miss tests
    │   ├── test_template_rendering.py # Jinja2 rendering tests
    │   └── test_worker_consumer.py    # Worker message handling tests
    └── integration/
        ├── test_api_endpoints.py      # API endpoint integration tests
        └── test_notification_flow.py  # End-to-end event flow tests
```

---

## 🚀 Quick Start with Docker Compose

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24.0+)
- [Docker Compose](https://docs.docker.com/compose/) (v2.20+)

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/ramalokeshreddyp/notifyflow-email-service.git
cd notifyflow-email-service
cp .env.example .env
```

### 2. Launch All Services
```bash
docker-compose up --build
```
This single command spins up:
- **PostgreSQL Database** (`localhost:5432`) - Auto-seeded with templates and user preferences.
- **Redis Cache** (`localhost:6379`) - In-memory cache & rate limiter.
- **RabbitMQ Message Broker** (`localhost:5672`) + **Management Web UI** (`http://localhost:15672`, user: `guest`, pass: `guest`).
- **FastAPI Service** (`http://localhost:8000`) - Interactive docs at `http://localhost:8000/docs`.
- **Worker Service** - Background consumer listening on `email_notifications` queue.

### 3. Verify Health Check
```bash
curl http://localhost:8000/health
```

---

## ⚙️ Environment Variables

All variables have production-ready defaults in `.env.example`:

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `production`, `testing`) |
| `API_PORT` | `8000` | Port exposed by the FastAPI server |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/notification_db` | Async SQLAlchemy DB connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `CACHE_TTL_SECONDS` | `3600` | Expiration time for cached templates & preferences (1 hour) |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max allowed requests per minute per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limiting sliding window duration in seconds |
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` | AMQP connection URL |
| `RABBITMQ_QUEUE` | `email_notifications` | Primary durable queue name |
| `RABBITMQ_EXCHANGE` | `notifications_exchange` | Topic exchange name |
| `RABBITMQ_ROUTING_KEY` | `notification.email` | Routing key for transactional emails |
| `RABBITMQ_DEAD_LETTER_QUEUE`| `email_notifications_dlq` | Dead Letter Queue for poison messages |

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/notifications/email` | Send transactional email notification (Async) | `202 Accepted` |
| `GET` | `/health` | System health check (API, DB, Redis, RabbitMQ) | `200 OK` |
| `GET` | `/api/templates` | List all available email templates | `200 OK` |
| `GET` | `/api/templates/{id}` | Retrieve email template by ID (Cache-first) | `200 OK` |
| `POST` | `/api/templates` | Create a new notification template | `201 Created` |
| `PUT` | `/api/templates/{id}` | Update template and invalidate cache | `200 OK` |
| `DELETE`| `/api/templates/{id}` | Delete template and invalidate cache | `204 No Content` |
| `GET` | `/api/preferences/{email}`| Get user notification preferences | `200 OK` |
| `PUT` | `/api/preferences/{email}`| Update user opt-out status / preferences | `200 OK` |

### Sample Notification Request
```bash
curl -X POST "http://localhost:8000/api/notifications/email" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "john.doe@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-7890",
      "customer_name": "John Doe",
      "product_name": "Pro Developer License",
      "total_amount": "$199.00",
      "shipping_address": "123 Tech Blvd, San Francisco, CA"
    }
  }'
```

### Sample Response (`202 Accepted`)
```json
{
  "notification_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Notification request accepted and queued for asynchronous processing.",
  "recipient_email": "john.doe@example.com",
  "template_id": "order-confirmation",
  "timestamp": "2026-09-28T12:00:00.000000Z"
}
```

### Sample Worker Console Log Output
```
============================================================
[EMAIL_DISPATCHED] Simulated Transactional Email Sent Successfully
Notification ID: 550e8400-e29b-41d4-a716-446655440000
Recipient:       john.doe@example.com
Template ID:     order-confirmation (Order Confirmation)
Subject:         Order Confirmation #ORD-7890 - Thank You for Your Purchase!
------------------- Email Body -------------------
Hello John Doe,

Thank you for your order! Your purchase of Pro Developer License (Order ID: ORD-7890) for a total of $199.00 has been confirmed and is being processed.

Shipping Address: 123 Tech Blvd, San Francisco, CA
Estimated Delivery: 3-5 business days

Thank you for shopping with us!
The NotifyFlow Team
============================================================
```

---

## 🧪 Automated Testing

The repository contains 29 comprehensive unit and integration tests covering all critical paths:

### Run Tests Locally
```bash
python -m pytest
```

### Run Tests in Docker
```bash
docker-compose exec api pytest
```

### Test Suite Coverage
- **API Validation**: Tests valid payloads, bad email formats, empty fields, dynamic dictionary data.
- **Rate Limiting**: Tests threshold enforcement, quota resets, multi-IP segregation, and fail-open resilience.
- **Redis Caching**: Tests template and preference caching, cache hits, cache misses, and cache invalidation.
- **Jinja2 Templating**: Tests variable injection, silent undefined fallbacks, custom currency formatting, HTML escaping.
- **Worker Message Consumption**: Tests opt-out skipping, normal dispatch logging, missing template handling, malformed JSON recovery.
- **End-to-End Flow**: Full integration pipeline from API ingestion to RabbitMQ publish, Worker consumption, and rendering.

---

## 💾 Database Seed Data

Upon startup, `database/init-db.sql` automatically populates the database:

### 1. Pre-Configured Templates
1. `order-confirmation` - E-commerce purchase confirmation with product and pricing details.
2. `password-reset` - Security password reset with expiring verification links.
3. `account-alert` - Security notifications for new device logins or suspicious activity.
4. `welcome-email` - Customer onboarding welcome message.
5. `payment-receipt` - Invoice receipt and billing notification.

### 2. Sample User Preferences
- `john.doe@example.com` (Opt-out: `false`, Language: `en`)
- `jane.smith@example.com` (Opt-out: `false`, Language: `en`)
- `optedout.user@example.com` (Opt-out: `true`, Language: `en`)
- `alex.tech@example.com` (Opt-out: `false`, Language: `es`)
- `sarah.connor@example.com` (Opt-out: `false`, Language: `en`)

---

## 🛡️ Error Handling & Fault Tolerance

1. **Poison Message Neutralization**: If a message contains invalid data or an unresolvable template, the worker logs the error with full diagnostic context and acknowledges the message to prevent queue head-of-line blocking.
2. **RabbitMQ Auto-Reconnect**: Both API and Worker feature exponential backoff retry loops to withstand transient network or broker outages.
3. **Graceful Cache Degradation**: If Redis is temporarily unreachable, the rate limiter fails open to prioritize service availability while logging warnings, and the API falls back to direct database reads.
4. **Health Check Orchestration**: Docker Compose uses health checks on PostgreSQL, Redis, and RabbitMQ with `condition: service_healthy` before initializing dependent API and Worker containers.

---

## 📄 License
This project is open source and available under the [MIT License](LICENSE).
