# Personal Notes 📝

An intermediate-level, production-grade personal notes web application built with **FastAPI**, **PostgreSQL** (with instant SQLite dev fallback), **SQLAlchemy 2.x (asyncio)**, **Alembic**, **Jinja2**, **Bootstrap 5**, and **HTMX**.

---

## ✨ Features

- **⚡ Zero-Reload Dashboard (HTMX)**:
  - **Inline Title Editing**: Click on any note title to edit it inline with real-time save or cancel.
  - **Inline Content Editing**: Edit or replace note content directly from the card.
  - **Quick Append**: Append new notes or thoughts directly to an existing note without opening a full edit page.
  - **Inline Category Assignment**: Change note categories directly from the note card dropdown.
  - **Inline Tag Management**: Add and remove tags with instant badge updates.
  - **Instant Toggles**: Favorite (❤️), Pin to Top (📌), and Archive (📦) toggles with live dashboard updates.
- **🔒 Secure Authentication & Authorization**:
  - User Registration & Login with Argon2id password hashing.
  - Cookie-based session handling via secure HTTP-Only tokens (seamless with HTMX AJAX requests).
  - Profile view with password change.
  - Password Reset workflow with secure cryptographic tokens (SHA-256 storage) and terminal email console logging for local testing.
  - **Strict Row-Level Multi-User Isolation**: All queries strictly scoped by `user_id`. Direct URL/ID tampering yields `404 Not Found`.
- **🗂️ Categories & Tags**:
  - User-scoped categories with customizable color badges and active note counters.
  - Many-to-many tag associations with inline badge removal and quick tagging.
- **🔍 Search, Filters & Sorting**:
  - Live debounced search across note titles and content (`hx-trigger="keyup changed delay:300ms"`).
  - Status filters: Active, Favorites, Pinned, Archived, and Trash.
  - Sorting: Recently Updated, Recently Created, Oldest First, Title A-Z, and Title Z-A.
- **🗑️ Two-Stage Trash (Soft Delete)**:
  - Deleting a note moves it to Trash.
  - Restore notes or permanently delete them with confirmation.
- **🌓 Theme Switcher**:
  - Seamless Light Mode and Dark Mode toggle stored in browser `localStorage`.

---

## 🏗️ Architecture & Project Structure

```text
personal-notes/
├── alembic/                  # Database migration scripts (Alembic Async)
├── app/
│   ├── core/                 # Settings, security (Argon2, JWT), and dependencies
│   ├── db/                   # Async engine, session factory, Base and Mixins
│   ├── models/               # SQLAlchemy 2.0 type-annotated mapped models
│   ├── schemas/              # Pydantic v2 validation and DTO schemas
│   ├── repositories/         # Scoped data access layer (User, Note, Category, Tag)
│   ├── services/             # Business logic orchestration & email service
│   ├── routers/              # FastAPI APIRouters (Auth, Dashboard, Notes, Categories, Tags)
│   ├── static/               # CSS (modern styles & theme variables) and JavaScript
│   └── templates/            # Jinja2 layouts, components, pages, and HTMX partials
├── tests/                    # Automated async pytest test suite
├── .env                      # Active environment settings
├── .env.example              # Configuration template
├── alembic.ini               # Alembic configuration
├── pytest.ini                # Test runner configuration
└── requirements.txt          # Python dependencies
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.14)
- **PostgreSQL 14+** (Or use the built-in SQLite fallback configured in `.env` for instant local testing)

### 2. Environment Setup
Create and activate a virtual environment:
```bash
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate

# On Linux/macOS:
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Database Configuration
By default, `.env` is configured with an async SQLite fallback so you can run and test immediately:
```ini
DATABASE_URL="sqlite+aiosqlite:///./personal_notes.db"
```

To use **PostgreSQL** (local or cloud like Neon/Supabase), update `.env`:
```ini
DATABASE_URL="postgresql+asyncpg://<username>:<password>@localhost:5432/personal_notes"
```

Run database migrations:
```bash
alembic upgrade head
```

### 4. Running the Development Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

---

## 🧪 Running Automated Tests

Run the test suite with `pytest`:
```bash
pytest -v
```

All 4 test suites verify:
1. `test_auth.py`: Registration, duplicate email rejection, login sessions, password reset workflow.
2. `test_notes.py`: Note creation, inline title/content edits, appends, category changes, tag operations, soft delete, restore, and permanent deletion.
3. `test_isolation.py`: Multi-user isolation, row-level authorization, and IDOR prevention.

---

## 🔐 Security Highlights

- **Password Hashing**: Argon2id via `pwdlib[argon2]`.
- **Authentication**: HTTP-Only SameSite cookies preventing JavaScript token theft.
- **IDOR Protection**: Every single query filters strictly by `user_id == current_user.id`.
- **XSS Protection**: Jinja2 auto-escaping on all user inputs and note descriptions.
- **CSRF Defense**: Strict SameSite cookie policy and Origin validation.
