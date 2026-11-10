# AI Smart Farming Assistant — Project Inspection Report & Migration Plan (Phase 0)

## 1. Executive Summary & Repository Inspection

- **Repository**: `https://github.com/chaithupatel07-beep/krishiguide.git`
- **Location**: `C:\Users\chait\.antigravity-ide\krishiguide`
- **Git Branch**: `main`
- **Current Commit**: `095ea75` ("fix(vercel): make deployment universal for both root and frontend root directory settings")

### Directory Structure
```
krishiguide/
├── frontend/                     # Nested duplicate of client for multi-platform deployment
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── src/                          # Root client code
│   ├── App.jsx                   # Main frontend component
│   ├── index.css                 # Styling system
│   └── main.jsx                  # React bootstrap
├── .env.example                  # VITE_API_URL=/api
├── .gitignore
├── index.html
├── netlify.toml
├── package.json                  # Root React & Vite dependencies
├── package-lock.json
├── README.md
├── vercel.json
└── vite.config.js                # Vite proxy configured: /api -> http://127.0.0.1:8000
```

---

## 2. Frontend & Backend Identification

- **Frontend**:
  - React 18.3.1 + Vite 6.1.0 + Lucide React 0.475.0 + Axios 1.7.9.
  - Fully functioning single-page application with tabs: Dashboard, AI Assistant, Crop Advisor, Weather & Irrigation, Soil & Fertilizer, Knowledge Library.
  - Development proxy in `vite.config.js` directs `/api/*` to `http://127.0.0.1:8000`.
- **Existing Backend in Repository**:
  - **None**. There was no Python or FastAPI backend code in the repository.
- **Other Local Workspaces**:
  - `agrisynapse` exists on the machine as a separate Node.js/Express mock engine; it is not part of KrishiGuide.

---

## 3. Installed Dependencies

- **Node.js Environment**:
  - `react`: ^18.3.1
  - `react-dom`: ^18.3.1
  - `axios`: ^1.7.9
  - `lucide-react`: ^0.475.0
  - `vite`: ^6.1.0
- **Python Environment (Python 3.13)**:
  - `fastapi`: 0.148.0
  - `uvicorn`: 0.54.0
  - `pydantic`: 2.14.1
  - Packages to install for Phase 1+: `sqlalchemy>=2.0`, `asyncmy`, `alembic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt`, `pymupdf`, `sentence-transformers`, `qdrant-client`, `google-genai`, `httpx`, `pytest`, `pytest-asyncio`.

---

## 4. Existing Database Configuration & Inspection

- **PostgreSQL / SQLite Status**:
  - The local Windows host has a background service `postgresql-x64-18` on port 5432, but it has no database models or migrations connected to `krishiguide`.
  - SQLite is not configured in `krishiguide`.
- **MySQL Migration Plan**:
  - In accordance with Mandatory Rule 11 ("Do not use PostgreSQL, pgvector, or PostgreSQL-specific libraries or SQL") and Rule 12 ("Use MySQL 8+, FastAPI, SQLAlchemy 2.x asynchronous sessions, Alembic, and Pydantic"):
  - Database name: `krishiguide_db`.
  - Driver: Asynchronous MySQL driver `asyncmy`.
  - Dialect: `mysql+asyncmy://<user>:<password>@<host>:3306/krishiguide_db`.
  - No legacy KrishiGuide database records exist in PostgreSQL to transfer; a clean schema will be initialized via Alembic on MySQL 8+.

---

## 5. Existing API Endpoints & Frontend Expectations

- In `src/App.jsx` (and `frontend/src/App.jsx`), the frontend currently triggers:
  - `POST /api/assistant/query` with payload:
    ```json
    {
      "question": "string",
      "language": "English | Hindi | Telugu"
    }
    ```
  - Expects response:
    ```json
    {
      "answer": "string",
      "sources": ["source 1", "source 2"]
    }
    ```
- **Compatibility Strategy**:
  - Implement `/api/assistant/query` as an alias to the RAG AI pipeline so the existing frontend chat continues working seamlessly without breaking changes.
  - Implement `/api/chat`, `/api/chat/history`, `/api/chat/{conversation_id}` as specified in Phase 7.
  - Implement the full suite of required endpoints across Auth, Documents, Farm Profile, Expert, and Admin.

---

## 6. Authentication, Roles & AI Integrations

- **Authentication & Roles**:
  - Currently no authentication UI or backend exists.
  - Required roles: `admin`, `farmer`, `expert`.
  - Default public registration: `farmer`.
- **AI Integrations**:
  - Embeddings: `sentence-transformers` (`all-MiniLM-L6-v2`).
  - Vector DB: `Qdrant` (collection: `krishiguide_docs`).
  - LLM: Google Gemini API (`google-genai` SDK / modern REST).
  - Document parser: `PyMuPDF` (`fitz`).

---

## 7. Phase-by-Phase Implementation Plan

1. **Phase 1**: FastAPI application scaffolding, MySQL 8+ async connection (`asyncmy`), health/ready endpoints, CORS, Pydantic settings.
2. **Phase 2**: SQLAlchemy 2.x models for all 12 tables, Alembic migrations, database indexes & constraints.
3. **Phase 3**: JWT authentication (`/api/auth/register`, `/login`, `/me`), bcrypt/argon2 hashing, OAuth2 password bearer.
4. **Phase 4**: Role-Based Access Control (RBAC) dependencies and ownership checks (`admin`, `farmer`, `expert`).
5. **Phase 5**: PDF ingestion pipeline (`PyMuPDF`), text chunking, `all-MiniLM-L6-v2` embeddings, Qdrant vector storage, background workers.
6. **Phase 6**: RAG pipeline & Gemini API integration with citation grounding and fallback handling.
7. **Phase 7**: AI Chat (`/api/chat`, `/api/chat/history`, `/api/assistant/query`), language preference, conversation history.
8. **Phase 8**: Farmer tools (Farm Profile, Cultivation Cost Calculator, Expenses, Crop Tasks).
9. **Phase 9**: Expert APIs (Cases, Responses, Status) and Admin APIs (Dashboard, Users, Feedback, Audit Logs).
10. **Phase 10**: End-to-end security audit, automated pytest suite, performance tuning, and documentation.

