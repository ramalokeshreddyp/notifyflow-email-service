# NotifyFlow System Architecture & Design Document

## 1. Executive Summary

**NotifyFlow** is an enterprise-grade, event-driven transactional email notification service designed for high throughput, sub-millisecond API responsiveness, and fault-tolerant message processing. The system completely decouples notification ingestion from the simulated delivery pipeline by leveraging **RabbitMQ** as an AMQP message broker, **Redis** as a distributed caching and rate-limiting tier, and **PostgreSQL** for persistent relational storage.

---

## 2. High-Level System Architecture

```mermaid
flowchart TD
    Client["Client / Upstream Services"] -->|HTTP POST /api/notifications/email| API["FastAPI Producer Service"]
    
    subgraph Storage & Cache
        Redis[("Redis In-Memory Cache\n(Templates, Prefs, Rate Limits)")]
        Postgres[("PostgreSQL Database\n(Persistent Store)")]
    end

    subgraph Message Broker
        Exchange{"RabbitMQ Exchange\n(notifications_exchange)"}
        Queue[("Durable Queue\n(email_notifications)")]
        DLQ[("Dead Letter Queue\n(email_notifications_dlq)")]
    end

    subgraph Asynchronous Worker
        Worker["Worker Consumer Service\n(Jinja2 Templating Engine)"]
        Logs[("Simulated Dispatch Logs / Console")]
    end

    API -->|1. Check Rate Limit| Redis
    API -->|2. Cache Aside Query| Redis
    Redis -.->|Cache Miss| Postgres
    API -->|3. Return 202 Accepted| Client
    API -->|4. Publish Event| Exchange
    Exchange -->|Route| Queue
    Queue -->|Consume Event| Worker
    Worker -->|Fetch Template/Prefs| Redis
    Worker -->|Render & Send| Logs
    Worker -.->|Poison / Failed| DLQ
```

---

## 3. Core Architectural Principles

### 3.1 Asynchronous Non-Blocking Execution
- **Zero Delivery Latency for Clients**: The API service validates payloads and queues the event to RabbitMQ within milliseconds, returning an `HTTP 202 Accepted` response immediately. Upstream clients are never blocked waiting for email rendering or network I/O.

### 3.2 Cache-Aside (Lazy Loading) Strategy
- **Notification Templates**: Cached under `template:<template_id>` with configurable TTL (default 1 hour). Eliminates database reads for high-frequency transactional templates (e.g., order confirmations, password resets).
- **User Preferences**: Cached under `user_prefs:<recipient_email>` with configurable TTL. Prevents repetitive user lookup queries during bursts.
- **Cache Invalidation**: Mutation endpoints (`PUT /api/templates/{id}`, `DELETE /api/templates/{id}`, `PUT /api/preferences/{email}`) automatically update or invalidate Redis keys to ensure consistency.

### 3.3 Sliding Window Rate Limiting
- Enforced per client IP address via Redis atomic operations (`INCR` + `EXPIRE`).
- Emits standard rate limiting headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`).
- Returns `HTTP 429 Too Many Requests` with a `Retry-After` header when thresholds are exceeded.

---

## 4. End-to-End Sequence Diagrams

### 4.1 Transactional Email Ingestion & Processing

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client App
    participant API as API Service
    participant Redis as Redis Cache
    participant DB as PostgreSQL
    participant RMQ as RabbitMQ (Broker)
    participant Worker as Worker Consumer

    Client->>API: POST /api/notifications/email
    API->>Redis: Check Rate Limit (IP)
    alt Rate Limit Exceeded
        API-->>Client: 429 Too Many Requests (Retry-After)
    else Rate Limit OK
        API->>Redis: GET template:{id}
        alt Cache Miss
            API->>DB: SELECT * FROM notification_templates
            API->>Redis: SET template:{id} (TTL=3600s)
        end
        API->>Redis: GET user_prefs:{email}
        alt Cache Miss
            API->>DB: SELECT * FROM user_preferences
            API->>Redis: SET user_prefs:{email} (TTL=3600s)
        end
        API->>RMQ: Publish persistent message (delivery_mode=2)
        API-->>Client: 202 Accepted {notification_id, status: "queued"}
        
        RMQ->>Worker: Deliver message from email_notifications queue
        Worker->>Worker: Check email_opt_out flag
        alt Opted Out
            Worker->>Worker: Log [NOTIFICATION_SKIPPED] & ACK
        else Active User
            Worker->>Worker: Render Jinja2 Subject & Body
            Worker->>Worker: Log [EMAIL_DISPATCHED] (Simulated Delivery)
            Worker->>RMQ: ACK message
        end
    end
```

---

## 5. Message Broker Design & Fault Tolerance

### 5.1 Durability & Persistence
- **Exchanges & Queues**: Declared with `durable=True`, ensuring broker restart survival.
- **Messages**: Published with `DeliveryMode.PERSISTENT` (`delivery_mode=2`) and stored to disk before acknowledgment.
- **Consumer Acknowledgments**: Worker processes messages with explicit manual acknowledgments only after successful processing.

### 5.2 Poison Message Handling & Dead-Letter Routing
- Unhandled or corrupted payloads are caught in protective `try-except` blocks.
- Failed messages are acknowledged and routed to the Dead Letter Exchange (`notifications_dlx`) and Dead Letter Queue (`email_notifications_dlq`) rather than re-queued in an infinite crash loop.

---

## 6. Scalability & Deployment Considerations

1. **Horizontal Scaling of API & Workers**:
   - The API is completely stateless and can scale horizontally behind an NGINX or cloud load balancer.
   - Workers can scale dynamically based on RabbitMQ queue depth metrics (`x-max-priority`, message count).
2. **Redis Cluster / Sentinel Support**:
   - Cache service supports distributed Redis clustering for high-availability setups.
3. **Database Connection Pooling**:
   - Asynchronous SQLAlchemy connection pooling (`asyncpg`) manages connection recycling and prevents connection exhaustion.
