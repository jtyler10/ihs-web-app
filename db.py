import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()


def _get(key, default=""):
    """Read a config value from Streamlit secrets (cloud) or env vars (local)."""
    # Try Streamlit secrets first (available on Streamlit Community Cloud)
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


DATABASE_URL = _get("DATABASE_URL")
if not DATABASE_URL:
    DB_USER = _get("DB_USER", "ihs_user")
    DB_PASS = quote_plus(_get("DB_PASS", "ihs_pass"))
    DB_HOST = _get("DB_HOST", "127.0.0.1")
    DB_PORT = _get("DB_PORT", "3306")
    DB_NAME = _get("DB_NAME", "ihs_db")
    DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        "?charset=utf8mb4"
    )

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
