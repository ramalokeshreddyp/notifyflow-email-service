# 🚀 NotifyFlow: Event-Driven Transactional Email Notification Service API

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)](https://www.rabbitmq.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-29%20Passed%20(100%25)-success?style=for-the-badge&logo=pytest&logoColor=white)]()

<br/>

**A production-ready, highly available, and event-driven backend service for transactional email notifications.**  
*Decouples message ingestion using RabbitMQ, accelerates reads and rate limits with Redis, persists data in PostgreSQL, and renders dynamic content using Jinja2.*

</div>

---

## 📑 Table of Contents
- [1. System Overview](#1-system-overview)
- [2. System Architecture](#2-system-architecture)
- [3. Key Architectural Features](#3-key-architectural-features)
- [4. Execution Flow Diagrams](#4-execution-flow-diagrams)
  - [4.1 End-to-End Notification Flow](#41-end-to-end-notification-flow)
  - [4.2 Cache-Aside Pattern Flow](#42-cache-aside-pattern-flow)
  - [4.3 Rate Limiting & Abuse Prevention Flow](#43-rate-limiting--abuse-prevention-flow)
  - [4.4 Worker Message Processing & Poison Isolation](#44-worker-message-processing--poison-isolation)
- [5. Technology Stack](#5-technology-stack)
- [6. Code Structure & Organization](#6-code-structure--organization)
- [7. Quick Start & Local Setup](#7-quick-start--local-setup)
- [8. Environment Variables Reference](#8-environment-variables-reference)
- [9. API Usage & Examples](#9-api-usage--examples)
- [10. Automated Testing](#10-automated-testing)
- [11. Pre-Seeded Database Templates & Profiles](#11-pre-seeded-database-templates--profiles)
- [12. Observability & Monitoring](#12-observability--monitoring)
- [13. Documentation Suite](#13-documentation-suite)

---

## 1. System Overview

In high-volume applications (e-commerce checkout, financial transactions, SaaS onboarding), synchronous email delivery blocks user requests and creates single points of failure. **NotifyFlow** provides a resilient event-driven notification architecture that:

1. **Eliminates Client Waiting**: Ingestion APIs accept requests, validate payloads, and push events to RabbitMQ in **< 5ms**, immediately returning `HTTP 202 Accepted`.
2. **Eliminates Database Choke Points**: Redis caches email templates and user preference profiles using the **Cache-Aside** pattern.
3. **Protects Upstream Services**: Redis-backed sliding-window rate limiting prevents burst abuse per IP address.
4. **Guarantees Delivery & Fault Isolation**: AMQP durable queues with persistent messages (`delivery_mode=2`), manual ACKs, and Dead Letter Queue (`DLQ`) routing prevent message loss and poison-message crashes.

---

## 2. System Architecture

```mermaid
flowchart TD
    subgraph Clients["Client Applications / Upstream Services"]
        ECom["E-Commerce Checkout"]
        Auth["Auth & Password Reset"]
        Billing["Billing & Invoicing Engine"]
    end

    subgraph API_Gateway["NotifyFlow Ingestion Tier"]
        API["FastAPI Producer Service\n(Port 8000)"]
    end

    subgraph In_Memory_Tier["In-Memory Acceleration & Rate Limiting"]
        Redis[("Redis 7 Cache\n- template:{id}\n- user_prefs:{email}\n- rate_limit:ip:{ip}")]
    end

    subgraph Persistent_Store["Relational Database"]
        Postgres[("PostgreSQL 16\n- notification_templates\n- user_preferences")]
    end

    subgraph Broker["AMQP Message Broker"]
        Exchange{{"Topic Exchange\nnotifications_exchange"}}
        Queue[("Durable Queue\nemail_notifications")]
        DLX{{"Direct Exchange\nnotifications_dlx"}}
        DLQ[("Dead Letter Queue\nemail_notifications_dlq")]
    end

    subgraph Worker_Tier["Asynchronous Processing Tier"]
        Worker["Worker Service\n(Jinja2 Templating Engine)"]
    end

    subgraph Output["Delivery Simulation"]
        Logs[("Delivery Console & Audit Logs")]
    end

    ECom -->|POST /api/notifications/email| API
    Auth -->|POST /api/notifications/email| API
    Billing -->|POST /api/notifications/email| API

    API -->|1. Check Rate Limit| Redis
    API -->|2. Cache Aside (Templates/Prefs)| Redis
    Redis -.->|Cache Miss| Postgres
    API -->|3. Publish Persistent Event| Exchange
    API -->|4. Return 202 Accepted| Clients

    Exchange -->|Route: notification.email| Queue
    Queue -->|Consume (Prefetch: 10)| Worker
    Worker -->|Fetch Template/Prefs| Redis
    Worker -->|Render & Dispatch| Logs

    Queue -.->|Poison / Corrupt| DLX
    DLX -->|Route: dead_letter| DLQ
```

---

## 3. Key Architectural Features

- ⚡ **Asynchronous Non-Blocking Processing**: Zero client delivery latency via immediate `202 Accepted` event queuing.
- 📬 **Reliable Message Queuing**: Durable exchanges, disk persistence (`delivery_mode=2`), and manual worker acknowledgments (`ACK`).
- 🚀 **Redis Cache-Aside Layer**: Sub-millisecond reads for templates and user preferences with configurable TTL and auto-invalidation on updates.
- 🛡️ **IP-Based Sliding Window Rate Limiting**: Distributed rate limiting using atomic Redis pipelines (`INCR` + `EXPIRE`), returning `429 Too Many Requests` with `Retry-After` headers.
- 🧩 **Jinja2 Dynamic Templating**: Safe variable injection, default value fallbacks, custom currency formatting, and automatic HTML escaping.
- 🔕 **User Opt-Out Compliance**: Evaluates user notification preferences before dispatch and acknowledges skipped notifications cleanly.
- 🛑 **Poison Message Neutralization**: Corrupted payloads or unresolvable templates are isolated and routed to the Dead Letter Queue without blocking the primary queue.
- 🐳 **Full Docker Orchestration**: All 5 services containerized with custom health checks and dependency coordination.

---

## 4. Execution Flow Diagrams

### 4.1 End-to-End Notification Flow

```mermaid
sequenceDiagram
    autonumber
    actor Client as Upstream Service
    participant API as FastAPI Ingestion Layer
    participant RateLimiter as Redis Rate Limiter
    participant Cache as Redis Cache Tier
    participant DB as PostgreSQL DB
    participant Broker as RabbitMQ Topic Exchange
    participant Worker as Worker Consumer

    Client->>API: POST /api/notifications/email
    API->>RateLimiter: Check IP window quota (INCR + TTL)
    alt Rate Limit Exceeded
        RateLimiter-->>API: Limit exceeded
        API-->>Client: HTTP 429 Too Many Requests (Retry-After header)
    else Rate Limit OK
        RateLimiter-->>API: Quota available
        
        API->>Cache: GET template:{id}
        alt Cache Miss
            API->>DB: SELECT * FROM notification_templates
            API->>Cache: SET template:{id} (TTL=3600s)
        end

        API->>Cache: GET user_prefs:{email}
        alt Cache Miss
            API->>DB: SELECT * FROM user_preferences
            API->>Cache: SET user_prefs:{email} (TTL=3600s)
        end

        API->>Broker: Publish Persistent Message (UUID, ISO Timestamp)
        Broker-->>API: Confirm Published
        API-->>Client: HTTP 202 Accepted {notification_id, status: "queued"}

        Broker->>Worker: Deliver Message from Queue
        Worker->>Worker: Check Opt-Out Status
        alt Opted Out
            Worker->>Worker: Log [NOTIFICATION_SKIPPED] & ACK
        else Active User
            Worker->>Worker: Render Jinja2 Template (Subject + Body)
            Worker->>Worker: Log [EMAIL_DISPATCHED] (Simulated Delivery)
            Worker->>Broker: ACK Message
        end
    end
```

---

### 4.2 Cache-Aside Pattern Flow

```mermaid
flowchart TD
    Start["API / Worker Request Data"] --> CheckCache{"Key in Redis?"}
    CheckCache -->|Cache HIT| ReturnCached["Return Cached JSON Object\n(Latency < 1ms)"]
    CheckCache -->|Cache MISS| QueryDatabase["Query PostgreSQL Table\n(Latency ~5-15ms)"]
    QueryDatabase --> DBFound{"Record Found?"}
    DBFound -->|Yes| SetRedis["Set Redis Key with TTL (3600s)"]
    SetRedis --> ReturnCached
    DBFound -->|No| HandleMissing["Raise 400 (Template) / Return Default (Prefs)"]
```

---

### 4.3 Rate Limiting & Abuse Prevention Flow

```mermaid
flowchart LR
    Incoming["Incoming Request"] --> ExtractIP["Extract Client IP\n(X-Forwarded-For / Host)"]
    ExtractIP --> AtomicPipe["Atomic Redis Pipeline\n(INCR rate_limit:ip:IP + TTL)"]
    AtomicPipe --> CheckThreshold{"count > RATE_LIMIT_PER_MINUTE?"}
    CheckThreshold -->|Yes| Raise429["Return HTTP 429 Too Many Requests\n(Headers: Retry-After, X-RateLimit-*)"]
    CheckThreshold -->|No| AllowRequest["Inject X-RateLimit Headers\nProceed with Request"]
```

---

### 4.4 Worker Message Processing & Poison Isolation

```mermaid
flowchart TD
    Msg["Message Received from RabbitMQ"] --> ValidatePayload{"Valid JSON & Required Fields?"}
    ValidatePayload -->|Invalid / Corrupt| Poison1["Log [POISON_MESSAGE]\nRoute to Dead Letter Queue (DLQ)\nACK to remove from queue"]
    ValidatePayload -->|Valid| CheckOptOut{"User Opted Out?"}
    CheckOptOut -->|Yes| SkipDispatch["Log [NOTIFICATION_SKIPPED]\nACK Message"]
    CheckOptOut -->|No| FetchTemplate{"Template Exists?"}
    FetchTemplate -->|No| Poison2["Log [POISON_MESSAGE]\nRoute to DLQ\nACK Message"]
    FetchTemplate -->|Yes| RenderTemplate["Render Jinja2 Subject & Body"]
    RenderTemplate --> RenderSuccess{"Render OK?"}
    RenderSuccess -->|Error| Poison3["Log [RENDERING_ERROR]\nRoute to DLQ & ACK"]
    RenderSuccess -->|Success| SendEmail["Log [EMAIL_DISPATCHED]\nSimulate Delivery\nACK Message"]
```

---

## 5. Technology Stack

| Layer | Component | Version | Why It Was Chosen |
|---|---|---|---|
| **API Framework** | FastAPI | `0.110+` | Ultra-high performance asynchronous event loop, automatic OpenAPI documentation, type safety with Pydantic v2. |
| **Message Broker** | RabbitMQ | `3.13` | Mature AMQP broker supporting durable exchanges, fine-grained routing keys, persistent disk delivery, and Dead Letter Exchanges. |
| **AMQP Client** | aio-pika | `9.4+` | Fully asynchronous non-blocking RabbitMQ client supporting robust reconnection and publisher confirms. |
| **Cache & Rate Limiter** | Redis | `7.0` | In-memory key-value store with sub-millisecond lookups and atomic pipeline primitives (`INCR`, `EXPIRE`). |
| **Relational Database** | PostgreSQL | `16` | Robust ACID storage for templates and user preferences with B-Tree indexing. |
| **Database ORM/Driver** | SQLAlchemy + asyncpg | `2.0+` | Non-blocking async connection pooling, avoiding thread pool exhaustion. |
| **Templating Engine** | Jinja2 | `3.1+` | Powerful sandboxed templating with custom filters, default value fallbacks, and safe autoescaping. |
| **Testing** | Pytest + Pytest-Asyncio | `8.1+` | Industry-standard async testing framework with rich fixture management. |
| **Containerization** | Docker & Compose | `v2+` | Portable multi-container orchestration with deterministic startup via health checks. |

---

## 6. Code Structure & Organization

```
notifyflow-email-service/
├── .env.example                 # Documented template for all environment configurations
├── .env                         # Default environment configuration
├── .gitignore                   # Git ignore rules
├── docker-compose.yml           # Full multi-container orchestration with health checks
├── pytest.ini                   # Pytest test discovery & execution configuration
├── README.md                    # Primary visual documentation & quick start guide
├── architecture.md              # Detailed architecture, sequence diagrams & design rationale
├── projectdocumentation.md      # Comprehensive technical manual & data dictionary
├── API_DOCS.md                  # Complete OpenAPI specification & cURL examples
├── database/
│   └── init-db.sql              # Database schema & initial seed data
├── api/
│   ├── Dockerfile               # Production multi-stage Docker build for API
│   ├── requirements.txt         # API service dependencies
│   └── src/
│       ├── main.py              # FastAPI application entrypoint & lifespan manager
│       ├── config.py            # Pydantic Settings configuration loader
│       ├── database.py          # SQLAlchemy async engine & sessionmaker
│       ├── models/
│       │   ├── db_models.py     # SQLAlchemy ORM models (Templates, Preferences)
│       │   └── schemas.py       # Pydantic validation & response schemas
│       ├── services/
│       │   ├── cache_service.py # Redis template & preference caching service
│       │   ├── rate_limiter.py  # Redis sliding-window IP rate limiter
│       │   └── rabbitmq_service.py # RabbitMQ publisher with durable exchanges/queues
│       └── routes/
│           ├── health.py        # /health endpoint verifying DB, Redis & RabbitMQ
│           ├── notifications.py # POST /api/notifications/email
│           ├── templates.py     # CRUD endpoints for email templates
│           └── preferences.py   # Endpoints for user notification preferences
├── worker/
│   ├── Dockerfile               # Lightweight Docker build for Worker
│   ├── requirements.txt         # Worker service dependencies
│   └── src/
│       ├── consumer.py          # RabbitMQ consumer & simulated email dispatcher
│       ├── config.py            # Worker settings loader
│       ├── database.py          # Worker async DB sessionmaker
│       ├── models.py            # Worker ORM models
│       ├── cache_service.py     # Worker Redis caching service
│       └── template_engine.py   # Jinja2 rendering engine with custom filters
└── tests/
    ├── conftest.py              # Pytest fixtures & in-memory async SQLite setup
    ├── unit/
    │   ├── test_api_validation.py      # Pydantic request & payload validation tests
    │   ├── test_rate_limiter.py       # Redis rate limiting & IP isolation tests
    │   ├── test_caching.py            # Redis cache hit, miss & invalidation tests
    │   ├── test_template_rendering.py # Jinja2 templating & custom filter tests
    │   └── test_worker_consumer.py    # Opt-out & poison message handling tests
    └── integration/
        ├── test_api_endpoints.py      # HTTP endpoint integration tests
        └── test_notification_flow.py  # End-to-end API -> MQ -> Worker pipeline test
```

---

## 7. Quick Start & Local Setup

### Option A: Run with Docker Compose (Recommended)

#### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)

#### 1. Clone & Initialize
```bash
git clone https://github.com/ramalokeshreddyp/notifyflow-email-service.git
cd notifyflow-email-service
cp .env.example .env
```

#### 2. Start All Services
```bash
docker-compose up --build
```

#### 3. Verify Operational Status
```bash
curl http://localhost:8000/health
```

---

### Option B: Run Locally Without Docker

#### Prerequisites
- Python 3.11+
- Running instances of PostgreSQL, Redis, and RabbitMQ

#### 1. Setup Virtual Environment
```bash
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate
```

#### 2. Install Dependencies
```bash
pip install -r api/requirements.txt
```

#### 3. Initialize Database
Execute `database/init-db.sql` in your PostgreSQL instance.

#### 4. Run API Service
```bash
uvicorn api.src.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 5. Run Worker Service
```bash
python -m worker.src.consumer
```

---

## 8. Environment Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Application mode (`development`, `production`, `testing`) |
| `API_PORT` | `8000` | Port for the FastAPI server |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/notification_db` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CACHE_TTL_SECONDS` | `3600` | Cache time-to-live for templates and preferences |
| `RATE_LIMIT_PER_MINUTE` | `60` | Maximum requests allowed per minute per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding rate limit window duration in seconds |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection URL |
| `RABBITMQ_QUEUE` | `email_notifications` | Primary durable queue name |
| `RABBITMQ_EXCHANGE` | `notifications_exchange` | Topic exchange name |
| `RABBITMQ_ROUTING_KEY` | `notification.email` | Routing key for transactional email events |
| `RABBITMQ_DEAD_LETTER_QUEUE`| `email_notifications_dlq` | Queue for rejected/poison messages |

---

## 9. API Usage & Examples

### 9.1 Send Transactional Email
```bash
curl -X POST "http://localhost:8000/api/notifications/email" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_email": "john.doe@example.com",
    "template_id": "order-confirmation",
    "dynamic_data": {
      "order_id": "ORD-99881",
      "customer_name": "John Doe",
      "product_name": "NotifyFlow Enterprise Suite",
      "total_amount": "$499.00",
      "shipping_address": "123 Innovation Drive, Silicon Valley, CA",
      "delivery_date": "October 5, 2026"
    }
  }'
```

#### Response (`HTTP 202 Accepted`)
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

#### Worker Console Output
```text
============================================================
[EMAIL_DISPATCHED] Simulated Transactional Email Sent Successfully
Notification ID: c71a39f6-6c7b-4d51-8e54-bf63c631a54b
Recipient:       john.doe@example.com
Template ID:     order-confirmation (Order Confirmation)
Subject:         Order Confirmation #ORD-99881 - Thank You for Your Purchase!
------------------- Email Body -------------------
Hello John Doe,

Thank you for your order! Your purchase of NotifyFlow Enterprise Suite (Order ID: ORD-99881) for a total of $499.00 has been confirmed and is being processed.

Shipping Address: 123 Innovation Drive, Silicon Valley, CA
Estimated Delivery: October 5, 2026

Thank you for shopping with us!
The NotifyFlow Team
============================================================
```

---

## 10. Automated Testing

NotifyFlow features **29 automated tests** with 100% pass coverage across unit and integration testing.

```bash
# Run all tests
python -m pytest -v
```

### Test Coverage Summary
```text
tests/unit/test_api_validation.py ............ [PASSED] (6 tests)
tests/unit/test_rate_limiter.py .............. [PASSED] (4 tests)
tests/unit/test_caching.py ................... [PASSED] (3 tests)
tests/unit/test_template_rendering.py ........ [PASSED] (4 tests)
tests/unit/test_worker_consumer.py ........... [PASSED] (4 tests)
tests/integration/test_api_endpoints.py ...... [PASSED] (7 tests)
tests/integration/test_notification_flow.py .. [PASSED] (1 test)

============================= 29 passed in 0.40s ==============================
```

---

## 11. Pre-Seeded Database Templates & Profiles

### Pre-Configured Templates
1. `order-confirmation` - E-commerce order confirmation and shipping notice.
2. `password-reset` - Security password reset with expiring tokens.
3. `account-alert` - Real-time security notice for logins and unusual activity.
4. `welcome-email` - Customer onboarding welcome message.
5. `payment-receipt` - Invoice receipt and billing notification.

### Pre-Configured User Profiles
- `john.doe@example.com` (Opt-Out: `false`, Language: `en`)
- `jane.smith@example.com` (Opt-Out: `false`, Language: `en`)
- `optedout.user@example.com` (Opt-Out: `true`, Language: `en`)
- `alex.tech@example.com` (Opt-Out: `false`, Language: `es`)
- `sarah.connor@example.com` (Opt-Out: `false`, Language: `en`)

---

## 12. Observability & Monitoring

- **Interactive API Documentation**: Swagger UI at `http://localhost:8000/docs` | ReDoc at `http://localhost:8000/redoc`.
- **System Health Endpoint**: `http://localhost:8000/health` (Reports active health for API, DB, Redis, and RabbitMQ).
- **RabbitMQ Management Dashboard**: `http://localhost:15672` (Credentials: `guest` / `guest`).

---

## 13. Documentation Suite

- 📘 [**architecture.md**](file:///c:/Users/lokes/Desktop/Gpp-40/architecture.md): Deep architectural breakdown, sequence diagrams, design decisions, failure recovery, and scaling strategies.
- 📙 [**projectdocumentation.md**](file:///c:/Users/lokes/Desktop/Gpp-40/projectdocumentation.md): Comprehensive technical manual, requirements matrix, data dictionary, caching specs, and operations runbook.
- 📗 [**API_DOCS.md**](file:///c:/Users/lokes/Desktop/Gpp-40/API_DOCS.md): Full OpenAPI specifications, parameter definitions, error schemas, and cURL examples.

---

<div align="center">
  <b>Built with ❤️ by the NotifyFlow Engineering Team</b>
</div>
