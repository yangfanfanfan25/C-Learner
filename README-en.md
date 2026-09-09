# C-Learner

**C-Learner** (internal codename *MY_RAG*) is a local-first, AI-powered learning platform. Upload your own study materials, ask questions in natural language, and get answers grounded in your documents — with quiz generation and a four-layer long-term memory that remembers your learning context.

Everything runs locally: SQLite for structured data, Milvus Lite for vector search, and a local embedding model — no external vector database required. The only external service you need is an LLM API key.

---

## Features

- **RAG Q&A** — Retrieval-augmented chat grounded in your own documents, with source citations and optional web search.
- **Document ingestion** — Upload PDF / Word / PPT files; the pipeline parses them, recovers structure, normalizes to Markdown, chunks, and indexes them for retrieval.
- **Knowledge base** — Organize content into domains and chapters; manage documents and knowledge slices.
- **Quiz generation** — Auto-generate practice papers from your knowledge base and answer them online.
- **Four-layer memory (L0–L3)** — Conversation → atom → scene → persona. Relevant memories are recalled and injected into each chat turn.
- **Local-first** — SQLite + Milvus Lite + local BGE embeddings. No cloud vector DB needed.
- **First-run wizard** — A setup gate guides you through LLM API key configuration on first launch.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, LangGraph / LangChain / DeepAgents, Milvus Lite |
| Embeddings | sentence-transformers (local BGE, default) or any OpenAI-compatible endpoint |
| LLM | DeepSeek (OpenAI-compatible; configurable) |
| Web search | Zhipu (optional) |
| Frontend | React 19, TypeScript, Vite, Ant Design |

## Prerequisites

- **Python 3.10+** (verified on 3.13)
- **Node.js 18+** with npm
- An **LLM API key** (DeepSeek by default)

## Quick Start

### 1. Clone

```bash
git clone https://github.com/yangfanfanfan25/C-Learner.git
cd C-Learner
```

### 2. Start the backend

```bash
cd apps/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On startup the API runs Alembic migrations automatically and initializes the local SQLite / Milvus stores under `data/` at the repository root.

Verify it is up:

```bash
curl http://127.0.0.1:8000/health
```

Interactive API docs: http://localhost:8000/docs

### 3. Start the frontend

Open a second terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000 — the Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

### 4. Configure your LLM

On first launch the web UI shows a setup screen asking for your LLM API key (DeepSeek by default). Fill it in and the connection is verified in place.

Alternatively, create `apps/api/.env` manually:

```dotenv
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL_NAME=deepseek-chat
LLM_API_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_PROVIDER=openai
```

## Usage

1. **Upload documents** — go to *Documents*, upload PDF / Word / PPT files, and wait for processing to finish.
2. **Ask questions** — in *Chat*, ask anything about your uploaded materials. Answers cite the source chunks; enable *Web Search* to supplement with live results.
3. **Practice** — open a generated *Quiz* paper and answer online.

## Configuration

Key environment variables (all optional except `LLM_API_KEY`):

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | — | LLM API key (required for chat) |
| `LLM_API_BASE_URL` | `https://api.deepseek.com/v1` | LLM endpoint |
| `LLM_MODEL_NAME` | `deepseek-chat` | LLM model |
| `LLM_MODEL_PROVIDER` | `openai` | LLM provider protocol |
| `ZHIPU_API_KEY` | — | Zhipu key (optional, enables web search) |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-zh-v1.5` | Embedding model |
| `EMBEDDING_API_KEY` / `EMBEDDING_API_BASE_URL` | — | Optional remote embedding endpoint (defaults to the local model) |
| `RAG_TOP_K` | `5` | Number of chunks retrieved per query |

All local data (SQLite DBs, Milvus, uploaded files, memory) is stored under `data/` at the repository root and is git-ignored.

## Project Structure

```
apps/
├── api/                      # FastAPI backend
│   ├── app/
│   │   ├── api/routes/       # HTTP endpoints (chat, documents, quiz, setup, ...)
│   │   ├── domain/           # business logic + ports (interfaces)
│   │   ├── infrastructure/   # adapters: DB, LLM, Milvus, embeddings, memory
│   │   ├── schemas/          # Pydantic models
│   │   └── main.py           # app entry point
│   ├── alembic/              # database migrations
│   └── requirements.txt
└── web/                      # React frontend
    └── src/
        ├── pages/            # Chat / Documents / Quiz
        ├── components/       # AI chat components
        └── services/         # API client layer
```

## License

Released under the [MIT License](https://opensource.org/licenses/MIT).
