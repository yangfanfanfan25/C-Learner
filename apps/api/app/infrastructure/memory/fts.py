"""FTS5 连接原语：raw DDL 建表 + BM25 MATCH 检索。

仅提供建表/检索两个纯函数，连接由调用方（未来的 SqliteMemoryRepository）打开。
业务表名与列（l0_conversation_fts / l1_memory_fts）在 Phase 1/2 才定义，
本阶段只交付「可建任意列 FTS5 表 + 按 bm25 排序检索」的通用能力。
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# trigram 分词器把 ASCII 标点（. " ( ) [ ] { } ~ : ! ? ' , ; @ # - / 等）当作 FTS5
# 语法解析并抛 fts5 syntax error；对自然语言问题把它们替换为空格，得到纯字面 token
# 流供子串匹配。保留字母/数字/CJK（\w，unicode 默认含中文）与空白（\s）。
_FTS5_SPECIAL = re.compile(r"[^\w\s]")


@dataclass(frozen=True)
class FtsHit:
    """一条 BM25 命中：行 rowid + 各列取值 + 原始 bm25 分数。"""

    rowid: int
    columns: dict[str, Any]
    score: float


def create_fts5_table(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    tokenize: str = "trigram",
) -> None:
    """以 ``CREATE VIRTUAL TABLE IF NOT EXISTS ... USING fts5(...)`` 建表。

    默认 ``tokenize='trigram'``：实测（SQLite 3.53.1）默认 unicode61 分词器对
    中文（连续 CJK 字符被当单个 token）完全无法关键词检索；trigram 支持中文子串
    匹配，但查询需 ≥3 字符。表名/列名/分词器均为内部常量，不来自用户输入，
    故不做 SQL 注入防护。
    """
    col_sql = ", ".join(columns)
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {table_name} "
        f"USING fts5({col_sql}, tokenize='{tokenize}')"
    )


def fts_search(
    conn: sqlite3.Connection,
    table_name: str,
    query: str,
    top_k: int,
) -> list[FtsHit]:
    """BM25 MATCH 检索，按匹配度降序返回前 ``top_k`` 条。

    ``ORDER BY bm25(...)``（升序）即最优匹配排前（实测 bm25 返回负值、越负越好）。
    返回 ``FtsHit.score`` 为原始 bm25 值，RRF 归一化（Phase 5）再定方向。查询串
    按字面子串匹配（trigram 不支持 OR/AND/前缀等 FTS5 运算符），recall 层
    （Phase 5）进入前先 sanitize_text 并做长度兜底。

    查询可能来自自然语言问题，含 ``.`` ``"`` ``*`` ``()`` 等 ASCII 标点时 trigram
    分词器会把它当 FTS5 语法并抛 ``sqlite3.OperationalError: fts5: syntax error``。
    此处先剥离特殊字符得到纯字面 token，再对残余解析错误降级为空结果（不打断
    recall 链路）。
    """
    if not query.strip():
        return []
    # 去掉 FTS5 语法/ASCII 标点，避免 MATCH 解析报错；留空白分隔的字面 token 流。
    safe_query = _FTS5_SPECIAL.sub(" ", query).strip()
    if not safe_query:
        return []
    sql = (
        f"SELECT rowid, *, bm25({table_name}) AS _score "
        f"FROM {table_name} WHERE {table_name} MATCH ? ORDER BY _score LIMIT ?"
    )
    try:
        cursor = conn.execute(sql, (safe_query, top_k))
        names = [d[0] for d in cursor.description]
        hits: list[FtsHit] = []
        for row in cursor.fetchall():
            values = dict(zip(names, row))
            columns = {k: v for k, v in values.items() if k not in ("rowid", "_score")}
            hits.append(
                FtsHit(rowid=values["rowid"], columns=columns, score=float(values["_score"]))
            )
        return hits
    except sqlite3.OperationalError as exc:
        logger.warning("fts_search MATCH 失败，降级为空: %r: %s", query, exc)
        return []
