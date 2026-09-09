# 数据库 Schema 文档

> 生成日期：2026-07-18
> 数据库类型：SQLite
> 模型定义位置：`apps/api/app/domain/`

---

## 目录

1. [wiki_sources — 原始文档表](#1-wiki_sources--原始文档表)
2. [wiki_pages — Wiki 页面表](#2-wiki_pages--wiki-页面表)
3. [wiki_links — 双向链接表](#3-wiki_links--双向链接表)
4. [wiki_versions — 版本历史表](#4-wiki_versions--版本历史表)
5. [wiki_logs — 操作日志表](#5-wiki_logs--操作日志表)
6. [chat_sessions — 对话会话表](#6-chat_sessions--对话会话表)
7. [chat_messages — 对话消息表](#7-chat_messages--对话消息表)
8. [exam_tasks — 练习任务表](#8-exam_tasks--练习任务表)
9. [exam_records — 答题记录表](#9-exam_records--答题记录表)
10. [exam_answers — 每题作答表](#10-exam_answers--每题作答表)
11. [subjects — 学科表](#11-subjects--学科表)
12. [subject_sources — 学科文档关联表](#12-subject_sources--学科文档关联表)
13. [knowledge_points — 知识点表](#13-knowledge_points--知识点表)
14. [表关系总览](#14-表关系总览)

---

## 1. wiki_sources — 原始文档表

**职责：** 存储用户上传的原始文档信息，记录文档处理状态。

**状态流转：** `pending → processing → completed` 或 `pending → processing → failed`

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| filename | VARCHAR(255) | ✅ | - | 原始文件名 |
| file_path | TEXT | ❌ | NULL | 文件存储路径（旧记录保留，新记录为空） |
| file_data | BLOB | ❌ | NULL | 文件二进制内容 |
| file_type | VARCHAR(20) | ✅ | - | 文件类型：pdf/word/ppt/image |
| file_size | BIGINT | ✅ | - | 文件大小（字节） |
| status | VARCHAR(20) | ✅ | pending | 处理状态：pending/processing/completed/failed |
| error_message | TEXT | ❌ | NULL | 错误信息（status=failed 时记录） |
| task_id | VARCHAR(255) | ❌ | NULL | 任务 ID（用于任务取消） |
| processing_stage | VARCHAR(50) | ❌ | NULL | 处理阶段：parsing/extracting/llm_generating/saving |
| ocr_markdown | TEXT | ❌ | NULL | OCR 解析后的完整 Markdown 内容 |
| uploaded_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 上传时间 |
| processed_at | DATETIME | ❌ | NULL | 处理完成时间 |

---

## 2. wiki_pages — Wiki 页面表

**职责：** 存储 LLM 生成的 Wiki 页面，维护页面版本号，统计链接数量。

**页面类型：**
- `summary`：概述页面
- `chapter`：章节摘要
- `entity`：实体页面（人物、组织、工具）
- `concept`：概念页面（理论、算法、方法）

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| source_id | VARCHAR(36) | ✅ | - | 外键 → wiki_sources.id（CASCADE） |
| title | VARCHAR(255) | ✅ | - | 页面标题（唯一标识） |
| content | TEXT | ✅ | - | Markdown 内容 |
| page_type | VARCHAR(50) | ✅ | - | 页面类型：summary/chapter/entity/concept |
| category | VARCHAR(100) | ❌ | NULL | 分类（如科目、主题） |
| version | INTEGER | ✅ | 1 | 版本号 |
| out_links_count | INTEGER | ✅ | 0 | 出链数量 |
| in_links_count | INTEGER | ✅ | 0 | 入链数量 |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | ❌ | NULL | 更新时间 |
| source_documents | JSON | ❌ | [] | 关联的源文档列表（跨文档合并时记录来源） |

---

## 3. wiki_links — 双向链接表

**职责：** 记录页面之间的链接关系，支持双向链接查询。

**链接规则：**
- `source_page_id`：包含链接的页面
- `target_page_id`：链接指向的页面（可为空，表示页面未创建）
- `target_title`：链接目标标题（用于占位）

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| source_page_id | VARCHAR(36) | ✅ | - | 外键 → wiki_pages.id（CASCADE） |
| target_page_id | VARCHAR(36) | ❌ | NULL | 外键 → wiki_pages.id（SET NULL） |
| target_title | VARCHAR(255) | ✅ | - | 目标页面标题 |
| position | INTEGER | ❌ | NULL | 链接在源页面中的位置 |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 创建时间 |

---

## 4. wiki_versions — 版本历史表

**职责：** 记录页面的历史版本，支持版本回溯。

**版本管理规则：**
- 文档更新时，旧版本内容复制到此表
- `wiki_pages.version` 递增
- 保留所有历史版本

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| page_id | VARCHAR(36) | ❌ | NULL | 外键 → wiki_pages.id（SET NULL） |
| version | INTEGER | ✅ | - | 版本号 |
| content | TEXT | ✅ | - | 历史版本内容 |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 创建时间 |

---

## 5. wiki_logs — 操作日志表

**职责：** 记录所有操作日志，支持知识演进追溯。

**操作类型：**
- `upload`：文档上传
- `generate`：Wiki 生成
- `update`：文档更新
- `delete`：文档删除

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| source_id | VARCHAR(36) | ❌ | NULL | 外键 → wiki_sources.id（SET NULL） |
| action | VARCHAR(50) | ✅ | - | 操作类型：upload/generate/update/delete |
| details | JSON | ❌ | NULL | 详细信息（JSON 格式） |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 创建时间 |

---

## 6. chat_sessions — 对话会话表

**职责：** 存储用户对话会话，记录会话状态和标题。

**状态流转：**
- `active → archived`
- `active → extracted`（已沉淀为 Wiki）

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| title | VARCHAR(255) | ✅ | 新对话 | 会话标题 |
| status | VARCHAR(20) | ✅ | active | 会话状态：active/archived/extracted |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 最后活跃时间 |

---

## 7. chat_messages — 对话消息表

**职责：** 存储对话中的每条消息，记录消息角色和引用来源。

**角色类型：**
- `user`：用户发送的消息
- `assistant`：LLM 生成的回答
- `system`：系统消息（如沉淀通知）

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| session_id | VARCHAR(36) | ✅ | - | 外键 → chat_sessions.id（CASCADE） |
| role | VARCHAR(20) | ✅ | - | 消息角色：user/assistant/system |
| content | TEXT | ✅ | - | 消息内容 |
| sources | JSON | ❌ | NULL | 引用的 Wiki 页面列表：[{id, title}] |
| created_at | DATETIME | ✅ | CURRENT_TIMESTAMP | 发送时间 |

---

## 8. exam_tasks — 练习任务表

**职责：** 记录模拟练习任务的配置、状态和生成结果。

**状态流转：** `pending → processing → completed` 或 `pending → processing → failed`

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| subject | VARCHAR(200) | ✅ | - | 科目名称 |
| focus_points | JSON | ✅ | - | 重点知识点列表 |
| question_types | JSON | ✅ | - | 题目类型列表 |
| output_format | VARCHAR(20) | ✅ | word | 输出格式：word/pdf |
| status | VARCHAR(20) | ✅ | pending | 任务状态：pending/processing/completed/failed |
| error_message | TEXT | ❌ | NULL | 失败原因 |
| task_id | VARCHAR(100) | ❌ | NULL | 任务 ID |
| file_path | VARCHAR(500) | ❌ | NULL | 生成文件存储路径 |
| file_data | BLOB | ❌ | NULL | 生成文件二进制内容 |
| file_name | VARCHAR(200) | ❌ | NULL | 下载文件名 |
| wiki_page_count | INTEGER | ✅ | 0 | 检索到的 Wiki 页面数量 |
| questions_json | JSON | ❌ | NULL | LLM 生成的原始题目 JSON（用于在线刷题） |
| created_at | DATETIME | ✅ | - | 创建时间 |
| completed_at | DATETIME | ❌ | NULL | 完成时间 |

---

## 9. exam_records — 答题记录表

**职责：** 记录一次完整的答题会话。

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| task_id | VARCHAR(36) | ✅ | - | 外键 → exam_tasks.id（CASCADE） |
| total_questions | INTEGER | ✅ | 0 | 总题目数 |
| current_index | INTEGER | ✅ | 0 | 当前作答到第几题（从0开始） |
| correct_count | INTEGER | ✅ | 0 | 已答对的题目数 |
| answered_count | INTEGER | ✅ | 0 | 已作答的题目数 |
| accuracy_rate | FLOAT | ✅ | 0.0 | 正确率（0.0 ~ 1.0） |
| duration_seconds | INTEGER | ✅ | 0 | 答题用时（秒） |
| status | VARCHAR(20) | ✅ | in_progress | 答题状态：in_progress/completed |
| created_at | DATETIME | ✅ | - | 开始答题时间 |
| completed_at | DATETIME | ❌ | NULL | 完成答题时间 |

---

## 10. exam_answers — 每题作答表

**职责：** 记录每道题的作答详情。

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| record_id | VARCHAR(36) | ✅ | - | 外键 → exam_records.id（CASCADE） |
| question_number | INTEGER | ✅ | - | 题目序号（从1开始） |
| question_type | VARCHAR(20) | ✅ | - | 题目类型：选择题/填空题/判断题/简答题/编程题/论述题 |
| question_content | TEXT | ✅ | - | 题目内容 |
| options | JSON | ❌ | NULL | 选项列表（选择题专用） |
| correct_answer | TEXT | ✅ | - | 正确答案 |
| user_answer | TEXT | ❌ | NULL | 用户提交的答案（未作答时为 null） |
| is_correct | BOOLEAN | ❌ | NULL | 是否正确（null 表示未作答） |
| explanation | TEXT | ✅ | "" | 答案解析 |
| answered_at | DATETIME | ❌ | NULL | 作答时间 |

---

## 11. subjects — 学科表

**职责：** 存储学科信息，支持手动创建或从 PDF 上传时自动创建。

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| name | VARCHAR(200) | ✅ | - | 学科名称（唯一） |
| description | TEXT | ❌ | NULL | 学科描述 |
| icon | VARCHAR(100) | ❌ | NULL | 图标（emoji或URL） |
| sort_order | INTEGER | ✅ | 0 | 排序序号 |
| status | VARCHAR(20) | ✅ | active | 状态：active/inactive |
| created_at | DATETIME | ✅ | - | 创建时间 |
| updated_at | DATETIME | ❌ | NULL | 更新时间 |

---

## 12. subject_sources — 学科文档关联表

**职责：** 实现学科与文档的多对多关联。

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| subject_id | VARCHAR(36) | ✅ | - | 外键 → subjects.id（CASCADE） |
| source_id | VARCHAR(36) | ✅ | - | 外键 → wiki_sources.id（CASCADE） |
| created_at | DATETIME | ✅ | - | 创建时间 |

**唯一约束：** `(subject_id, source_id)`

---

## 13. knowledge_points — 知识点表

**职责：** 存储知识点，支持两层层级结构（章→知识点）。

**层级结构：**
- 章：`parent_id = NULL`
- 知识点：`parent_id = 章的ID`

| 字段 | 类型 | 非空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | VARCHAR(36) | ✅ | UUID | 主键 UUID |
| subject_id | VARCHAR(36) | ✅ | - | 外键 → subjects.id（CASCADE） |
| parent_id | VARCHAR(36) | ❌ | NULL | 外键 → knowledge_points.id（CASCADE） |
| wiki_page_id | VARCHAR(36) | ❌ | NULL | 外键 → wiki_pages.id（SET NULL） |
| title | VARCHAR(255) | ✅ | - | 知识点标题 |
| description | TEXT | ❌ | NULL | 知识点描述 |
| point_type | VARCHAR(50) | ✅ | concept | 类型：chapter/concept/entity/summary |
| tags | JSON | ❌ | [] | 标签列表 |
| sort_order | INTEGER | ✅ | 0 | 排序序号 |
| status | VARCHAR(20) | ✅ | active | 状态：active/inactive |
| created_at | DATETIME | ✅ | - | 创建时间 |
| updated_at | DATETIME | ❌ | NULL | 更新时间 |

---

## 14. 表关系总览

```
wiki_sources (1) ──→ (N) wiki_pages
wiki_pages (1) ──→ (N) wiki_links (source_page_id)
wiki_pages (1) ──→ (N) wiki_links (target_page_id)
wiki_pages (1) ──→ (N) wiki_versions
wiki_sources (1) ──→ (N) wiki_logs

chat_sessions (1) ──→ (N) chat_messages

exam_tasks (1) ──→ (N) exam_records
exam_records (1) ──→ (N) exam_answers

subjects (1) ──→ (N) subject_sources (N) ──→ (1) wiki_sources
subjects (1) ──→ (N) knowledge_points
knowledge_points (1) ──→ (N) knowledge_points (自引用，parent_id)
knowledge_points (N) ──→ (1) wiki_pages (可选)
```

---

## PostgreSQL → SQLite 类型映射

| PostgreSQL 类型 | SQLite 类型 | 说明 |
|----------------|-------------|------|
| UUID(as_uuid=True) | VARCHAR(36) | Python 端用 `uuid.uuid4()` 生成字符串 |
| JSONB | JSON | SQLite 原生支持 JSON 函数 |
| LargeBinary (bytea) | BLOB | 二进制存储 |
| DateTime(timezone=True) | DATETIME | SQLite 不区分时区，统一存 UTC |
