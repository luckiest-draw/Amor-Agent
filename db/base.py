"""SQLAlchemy 声明式基类 — 所有 Model 继承它."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass