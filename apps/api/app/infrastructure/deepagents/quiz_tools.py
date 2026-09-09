"""deepagents 模拟练习工具定义。

职责：把「读取用户指定知识文档 → 结构化生成试卷 → 落库写导出文件」封装为
智能体可调用的 ``generate_quiz_paper`` 工具，并把试卷载荷写入共享的
``QuizCollector``，供流式运行时回传 SSE ``quiz`` 事件；执行步骤与出题过程
出题文本通过 LangGraph 原生 ``get_stream_writer`` custom 事件实时上报
（``kind="quiz_token"`` / ``kind="quiz_reset"``）；工具生命周期和最终摘要由
原生 ``tools`` 流输出，供前端逐条展示。

本模块只定义工具与试卷收集器，不包含图结构搭建或业务编排。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.tools import StructuredTool

from app.domain.ports.knowledge_reader import KnowledgeDocumentReader
from app.domain.ports.prompts import SystemPromptProvider
from app.domain.quiz_service import QuizPaperService
from app.infrastructure.deepagents.tools import stream_emit
from app.schemas.quiz import QuizPaper

logger = logging.getLogger(__name__)

_MAX_RETRIES = 1
"""结构化出题失败后的重试次数（共尝试 2 次）。"""


class QuizCollector:
    """共享的试卷载荷收集器：工具生成成功后 set 一次，流式循环 drain 一次。

    试卷是**单次完整载荷**（取走即清空），用于发出一次性 SSE ``quiz`` 事件。
    """

    def __init__(self) -> None:
        self._payload: dict[str, Any] | None = None

    def set(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def drain(self) -> dict[str, Any] | None:
        payload, self._payload = self._payload, None
        return payload


def build_generate_quiz_tool(
    *,
    session_id: str | None,
    document_ids: list[str],
    knowledge_reader: KnowledgeDocumentReader,
    quiz_service: QuizPaperService,
    quiz_generation_model: Any,
    prompt_provider: SystemPromptProvider,
    collector: QuizCollector,
) -> StructuredTool:
    """构建模拟练习出题工具。

    出题依据的文档由前端 ``@`` 选择并经请求透传（``document_ids``，构建时固定），
    工具不检索知识库，直接按 ID 读取已入库知识内容注入上下文。
    ``quiz_generation_model`` 为组合根创建的普通聊天模型（不要求
    ``with_structured_output``——部分模型/推理模式不支持 response_format 或
    强制 tool_choice）；工具内部要求模型输出 JSON 文本并解析校验
    （``QuizPaper`` schema，失败重试一次，仍失败则抛 ``RuntimeError``，
    由 agent 转为文本说明，不产出半成品试卷）。

    出题生成使用 ``astream`` 流式调用，文本增量经 ``stream_emit`` 实时上报
    ``quiz_token`` custom 事件（框架原生通道，工具执行期间即送达主循环），
    前端在生成过程中逐条看到输出，而不是等整卷生成完才一次性推送。
    """

    async def generate_quiz_paper(requirements: str) -> str:
        """根据出题需求（题型、数量、难度、重点等）基于已选知识文档生成一套模拟练习试卷。"""
        documents = knowledge_reader.get_documents(document_ids)
        if not documents:
            message = (
                "尚未选择可用的知识文档。请在输入框中通过 @ 选择已处理完成的文档，"
                "再发起出题。"
            )
            return message

        context_parts: list[str] = []
        for document in documents:
            markdown = knowledge_reader.read_markdown([document.id]).get(document.id)
            if markdown:
                context_parts.append(f"## 文档：{document.filename}\n\n{markdown}")
        document_context = "\n\n---\n\n".join(context_parts) or "（给定知识内容为空）"

        prompt = prompt_provider.quiz_generation_prompt().format(
            document_context=document_context,
            requirements=requirements or "未指定具体需求，请自行合理确定题型、题量与难度。",
        )
        paper = await _generate_paper_with_retry(quiz_generation_model, prompt)
        if not paper.questions:
            raise RuntimeError("题目生成失败：模型未返回任何题目")

        detail = quiz_service.create_paper(
            session_id=session_id,
            title=paper.title,
            document_ids=[document.id for document in documents],
            document_titles=[document.filename for document in documents],
            requirements=requirements or None,
            paper=paper,
        )
        collector.set(
            {
                "paper_id": detail.id,
                "title": detail.title,
                "total": detail.total,
                "difficulty": detail.difficulty,
                "question_types": detail.question_types,
                "downloads": (
                    {"md": detail.downloads["md"], "json": detail.downloads["json"]}
                    if detail.downloads
                    else None
                ),
                "questions": [question.model_dump() for question in detail.questions],
            }
        )

        return (
            f"试卷生成成功：《{detail.title}》共 {detail.total} 题。"
            "结构化试卷和下载入口已通过系统事件提供，请简短提示用户点击“开始答题”。"
        )

    return StructuredTool.from_function(
        name="generate_quiz_paper",
        description=(
            "根据出题需求（requirements，含题型、数量、难度、重点等）生成一套模拟练习试卷。"
            "出题依据的知识文档已由用户通过 @ 选择，工具直接读取其知识内容，无需再检索；"
    "结构化试卷由系统单独展示；工具返回简短的生成结果摘要。"
        ),
        coroutine=generate_quiz_paper,
    )


async def _generate_paper_with_retry(
    model: Any,
    prompt: str,
) -> QuizPaper:
    """调用模型流式生成试卷：要求输出 JSON 文本，解析后经 schema 校验，失败带错重试一次。

    不依赖 ``with_structured_output``：部分模型/推理模式不支持
    ``response_format`` 或强制 ``tool_choice``，故采用「提示词约束 JSON +
    文本解析 + schema 校验」的兼容方案。

    使用 ``astream`` 逐段消费模型输出：每个文本增量同步经 ``stream_emit``
    实时上报 ``quiz_token`` custom 事件，前端可逐条看到出题过程输出，
    而不是等整卷生成完才一次性推送。
    """
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            full_text = ""
            async for chunk in model.astream(prompt):
                delta = _chunk_text(chunk)
                if delta:
                    full_text += delta
                    stream_emit("quiz_token", delta)
            payload = _extract_json(full_text)
            return QuizPaper.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - 解析/校验/调用失败统一进入重试与报错
            last_error = exc
            logger.warning("Quiz generation attempt %d failed: %s: %s", attempt + 1, type(exc).__name__, exc)
            if attempt < _MAX_RETRIES:
                stream_emit("quiz_reset", None)
    raise RuntimeError(f"题目生成失败（JSON 解析或 schema 校验未通过）：{type(last_error).__name__}: {last_error}")


def _chunk_text(chunk: Any) -> str:
    """把流式输出 chunk（AIMessageChunk / str / dict）归一为文本增量。"""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        return str(chunk.get("text") or chunk.get("content") or "")
    content = getattr(chunk, "content", None)
    if content is None:
        return str(chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                parts.append(str(text))
        return "".join(parts)
    return str(content)


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON 对象：剥离 markdown 围栏，取首个 { 到末尾 }。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型输出中未找到 JSON 对象")
    return json.loads(stripped[start : end + 1])
