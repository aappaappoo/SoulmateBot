"""
Async Database connection using SQLAlchemy 2.0
异步数据库连接管理
"""
from sqlalchemy. ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from config import settings
from src. models.database import Base


def get_async_database_url(url: str) -> str:
    """将同步数据库URL转换为异步URL"""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://")
    elif url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+aiomysql://")
    elif url.startswith("sqlite: ///"):
        return url.replace("sqlite: ///", "sqlite+aiosqlite: ///")
    return url


# 创建异步引擎
async_engine = create_async_engine(
    get_async_database_url(settings.database_url),
    poolclass=NullPool,  # 异步场景推荐
    echo=settings.debug,
)

# 创建异步Session工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（生成器方式）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话（上下文管理器方式）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_async_db():
    """异步初始化数据库表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_async_db():
    """关闭异步数据库连接"""
    await async_engine.dispose()