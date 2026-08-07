# Interactive Course Syllabus

A web app that turns a static syllabus into a living one. The instructor enters a
schedule once, then edits it in plain English ("delay all topics by a week", "move
Assignment 2 to next Friday", "add a quiz after the recursion lecture", "cancel the
class on March 10 and adjust"). Students view a clean, read-only schedule via a shared
link with upcoming deadlines highlighted.

The core idea: natural-language edits never touch the database directly. The LLM
**proposes** a typed set of operations → the backend computes a **preview diff** → the
instructor **confirms** → it commits in one transaction with a snapshot for **undo**.

## Stack

- **Backend:** FastAPI + SQLModel (SQLite), Python 3.12, managed with `uv`.
- **Frontend:** React + Vite + TypeScript + Tailwind CSS v4.
- **LLM:** OpenAI by default via the `openai` SDK, behind a swappable provider
  interface (`app/llm/`). Runs without a key using a stub (manual editing still works).

## Project layout

```
backend/
  app/
    models.py          SQLModel tables (Course, ClassMeeting, Reading, Assessment, ChangeLog)
    scheduling.py      rrule meeting-date generation
    operations.py      typed operation union + pure apply() + diff   ← the safe-edit core
    persistence.py     reconcile DB to a target state (apply & undo)
    serialization.py   ORM <-> JSON state dict
    llm/               provider registry (OpenAI, OpenAI-compatible, stub)
    routers/           courses (CRUD), chat (propose/apply/undo), public (student view)
  tests/               20 tests (scheduling, the 4 example edits, full API flow)
frontend/
  src/
    pages/Instructor.tsx   login + course list + editor/chat layout
    pages/Student.tsx      public read-only syllabus
    components/            Login, CourseSetup, SyllabusEditor, ChatPanel
```

## Running it

**1. Backend** (port 8010):

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8010
```

API docs at http://localhost:8010/docs. The app boots without an API key (AI editing
shows a "configure the key" message; everything else works).

**2. Frontend** (port 5173, proxies `/api` to the backend):

```bash
cd frontend
npm install        # first time only
npm run dev
```

Open http://localhost:5173, sign in with `ADMIN_PASSWORD`, create a course, and use the
Assistant panel. Student links use the normalized course title and term, such as
`http://localhost:5173/cs1428fall2026` (Copy student link button).

### One-command Windows hosting

After installing `uv` and Node/npm, the Windows supervisor starts the backend and
frontend and automatically restarts either process if it exits. The named Cloudflare
Tunnel runs independently as the Windows `cloudflared` service:

```powershell
.\scripts\manage.ps1 start
.\scripts\manage.ps1 status
.\scripts\manage.ps1 restart
.\scripts\manage.ps1 stop
```

You can also double-click `start-all.cmd`, `restart-all.cmd`, or `stop-all.cmd` in
File Explorer. Runtime state and logs are written to `.runtime/`. The launcher allows
`syllabus.xiaominapps.com` in Vite and reports the state of the independently managed
Cloudflare service. The permanent address is saved in `PUBLIC-URL.txt`.

## Tests

```bash
cd backend && uv run pytest        # 20 tests
cd frontend && npm run build       # type-check + production build
```

## How natural-language editing stays safe

1. `POST /api/courses/{id}/chat` — the provider returns an `OperationSet` (typed,
   Pydantic-validated). The server applies it to a *copy* of the state and returns a
   preview diff. Nothing is committed. Ambiguous requests come back as a clarifying
   question instead of a guess.
2. `POST /api/courses/{id}/apply` — re-validates the operations, applies, reconciles the
   DB, and writes a `ChangeLog` with a full pre-change snapshot.
3. `POST /api/courses/{id}/undo` — restores the most recent snapshot.

Operations are limited to a known set (`shift_dates`, `shift_topics`,
`move_assessment_due`, `add_assessment`, `cancel_meeting`, `update_meeting`); anything
referencing an unknown id is rejected, never applied.

## Swapping the LLM provider

Most switching is now environment-only:

```bash
# Official OpenAI Responses API
LLM_PROVIDER=openai
LLM_ENDPOINT=responses
LLM_MODEL=gpt-5.5
OPENAI_API_KEY=sk-...

# OpenAI-compatible providers such as OpenRouter, LM Studio, vLLM, etc.
LLM_PROVIDER=openai_compatible
LLM_ENDPOINT=chat
LLM_MODEL=provider/model-name
OPENAI_BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=...
```

To add a truly different provider, implement the `LLMProvider` protocol in
`app/llm/base.py` and register it in `app/llm/__init__.py`. It only needs to return
an `OperationSet`; preview, validation, apply, and undo stay unchanged.
