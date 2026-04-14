import os
import streamlit as st
from sqlalchemy import func
from db import SessionLocal, engine, Base
from models import Book

if os.getenv("ALLOW_CREATE_TABLES") == "1":
    Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="IHS Inventory", layout="wide", page_icon="📚")

st.title("IHS Book Inventory")
st.markdown(
    "Use the **sidebar** to navigate: "
    "**Add Book** to enter a new title, "
    "**Inventory** to browse and search the full list."
)
st.markdown("---")

try:
    session = SessionLocal()
    total = session.query(func.count(Book.id)).scalar() or 0
    scanned = session.query(func.count(Book.id)).filter(Book.scanned == True).scalar() or 0
    session.close()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Books", total)
    c2.metric("Scanned", scanned)
    c3.metric("Not Yet Scanned", total - scanned)
except Exception as e:
    st.warning(f"Could not connect to database: {e}")
