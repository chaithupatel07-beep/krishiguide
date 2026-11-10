# AI Smart Farming Assistant — Backend Architecture & API Documentation

Comprehensive technical documentation for the AI Smart Farming Assistant backend service.

---

## 1. System Architecture

AI Smart Farming Assistant is an AI-powered smart agriculture assistant providing Retrieval-Augmented Generation (RAG) agronomic advisory, farm management tools, expert escalation queues, and administrative operations.

```
                      +-----------------------------+
                      |   React 18 + Vite Frontend  |
                      |   (Port 5173 / Proxy :8000) |
                      +--------------+--------------+
                                     |
                       HTTP / REST API (JWT Bearer)
                                     |
                                     v
                      +-----------------------------+
                      |       FastAPI Gateway       |
                      |   CORS / Auth / Validation  |
                      +-------+--------------+------+
                              |              |
              +---------------+              +---------------+
              |                                              |
              v                                              v
+---------------------------+                  +---------------------------+
|    MySQL 8+ Database      |                  |   Qdrant Vector Database  |
|  (InnoDB, Async SQLAlchemy)|                  | (Port 6333, Cosine, 384d) |
|  - Users & Roles          |                  +-------------+-------------+
|  - Farm Profiles          |                                ^
|  - Documents & Chunks     |                                |
|  - Chats & Citations      |                  Sentence Transformers
|  - Expenses & Tasks       |                  (all-MiniLM-L6-v2)
|  - Expert Cases & Audits  |                                |
+---------------------------+                  +-------------+-------------+
                                               |     Google Gemini API     |
                                               | (gemini-2.5-flash Grounded|
                                               +---------------------------+
```

---

## 2. Technology Stack

- **API Framework:** FastAPI 0.115+ (Python 3.13)
- **Database:** MySQL 8.4 Server (InnoDB)
- **Async Driver:** `asyncmy`
- **ORM:** SQLAlchemy 2.0+ (Declarative Mapped typed models)
- **Database Migrations:** Alembic
- **Vector Database:** Qdrant (Port 6333)
- **Embeddings:** Sentence Transformers `all-MiniLM-L6-v2` (384-dimensional normalized vectors)
- **LLM Grounding:** Google Gemini API (`google-genai` SDK with strict grounding rules)
- **PDF Extraction:** PyMuPDF (`fitz` / `pymupdf`)
- **Authentication:** HS256 JWT, bcrypt (12 rounds)

---

## 3. Database Schema (12 Tables)

1. **`users`**: Platform accounts (`id`, `full_name`, `email`, `phone_number`, `hashed_password`, `role`: `farmer`/`expert`/`admin`, `account_status`: `active`/`suspended`/`inactive`, timestamps).
2. **`farm_profiles`**: Farmer land profile (`id`, `user_id` [FK unique], `farm_location`, `farm_size` [Decimal acres], `soil_type`, `crop_details` [JSON], `irrigation_details` [JSON]).
3. **`documents`**: Agricultural documents repository (`id`, `document_name`, `file_path`, `file_type`, `file_size`, `uploaded_by` [FK], `is_public`, `processing_status`: `pending`/`processing`/`completed`/`failed`, `processing_error`, `meta_info` [JSON]).
4. **`document_chunks`**: Partitioned text chunks (`id`, `document_id` [FK], `chunk_index`, `chunk_text`, `page_number`, `meta_info` [JSON], `vector_reference` [UUID]).
5. **`conversations`**: Chat sessions (`id`, `user_id` [FK], `title`, `language`, timestamps).
6. **`chat_messages`**: Conversational turns (`id`, `conversation_id` [FK], `sender_role`: `user`/`assistant`/`system`, `content`, `language`, `is_reported`, `meta_info` [JSON]).
7. **`message_sources`**: Grounded citations (`id`, `message_id` [FK], `document_id` [FK], `chunk_id` [FK], `document_name`, `page_number`, `similarity_score` [Decimal], `snippet`).
8. **`farm_expenses`**: Expense tracker (`id`, `user_id` [FK], `category`, `amount` [Decimal], `crop_name`, `description`, `expense_date`, `meta_info` [JSON]).
9. **`crop_tasks`**: Agronomic activity scheduler (`id`, `user_id` [FK], `task_title`, `crop_name`, `description`, `scheduled_date`, `is_completed`, `reminder_info` [JSON]).
10. **`expert_cases`**: Escalated cases for specialist review (`id`, `farmer_id` [FK], `expert_id` [FK], `message_id` [FK], `title`, `farmer_question`, `ai_response_snapshot`, `expert_response`, `status`: `pending`/`assigned`/`in_review`/`resolved`/`closed`, `recommendations` [JSON], `resolved_at`).
11. **`feedback`**: Platform & AI feedback (`id`, `user_id` [FK], `message_id` [FK], `feedback_type`, `rating`, `comments`, `is_reviewed`).
12. **`audit_logs`**: System audit trail (`id`, `user_id` [FK], `action`, `resource_type`, `resource_id`, `details` [JSON], `ip_address`, `user_agent`).

---

## 4. Environment Variables Configuration

Copy `.env.example` to `.env` in the `backend/` directory:

