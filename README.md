# AzDO TestCase Manager — Backend

FastAPI backend for the Azure DevOps Test Case Manager UI.  
Handles AzDO API proxying, config profiles, upload history, and AI test case generation.

---

## Features

| Feature | Endpoint |
|---|---|
| Proxy AzDO API calls (PAT stays server-side) | `/api/upload/stream` |
| Save / load named config profiles | `/api/config/profiles` |
| Validate AzDO connection | `/api/config/validate` |
| Validate test cases JSON | `/api/testcases/validate` |
| Preview test cases | `/api/testcases/preview` |
| Upload with real-time SSE streaming | `/api/upload/stream` |
| Upload (synchronous) | `/api/upload/sync` |
| Upload history | `/api/history/` |
| AI generation from description | `/api/ai/generate` |
| AI generation from screenshot upload | `/api/ai/generate-from-image` |

Interactive API docs: **http://localhost:8000/docs**

---

## Quick Start

### 1. Install dependencies

```bash
cd azdo-backend
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY for AI features
```

### 3. Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Serve the frontend

Copy `index.html` into a `static/` folder inside the project:

```bash
mkdir -p static
cp ../azdo-testcase-manager.html static/index.html
```

The backend will serve it at **http://localhost:8000**

---

## Project Structure

```
azdo-backend/
├── main.py                  # FastAPI app, startup, route registration
├── requirements.txt
├── .env.example
├── models/
│   └── schemas.py           # Pydantic request/response models
├── services/
│   ├── db.py                # SQLite (aiosqlite) — config profiles + history
│   └── azdo.py              # Azure DevOps REST API client
└── routers/
    ├── config.py             # GET/POST/DELETE config profiles, validate connection
    ├── testcases.py          # Validate + preview test cases
    ├── upload.py             # SSE streaming upload + sync upload
    ├── history.py            # Upload history CRUD
    └── ai.py                 # Claude AI test case generation
```

---

## API Examples

### Validate connection
```bash
curl -X POST http://localhost:8000/api/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-profile",
    "config": {
      "org": "ViewpointVSO",
      "project": "Platform Apps",
      "pat": "YOUR_PAT",
      "plan_id": 624343,
      "story_id": 678700
    }
  }'
```

### Generate test cases with AI
```bash
curl -X POST http://localhost:8000/api/ai/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Login screen with email and password fields, forgot password link",
    "count": 5
  }'
```

### Generate from screenshot
```bash
curl -X POST http://localhost:8000/api/ai/generate-from-image \
  -F "image=@screenshot.png" \
  -F "description=Messenger chat screen" \
  -F "count=6"
```

### Upload with streaming (JavaScript)
```javascript
const response = await fetch('http://localhost:8000/api/upload/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ config: { ... }, testcases: [ ... ] })
});

const reader = response.body.getReader();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const lines = new TextDecoder().decode(value).split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      console.log(event); // { type, message, progress }
    }
  }
}
```

---

## PAT Scopes Required

Your Azure DevOps Personal Access Token needs:
- **Test Plans** → Read & Write
- **Work Items** → Read & Write

---

## Notes

- The SQLite database (`azdo_manager.db`) is created automatically on first run
- PATs are stored as-is in the SQLite profiles — use OS-level file permissions to protect the DB, or avoid saving PATs in profiles and enter them per-session in the UI
- For production, replace SQLite with PostgreSQL and add authentication middleware
