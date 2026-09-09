# ==============================================================================
# Alembic 环境配置
# ==============================================================================
# 功能：
#   - 导入所有领域模型，使 Alembic 能通过 Base.metadata 发现 schema 变更
#   - 配置 SQLite 的 render_as_batch 模式（支持 ALTER TABLE）
# ==============================================================================

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import get_settings

# 导入 Base 和所有领域模型，确保 metadata 被填充
from app.infrastructure.sqlite.engine import Base
from app.domain import (  # noqa: F401
    # Chat
    ChatMessage,
    ChatSession,
    # Documents
    DocumentRecord,
    DocumentChunk,
    # 新知识库模型
    Domain,
    Chapter,
    KnowledgeCatalog,
    KnowledgeContent,
    KnowledgeLink,
    KnowledgeSource,
    ExamRecord,
    ReviewRecord,
    # 长期记忆（Phase 1：L0 消息 + 游标）
    MemoryL0Message,
    MemoryCursor,
    # 长期记忆（Phase 2：L1 记忆原子 + 生成日志）
    MemoryL1Atom,
    MemoryGenerationLog,
)

# 模拟练习试卷模型定义在 infrastructure 层（非 app.domain），必须单独导入，
# 否则 Base.metadata 缺 quiz_papers，autogenerate 会误判为「多余的表」并生成 drop_table。
from app.infrastructure.quiz import QuizPaper  # noqa: F401

# Alembic 配置对象
config = context.config

# 数据库 URL 从应用配置读取（锚定到仓库根 data/），覆盖 alembic.ini 中的
# 相对路径，避免迁移因启动 CWD 不同而写入错误位置。
_settings = get_settings()
config.set_main_option(
    "sqlalchemy.url",
    f"sqlite:///{_settings.sqlite_path.as_posix()}",
)

# 解析配置文件中的日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 target_metadata，用于 autogenerate 支持
target_metadata = Base.metadata

# FTS5 虚拟表及其影子表由 app 启动时 init_fts() 以 raw DDL 创建
# （见 infrastructure/memory/sqlite_repository.py），刻意不进 Alembic。
# 不排除的话，autogenerate 会把它们误判为「多余的表」并生成 drop_table。
_FTS_TABLE_SUFFIXES = (
    "_fts",
    "_fts_data",
    "_fts_idx",
    "_fts_content",
    "_fts_docsize",
    "_fts_config",
)


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    """autogenerate 比对时排除 FTS5 虚拟表与其影子表。"""
    if type_ == "table" and name and (
        name.startswith("sqlite_") or name.endswith(_FTS_TABLE_SUFFIXES)
    ):
        return False
    return True


def run_migrations_offline() -> None:
    """以 'offline' 模式运行迁移。

    仅使用 URL 配置上下文，不创建 Engine。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 需要此选项支持 ALTER TABLE
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以 'online' 模式运行迁移。

    创建 Engine 并关联连接到上下文。
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 需要此选项支持 ALTER TABLE
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