```ini
PROJECT_NAME="AI Smart Farming Assistant"
VERSION="1.0.0"
ENVIRONMENT="production"
DEBUG=False

# MySQL 8+ Connection
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=krishiguide_db
DATABASE_URL=mysql+asyncmy://root:your_mysql_password@127.0.0.1:3306/krishiguide_db

# Security & Authentication
JWT_SECRET_KEY=your_secure_random_hs256_jwt_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI / Vector / RAG
GEMINI_API_KEY=your_google_gemini_api_key_here
QDRANT_URL=http://127.0.0.1:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=krishiguide_docs
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# Storage
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=25

# CORS Origins
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000"]
```

---

## 5. Startup & Execution Instructions

### A. Start MySQL 8 Server
```powershell
& "C:\Users\chait\mysql-server\mysql-8.4.13-winx64\bin\mysqld.exe" --console --datadir="C:\Users\chait\mysql-server\data" --port=3306 --bind-address=127.0.0.1
```

### B. Start Qdrant Vector Engine
```powershell
& "C:\Users\chait\qdrant-server\qdrant.exe"
```

### C. Run Database Migrations
```powershell
cd backend
py -3.13 -m alembic upgrade head
```

To rollback migrations:
```powershell
py -3.13 -m alembic downgrade base
```

### D. Start FastAPI Backend Server
```powershell
cd backend
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive Swagger documentation is available at:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON:** `http://127.0.0.1:8000/openapi.json`

---

## 6. Complete API Reference

### Health & Diagnostics
- `GET /api/health` — System health check.
- `GET /api/ready` — Async MySQL database readiness check.

### Authentication (`/api/auth`)
- `POST /api/auth/register` — Farmer registration (`full_name`, `email`, `password`, `phone_number`). Prevents public role escalation.
- `POST /api/auth/login` — Authenticate and receive HS256 JWT access token.
- `GET /api/auth/me` — Retrieve authenticated user profile (requires `Bearer <token>`).

### AI Chat & Conversations (`/api/chat`)
- `POST /api/chat` — Submit query to grounded RAG pipeline. Returns answer, real document citations, and conversation ID.
- `GET /api/chat/history` — Paginated list of farmer conversations with message counts.
- `GET /api/chat/{conversation_id}` — Full conversation message history and cited sources.
- `POST /api/chat/messages/{message_id}/report` — Report inaccurate advice; automatically generates an `ExpertCase` for specialist review.
- `DELETE /api/chat/{conversation_id}` — Cascading delete of conversation thread.
- `POST /api/assistant/query` — **Frontend compatibility endpoint**: accepts `{ question, language }` from React frontend (supports both anonymous and authenticated sessions).

### Agricultural Documents (`/api/documents`)
- `POST /api/documents/upload` — Upload PDF manual/guide (max 25MB, validated MIME, path traversal protected). Ingests asynchronously in background.
- `GET /api/documents` — List accessible public and owned private documents.
- `GET /api/documents/{document_id}` — Retrieve document metadata and processing status.
- `DELETE /api/documents/{document_id}` — Delete document from disk, MySQL, and remove vector points from Qdrant.
- `POST /api/documents/{document_id}/process` — Trigger or retry background ingestion.

### Farmer Tools & Farm Management (`/api/farm`)
- `GET /api/farm/profile` — Get farmer's land profile (soil, crops, irrigation).
- `PUT /api/farm/profile` — Create or update farm profile.
- `POST /api/farm/calculate-cost` — Cultivation cost calculator using exact Decimal arithmetic (computes per-acre costs, category breakdowns, yield projections, gross revenue, net profit, profit margin).
- `GET /api/farm/expenses` — Query farm expenses with category, crop, and date range filters and total expenditure sums.
- `POST /api/farm/expenses` — Record farm expense.
- `DELETE /api/farm/expenses/{expense_id}` — Delete expense entry (ownership protected).
- `GET /api/farm/tasks` — List scheduled agronomic activities and reminders.
- `POST /api/farm/tasks` — Schedule new crop activity (priority, scheduled date, tags).
- `PATCH /api/farm/tasks/{task_id}` — Update task execution date or mark completed.

### Expert Panel (`/api/expert`)
- `GET /api/expert/cases` — View unassigned queue and assigned agronomy consultation cases.
- `POST /api/expert/cases/{case_id}/respond` — Provide verified agronomic recommendations and corrective advice.
- `PATCH /api/expert/cases/{case_id}/status` — Update case status (`pending`, `assigned`, `in_review`, `resolved`, `closed`).

### Administration (`/api/admin`)
- `GET /api/admin/dashboard` — Live database aggregations across users, documents, chats, expert cases, and farm metrics.
- `GET /api/admin/users` — Paginated user directory with search and role/status filtering.
- `PATCH /api/admin/users/{user_id}` — Promote users (farmer -> expert/admin) or activate/deactivate accounts (guards against self-demotion/deactivation).
- `GET /api/admin/feedback` — Review farmer feedback.
- `POST /api/feedback` — Submit feedback on advice accuracy or features.
- `GET /api/admin/audit-logs` — Audit trail for administrative and sensitive data changes.

---

## 7. Running the Automated Test Suite

Run all 55 integration and unit tests:
```powershell
cd backend
py -3.13 -m pytest tests/ -v
```
All 55 tests pass with 0 unresolved errors.

