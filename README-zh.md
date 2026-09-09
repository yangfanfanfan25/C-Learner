# C-Learner

**C-Learner**（内部代号 *MY_RAG*）是一款本地优先的 AI 学习平台。上传你自己的学习资料，用自然语言提问，答案基于你的文档给出——并支持智能出题，以及一套四层长期记忆系统，记住你的学习上下文。

全部本地运行：SQLite 存储结构化数据、Milvus Lite 做向量检索、本地 Embedding 模型——不需要任何云端向量数据库。唯一需要的外部服务是 LLM API Key。

---

## 核心功能

- **RAG 智能问答** — 基于你自己的文档做检索增强问答，带来源引用，可选联网搜索。
- **文档解析入库** — 上传 PDF / Word / PPT，管道自动完成「解析 → 结构恢复 → LLM 规范化 Markdown → 切片 → 向量索引」。
- **知识库管理** — 按域（domain）与章节（chapter）组织内容，管理文档与知识切片。
- **智能出题练习** — 从知识库自动生成模拟试卷，支持在线答题。
- **四层长期记忆（L0–L3）** — 会话 → 原子记忆 → 场景 → 画像，每次对话召回相关记忆并注入上下文。
- **本地优先** — SQLite + Milvus Lite + 本地 BGE Embedding，无需云端向量库。
- **首次运行引导** — 首次启动由引导页带你完成 LLM API Key 配置。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI、SQLAlchemy 2.x、LangGraph / LangChain / DeepAgents、Milvus Lite |
| Embedding | sentence-transformers（默认本地 BGE，可换任意 OpenAI 兼容接口） |
| LLM | DeepSeek（OpenAI 兼容，可配置） |
| 联网搜索 | 智谱 Zhipu（可选） |
| 前端 | React 19、TypeScript、Vite、Ant Design |

## 环境要求

- **Python 3.10+**（已在 3.13 验证）
- **Node.js 18+** 与 npm
- 一个 **LLM API Key**（默认 DeepSeek）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yangfanfanfan25/C-Learner.git
cd C-Learner
```

### 2. 启动后端

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

启动时 API 会自动执行 Alembic 迁移，并在仓库根目录 `data/` 下初始化本地 SQLite / Milvus。

验证是否就绪：

```bash
curl http://127.0.0.1:8000/health
```

交互式 API 文档：http://localhost:8000/docs

### 3. 启动前端

另开一个终端：

```bash
cd apps/web
npm install
npm run dev
```

浏览器打开 http://localhost:3000 —— Vite dev server 会把 `/api` 代理到 `http://127.0.0.1:8000`。

### 4. 配置 LLM

首次启动时，网页会显示配置引导页，让你填入 LLM API Key（默认 DeepSeek），填写后当场校验连通性。

也可以手动创建 `apps/api/.env`：

```dotenv
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_MODEL_NAME=deepseek-chat
LLM_API_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_PROVIDER=openai
```

## 使用方式

1. **上传文档** — 进入「文档」页，上传 PDF / Word / PPT，等待处理完成。
2. **提问** — 在「对话」页针对已上传资料提问，回答会引用来源片段；打开「联网搜索」可补充实时结果。
3. **练习** — 打开生成的「模拟练习」试卷在线作答。

## 配置项

关键环境变量（除 `LLM_API_KEY` 外均可选）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | — | LLM API Key（对话必需） |
| `LLM_API_BASE_URL` | `https://api.deepseek.com/v1` | LLM 接口地址 |
| `LLM_MODEL_NAME` | `deepseek-chat` | LLM 模型名 |
| `LLM_MODEL_PROVIDER` | `openai` | LLM 协议类型 |
| `ZHIPU_API_KEY` | — | 智谱 Key（可选，启用联网搜索） |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-zh-v1.5` | Embedding 模型 |
| `EMBEDDING_API_KEY` / `EMBEDDING_API_BASE_URL` | — | 可选远程 Embedding 接口（默认用本地模型） |
| `RAG_TOP_K` | `5` | 每次检索返回的切片数 |

所有本地数据（SQLite、Milvus、上传文件、记忆）都存放在仓库根目录 `data/` 下，已加入 git 忽略。

## 项目结构

```
apps/
├── api/                      # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/       # HTTP 接口（chat / documents / quiz / setup …）
│   │   ├── domain/           # 业务逻辑 + 端口（接口定义）
│   │   ├── infrastructure/   # 适配器：DB、LLM、Milvus、Embedding、记忆
│   │   ├── schemas/          # Pydantic 模型
│   │   └── main.py           # 应用入口
│   ├── alembic/              # 数据库迁移
│   └── requirements.txt
└── web/                      # React 前端
    └── src/
        ├── pages/            # 对话 / 文档 / 练习
        ├── components/       # AI 对话组件
        └── services/         # API 请求层
```

## License

基于 [MIT License](https://opensource.org/licenses/MIT) 开源。
