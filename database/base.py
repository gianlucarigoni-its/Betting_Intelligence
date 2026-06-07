from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Percorso assoluto al file SQLite
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "betting.db"

DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Classe base da cui ereditano tutti i modelli ORM."""
    pass


def get_db():
    """Dependency per ottenere una sessione DB e chiuderla correttamente."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()