# apps/web

This is the active frontend for new MY_RAG development.

## Development Rules

- New frontend work must target `apps/web`.
- The legacy `frontend/` directory is migration reference only unless a task explicitly says otherwise.
- Backend calls must go through `src/services/`; page components must not hard-code backend URLs or call `fetch` directly.
- Chat streaming uses `src/services/chat.ts` and the backend endpoint `/api/chat/sessions/{session_id}/messages/stream`.
- The visible web-search switch sends `enable_web_search` to the backend. The backend only enters the `web_search` graph node when this value is true.

## Local Run

Start the API first, then run:

```powershell
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.
