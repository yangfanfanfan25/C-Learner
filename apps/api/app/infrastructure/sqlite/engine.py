# ==============================================================================
# SQLAlchemy 同步引擎模块
# ==============================================================================
# 功能：
#   - 创建同步 SQLAlchemy Engine，绑定本地 SQLite 文件
#   - 提供 SessionLocal 同步会话工厂
#   - 定义 Base 声明式基类，供所有领域模型继承
#   - 提供 get_db 依赖注入函数，用于 FastAPI 路由注入
#
# 数据流：
#   settings.sqlite_path → Engine → SessionLocal → 业务代码
# ==============================================================================

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """声明式基类，所有 ORM 模型必须继承此类。"""
    pass


def create_sync_engine(settings: Settings | None = None) -> Engine:
    """创建同步 SQLAlchemy 引擎。

    参数：
        settings: 应用配置，默认使用 get_settings() 获取

    返回：
        SQLAlchemy 同步引擎实例
    """
    if settings is None:
        settings = get_settings()

    db_path: Path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(
        url=f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """创建同步会话工厂。

    参数：
        engine: SQLAlchemy 引擎，默认使用 get_engine()

    返回：
        sessionmaker 工厂实例
    """
    if engine is None:
        engine = create_sync_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


# ==============================================================================
# 模块级单例（延迟初始化）
# ==============================================================================
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """获取或创建模块级引擎单例。"""
    global _engine
    if _engine is None:
        _engine = create_sync_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """获取或创建模块级会话工厂单例。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入函数，yield 一个同步数据库会话。

    使用方式：
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    说明：
        - 自动处理事务提交
        - 异常时自动回滚
        - 请求结束后自动关闭会话
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """创建 Base.metadata 中定义的所有表。

    说明：
        - 仅在开发环境使用
        - 生产环境应使用 Alembic 迁移
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def dispose_engine() -> None:
    """释放引擎连接池。

    说明：
        在应用关闭时调用，释放所有数据库连接。
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
