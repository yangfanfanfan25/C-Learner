"""SSE 表现层助手：将聊天事件编码为 text/event-stream 文本帧。"""

from __future__ import annotations

import json


def format_sse_event(event: str, data: dict) -> str:
    """编码单个 SSE 帧：``event: <name>`` + ``data: <json>`` + 空行。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
