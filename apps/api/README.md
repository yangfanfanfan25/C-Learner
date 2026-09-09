# apps/api

New local FastAPI backend target for the MY_RAG PC knowledge base.

Current scope:

- FastAPI application factory in `app/main.py`
- `/health` endpoint with a Pydantic response schema
- Local-first configuration defaults for SQLite, Milvus Lite, and `data/`
- Document processing pipeline: 解析 → 结构恢复 → LLM 规范化 Markdown → 结构化知识切片 → SQLite 持久化 → Milvus Lite 向量索引
- Chat workflow with RAG semantic search first and optional web search (Zhipu)

## 文档处理

- `POST /api/documents/process`（multipart）执行完整文档处理，成功后写 SQLite 和 Milvus，返回结构化处理结果与持久化统计。
- `GET /api/documents` 分页列出已处理文档。
- `GET /api/documents/{id}` 返回文档及知识切片摘要。
- `DELETE /api/documents/{id}` 同时删除 SQLite 记录和 Milvus 向量。
- 支持格式沿用 MarkItDown 支持范围；当前不处理图片文件。
- 管道错误把文档状态记录为 `failed`，保留具体 stage 与可读错误；API 不返回密钥或内部堆栈。

## Vector Store & Embeddings

- Milvus Lite 本地数据库 URI 模式：`pymilvus.MilvusClient(uri=<local .db>)`，COSINE 相似度。
- Embedding 使用 `langchain_openai.OpenAIEmbeddings`，默认复用 LLM 的 API key/base URL。
- 相关配置见 `docs/constraints/runtime-versions.md`。

## Web Search

The chat workflow supports optional web search via `zhipuai` (Zhipu WebSearch API). Key design:

- **Explicit toggle**: web search is only invoked when `enable_web_search=true` in the chat request.
- **RAG-first**: local knowledge retrieval always runs first; web results supplement, not replace.
- **Graceful degradation**: if the external search fails, the workflow falls back to RAG-only answering.
- **Citations**: web sources include URL for display in the frontend.

Configuration environment variables:

| Variable | Default | Description |
|---|---|---|
| `ZHIPU_API_KEY` | — | Zhipu AI API key |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Max results per search (1-10) |
| `WEB_SEARCH_TIMEOUT_SECONDS` | `15` | Search timeout in seconds (3-60) |
| `DOCUMENT_LLM_MAX_CONCURRENCY` | `5` | Max concurrent chapter-normalization LLM calls per document (1-20) |

Run the health test from the repository root:

```bash
python -m pytest test/unit/test_api_health.py
```
