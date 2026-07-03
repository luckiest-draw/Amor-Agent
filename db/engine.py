"""PostgreSQL 异步引擎 + session 工厂."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from amor.config import AmorConfig

config = AmorConfig()

engine = create_async_engine(
    config.database_url,
    echo = False,        # 生产环境关掉，调试时可开 True
    pool_size = 10,      # 连接池大小
    max_overflow = 20,   # 超出 pool_size 后最多再开 20 个
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False, #异步模式必须关，否则commit后实行访问报错
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入用 — 每个请求独立 session，用完自动关闭."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()