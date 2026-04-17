import os
import streamlit as st
import sqlalchemy
from db import SessionLocal, engine, Base
from models import Book

_allow_create = os.getenv("ALLOW_CREATE_TABLES") or st.secrets.get("ALLOW_CREATE_TABLES", "0")
if _allow_create == "1":
    Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="IHS Book Production", layout="wide", page_icon="📚")

st.title("IHS Book Production")
st.markdown(
    "Use the **sidebar** to navigate: "
    "**Add Book** to enter a new title, "
    "**Inventory** to browse and search the full list, "
    "**Production** to move books through the pipeline."
)
st.markdown("---")

STAGES = [
    "Acquisitions",
    "In Hand",
    "Scanning",
    "Transcription",
    "Text Editing",
    "Rights & Permissions",
    "Preface & Front Matter",
    "Cover & Art",
    "CIP",
    "Typesetting",
    "Proof",
    "Print Ready",
    "Printing",
    "Marketing",
    "Published",
]

try:
    session = SessionLocal()

    total = session.execute(sqlalchemy.text("SELECT COUNT(*) FROM inventory")).scalar() or 0

    # Count books at each current production stage
    stage_counts = {}
    for stage in STAGES:
        count = session.execute(sqlalchemy.text("""
            SELECT COUNT(*) FROM production p
            WHERE p.stage = :stage
            AND p.id = (
                SELECT MAX(p2.id) FROM production p2 WHERE p2.book_id = p.book_id
            )
        """), {"stage": stage}).scalar() or 0
        stage_counts[stage] = count

    in_pipeline = sum(stage_counts.values())
    not_in_pipeline = total - in_pipeline

    session.close()

    # Top-level metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Books in Inventory", total)
    c2.metric("In Production Pipeline", in_pipeline)
    c3.metric("Not Yet in Pipeline", not_in_pipeline)

    st.markdown("---")
    st.subheader("Books by Production Stage")

    # Stage metrics — 4 per row
    cols = st.columns(4)
    for i, stage in enumerate(STAGES):
        cols[i % 4].metric(stage, stage_counts[stage])

except Exception as e:
    st.warning(f"Could not connect to database: {e}")
