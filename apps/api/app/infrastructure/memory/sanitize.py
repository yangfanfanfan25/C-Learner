"""L0 消息清洗：剥记忆标签/指令/时间戳/媒体/base64/System 块、剥代码块、捕获判定。

Phase 1（L0 capture）在写库前调用：纯函数、无 I/O、无外部依赖（仅标准库 ``re``），
只做文本归一化，不落地任何状态。

已知延期：spec §5 的「网关元数据块」与「长度上限 / prompt 注入检测」因格式未知
或原文已注释，本期不实现（对应 spec §9 风险 3）。
"""

from __future__ import annotations

import re

_MEMORY_TAGS = re.compile(
    r"</?(?:relevant-memories|user-persona|relevant-scenes|scene-navigation)>.*?"
    r"</(?:relevant-memories|user-persona|relevant-scenes|scene-navigation)>",
    re.DOTALL,
)
_REPLY_TO = re.compile(r"\[\[reply_to_[^\]]*\]\]")
_TIMESTAMP = re.compile(r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*", re.MULTILINE)
_MEDIA = re.compile(r"\[media attached:[^\]]*\]")
_BASE64 = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+")
_SYSTEM_BLOCK = re.compile(r"System:\[[^\]]*\]")
_NULL_BYTE = re.compile(r"\x00")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_CODE_BLOCK = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)


def sanitize_text(text: str) -> str:
    """剥清洗标签与噪声，折叠多余换行，返回去首尾空白的结果。"""
    out = _MEMORY_TAGS.sub("", text)
    out = _REPLY_TO.sub("", out)
    out = _TIMESTAMP.sub("", out)
    out = _MEDIA.sub("", out)
    out = _BASE64.sub("", out)
    out = _SYSTEM_BLOCK.sub("", out)
    out = _NULL_BYTE.sub("", out)
    out = _MULTI_NEWLINE.sub("\n", out)
    return out.strip()


def strip_code_blocks(text: str) -> str:
    """仅剥 fenced 代码块（三个反引号开闭，可带语言标识），整段移除。"""
    return _CODE_BLOCK.sub("", text)


def should_capture_l0(text: str) -> bool:
    """拒空/纯空白与斜杠命令，其余可入 L0。"""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("/"):
        return False
    return True
