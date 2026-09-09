"""模拟练习试卷应用服务。

职责：试卷落库、导出文件（md/json）、查询与判分。
判分为纯函数（``grade_paper``），不依赖数据库；创建/查询依赖注入的
DB 会话与 ``QuizFileStorage``。
"""

from __future__ import annotations

import json
import re

from app.domain.ports.quiz_file_storage import QuizFileStorage
from app.infrastructure.quiz import QuizPaper as QuizPaperRecord
from app.schemas.quiz import (
    QuizAnswerInput,
    QuizGradeResponse,
    QuizGradeResultItem,
    QuizPaper,
    QuizPaperDetailResponse,
    QuizQuestion,
)

_TYPE_NAMES = {
    "choice": "选择题",
    "multi_choice": "多选题",
    "true_false": "判断题",
    "fill": "填空题",
    "short_answer": "简答题",
}

_DIFFICULTY_NAMES = {1: "基础", 2: "进阶", 3: "综合"}

_SECTION_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}


def _safe_filename(title: str) -> str:
    """把试卷标题转成安全文件名（去非法字符、压缩空白、限长）。"""
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_") or "quiz"
    return stem[:80]


def _answer_text(question: QuizQuestion) -> str:
    """把参考答案格式化为 Markdown 展示文本。"""
    if question.type == "true_false":
        return "正确" if question.answer is True else "错误"
    if isinstance(question.answer, list):
        return "、".join(str(item) for item in question.answer)
    return str(question.answer)


