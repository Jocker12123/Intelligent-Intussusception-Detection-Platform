from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns(table: str, columns: dict) -> None:
    """幂等地为已存在的 SQLite 表补列，避免 create_all 不改旧表导致插入报错。

    columns: {"列名": "类型定义"}，例如 {"model_name": "VARCHAR(100)"}。
    仅对 SQLite（create_all 场景）生效；已有列则跳过。
    """
    with engine.connect() as conn:
        existing = {row["name"] for row in inspect(conn).get_columns(table)}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.commit()
