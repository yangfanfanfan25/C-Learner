"""阶段1：将上传的文档转换为可处理的页面。

使用 markitdown 库实现文档转换，替代原有的 LibreOffice 方案。
实现 DocumentConverter 接口。
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from app.domain.ports.document_converter import DocumentConverter
from app.schemas.knowledge_pipeline import ParsedDocumentPage

# 幻灯片标记正则
SLIDE_MARKER_RE = re.compile(r"^<!--\s*Slide\s*number\s*:\s*(\d+)\s*-->$", re.IGNORECASE)

# markitdown 直接支持的扩展名（当前不处理图片文件）
MARKITDOWN_EXTENSIONS = {
    ".pdf", ".pptx", ".docx", ".xlsx", ".xls", ".csv",
    ".txt", ".text", ".md", ".markdown", ".json", ".jsonl",
    ".html", ".htm", ".epub", ".ipynb", ".msg", ".zip",
}

# 纯文本扩展名（直接解码，不走 markitdown）
PLAIN_TEXT_EXTENSIONS = {".txt", ".text", ".md", ".markdown"}

# 需要 antiword 转换的旧版 Word 格式
LEGACY_WORD_EXTENSIONS = {".doc"}


class MarkItDownDocumentConverter:
    """使用 markitdown 将文件字节转换为可处理的页面。

    实现 DocumentConverter 接口。支持格式：
    - PDF、DOCX、PPTX、XLSX、HTML、CSV、JSON、XML
    - Markdown、纯文本
    - 旧版 Word（.doc，通过 antiword）
    - URL

    明确不支持的格式：
    - 图片（jpg/jpeg/png）：当前不支持，直接拒绝。
    - 音频：需要转录模型，不属于本产品范围。
    """

    def __init__(self) -> None:
        self._converter: Any | None = None

    def convert(self, file_bytes: bytes, filename: str) -> list[ParsedDocumentPage]:
        """解析文件字节，返回页面列表。"""
        suffix = Path(filename).suffix.lower()

        # 纯文本直接解码返回
        if suffix in PLAIN_TEXT_EXTENSIONS:
            text = file_bytes.decode("utf-8", errors="replace")
            return [ParsedDocumentPage(page_id=1, text=text)]

        # 旧版 Word 用 antiword 转换
        if suffix in LEGACY_WORD_EXTENSIONS:
            text = self._convert_doc_with_antiword(file_bytes, filename)
            return [ParsedDocumentPage(page_id=1, text=text)]

        # 其他格式用 markitdown 转换
        text = self._convert_with_markitdown(file_bytes, filename)

        if not text.strip():
            return [ParsedDocumentPage(page_id=1, text="(空文档)")]

        # 后处理：将幻灯片标记转换为 ## 标题
        text = self._convert_slide_markers(text)

        return [ParsedDocumentPage(page_id=1, text=text)]

    def _convert_with_markitdown(self, file_bytes: bytes, filename: str) -> str:
        # MarkItDown imports optional audio dependencies such as pydub. Delay
        # loading it so normal API startup does not require an ffmpeg runtime.
        from markitdown import MarkItDown, StreamInfo

        """使用 markitdown 转换文档。"""
        suffix = Path(filename).suffix.lower()

        # 不支持的格式，明确报错
        if suffix not in MARKITDOWN_EXTENSIONS:
            raise ValueError(f"不支持的文档类型: {suffix or filename}")

        if self._converter is None:
            self._converter = MarkItDown()

        stream_info = StreamInfo(filename=filename)
        result = self._converter.convert(
            BytesIO(file_bytes),
            stream_info=stream_info,
        )
        text = result.text_content if hasattr(result, "text_content") else str(result)
        return text

    @staticmethod
    def _convert_doc_with_antiword(file_bytes: bytes, filename: str) -> str:
        """使用 antiword 将旧版 Word (.doc) 转换为纯文本。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = tmp / f"source.doc"
            source.write_bytes(file_bytes)

            try:
                result = subprocess.run(
                    ["antiword", str(source)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"antiword 转换失败: {result.stderr.strip()}")
                return result.stdout
            except FileNotFoundError:
                raise RuntimeError("antiword 未安装，无法处理 .doc 文件")

    @staticmethod
    def _convert_slide_markers(text: str) -> str:
        """将 <!-- Slide number: X --> 转换为 ## 幻灯片 X 标题。"""
        lines = text.split("\n")
        result_lines = []

        for line in lines:
            stripped = line.strip()
            match = SLIDE_MARKER_RE.match(stripped)
            if match:
                slide_num = match.group(1)
                result_lines.append(f"## 幻灯片 {slide_num}")
            else:
                result_lines.append(line)

        return "\n".join(result_lines)