class QuizPaperService:
    """试卷创建 / 查询 / 判分 / 导出。"""

    def __init__(self, db, file_storage: QuizFileStorage) -> None:
        self.db = db
        self.file_storage = file_storage

    # -- creation ------------------------------------------------------------

    def create_paper(
        self,
        *,
        session_id: str | None,
        title: str,
        document_ids: list[str],
        document_titles: list[str],
        requirements: str | None,
        paper: QuizPaper,
    ) -> QuizPaperDetailResponse:
        """校验后的试卷落库并写出 md/json 导出文件。"""
        record = QuizPaperRecord(
            session_id=session_id,
            title=title,
            document_ids=document_ids or None,
            document_titles=document_titles or None,
            requirements=requirements,
            question_types=paper.question_types,
            difficulty=paper.difficulty,
            questions_json=paper.model_dump_json(),
        )
        self.db.add(record)
        self.db.flush()  # 生成 record.id

        stem = _safe_filename(title)
        md_bytes = self.build_markdown(paper).encode("utf-8")
        json_bytes = paper.model_dump_json(indent=2, ensure_ascii=False).encode("utf-8")
        record.file_path_md = self.file_storage.save(record.id, f"{stem}.md", md_bytes)
        record.file_path_json = self.file_storage.save(record.id, f"{stem}.json", json_bytes)

        self.db.commit()
        self.db.refresh(record)
        return self._detail(record)

    # -- queries -------------------------------------------------------------

    def get_paper(self, paper_id: str) -> QuizPaperDetailResponse | None:
        record = (
            self.db.query(QuizPaperRecord)
            .filter(QuizPaperRecord.id == paper_id)
            .first()
        )
        if record is None:
            return None
        return self._detail(record)

    def resolve_export_file(
        self,
        paper_id: str,
        file_format: str,
    ) -> tuple[str | None, str | None]:
        """返回 ``(相对路径, 下载文件名)``；试卷不存在或格式不支持时返回 (None, None)。

        ``file_format`` 仅支持 ``md`` / ``json``。
        """
        record = (
            self.db.query(QuizPaperRecord)
            .filter(QuizPaperRecord.id == paper_id)
            .first()
        )
        if record is None:
            return None, None
        if file_format == "md":
            return record.file_path_md, f"{_safe_filename(record.title)}.md"
        if file_format == "json":
            return record.file_path_json, f"{_safe_filename(record.title)}.json"
        return None, None

    # -- grading -------------------------------------------------------------

    @staticmethod
    def grade_paper(
        paper: QuizPaperDetailResponse,
        answers: list[QuizAnswerInput],
    ) -> QuizGradeResponse:
        """按题型规则判分（纯函数，不落库）。

        short_answer 不自动判分（correct 为 None），计入 total 但不计入 correct_count。
        """
        by_id = {question.id: question for question in paper.questions}
        results: list[QuizGradeResultItem] = []
        correct_count = 0
        for question in paper.questions:
            user_answer = next(
                (answer.value for answer in answers if answer.question_id == question.id),
                None,
            )
            correct = QuizPaperService._check_answer(question, user_answer)
            if correct is True:
                correct_count += 1
            results.append(
                QuizGradeResultItem(
                    question_id=question.id,
                    correct=correct,
                    user_answer=user_answer,
                    correct_answer=question.answer,
                    explanation=question.explanation,
                )
            )
        score = round(correct_count / paper.total * 100) if paper.total else 0
        return QuizGradeResponse(
            paper_id=paper.id,
            total=paper.total,
            correct_count=correct_count,
            score=score,
            results=results,
        )

    @staticmethod
    def _check_answer(question: QuizQuestion, user_answer: object) -> bool | None:
        """单题判分：返回 True/False；short_answer 不自动判分（返回 None）。"""
        if question.type == "short_answer":
            return None
        if user_answer is None:
            return False
        if question.type == "choice":
            return user_answer == question.answer
        if question.type == "multi_choice":
            if not isinstance(user_answer, list):
                return False
            return set(user_answer) == set(question.answer)
        if question.type == "true_false":
            return user_answer == question.answer
        if question.type == "fill":
            return str(user_answer).strip() == str(question.answer).strip()
        return None

    # -- export --------------------------------------------------------------

    @staticmethod
    def build_markdown(paper: QuizPaper) -> str:
        """渲染标准 Markdown 试卷：题目在前（不含答案），参考答案与解析收在文末。"""
        lines = [
            f"# {paper.title}",
            "",
            f"> 难度：{_DIFFICULTY_NAMES.get(paper.difficulty, paper.difficulty)} ｜ "
            f"共 {paper.total} 题 ｜ 题型：{'、'.join(_TYPE_NAMES.get(t, t) for t in paper.question_types)}",
            "",
        ]

        number = 0
        section_index = 1
        for qtype in paper.question_types:
            group = [q for q in paper.questions if q.type == qtype]
            lines.append(f"## {_SECTION_CN.get(section_index, section_index)}、{_TYPE_NAMES.get(qtype, qtype)}（{len(group)} 题）")
            lines.append("")
            for question in group:
                number += 1
                lines.append(f"### {number}. {question.stem}")
                lines.append("")
                for option in question.options:
                    lines.append(f"- {option.key}. {option.text}")
                if question.options:
                    lines.append("")
            section_index += 1

        lines.append("---")
        lines.append("")
        lines.append("## 参考答案与解析")
        lines.append("")
        number = 0
        for qtype in paper.question_types:
            group = [q for q in paper.questions if q.type == qtype]
            for question in group:
                number += 1
                lines.append(f"### {number}. {question.stem}")
                lines.append("")
                lines.append(f"- 答案：{_answer_text(question)}")
                if question.explanation:
                    lines.append(f"- 解析：{question.explanation}")
                if question.knowledge_points:
                    lines.append(f"- 知识点：{'、'.join(question.knowledge_points)}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # -- internals -----------------------------------------------------------

    def _detail(self, record: QuizPaperRecord) -> QuizPaperDetailResponse:
        paper = QuizPaper.model_validate(json.loads(record.questions_json))
        downloads = None
        if record.file_path_md and record.file_path_json:
            downloads = {
                "md": f"/api/quiz/papers/{record.id}/download?format=md",
                "json": f"/api/quiz/papers/{record.id}/download?format=json",
            }
        return QuizPaperDetailResponse(
            id=record.id,
            session_id=record.session_id,
            title=record.title,
            document_ids=record.document_ids or [],
            document_titles=record.document_titles or [],
            requirements=record.requirements,
            difficulty=record.difficulty,
            question_types=paper.question_types,
            total=paper.total,
            questions=paper.questions,
            downloads=downloads,
            created_at=record.created_at,
        )
