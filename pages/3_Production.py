import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
import streamlit as st
import pandas as pd
from db import SessionLocal
from models import Production

st.set_page_config(page_title="Production — IHS Inventory", layout="wide")
st.title("Production Pipeline")

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
]
TERMINAL = "Published"
ALL_STAGES = STAGES + [TERMINAL]
_PEOPLE = ["", "John Sharpe", "Jacob Hamm", "John Joyce", "Jonathan Tyler"]


# ── Deferred operations (must run before any widgets) ────────────────
_do_advance = st.session_state.pop("_do_advance", None)
if _do_advance:
    session = SessionLocal()
    try:
        session.add(Production(
            book_id=_do_advance["book_id"],
            stage=_do_advance["stage"],
            assigned_to=_do_advance["assigned_to"] or None,
            notes=_do_advance["notes"] or None,
        ))
        session.commit()
        st.success(f"Moved to **{_do_advance['stage']}**.")
    except Exception as e:
        session.rollback()
        st.error(f"Error: {e}")
    finally:
        session.close()

_do_add = st.session_state.pop("_do_add_pipeline", None)
if _do_add:
    session = SessionLocal()
    try:
        existing = session.execute(
            sqlalchemy.text(
                "SELECT id FROM production WHERE book_id = :bid ORDER BY id DESC LIMIT 1"
            ),
            {"bid": _do_add["book_id"]},
        ).fetchone()
        if existing:
            st.warning("This book is already in the pipeline.")
        else:
            session.add(Production(
                book_id=_do_add["book_id"],
                stage=_do_add["stage"],
                assigned_to=_do_add["assigned_to"] or None,
                notes=_do_add["notes"] or None,
            ))
            session.commit()
            st.success(f"Added to pipeline at **{_do_add['stage']}**.")
    except Exception as e:
        session.rollback()
        st.error(f"Error: {e}")
    finally:
        session.close()


# ── Data helpers ──────────────────────────────────────────────────────
def get_pipeline():
    """Current stage per book (excludes Published)."""
    session = SessionLocal()
    try:
        rows = session.execute(sqlalchemy.text("""
            SELECT
                p.book_id, p.stage, p.assigned_to, p.notes, p.created_at,
                b.title, b.authors, b.priority
            FROM production p
            JOIN inventory b ON b.id = p.book_id
            WHERE p.id = (
                SELECT MAX(p2.id) FROM production p2 WHERE p2.book_id = p.book_id
            )
            AND p.stage != :terminal
            ORDER BY b.title
        """), {"terminal": TERMINAL}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        session.close()


def get_history(book_id):
    session = SessionLocal()
    try:
        rows = session.execute(sqlalchemy.text("""
            SELECT stage, assigned_to, notes, created_at
            FROM production
            WHERE book_id = :bid
            ORDER BY id ASC
        """), {"bid": book_id}).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        session.close()


def get_books_not_in_pipeline():
    session = SessionLocal()
    try:
        rows = session.execute(sqlalchemy.text("""
            SELECT b.id, b.title, b.authors
            FROM inventory b
            WHERE b.id NOT IN (
                SELECT DISTINCT book_id FROM production
            )
            ORDER BY b.title
        """)).fetchall()
        return [dict(r._mapping) for r in rows]
    finally:
        session.close()


# ── Add Book to Pipeline ──────────────────────────────────────────────
with st.expander("Add Book to Pipeline", expanded=False):
    available = get_books_not_in_pipeline()
    if not available:
        st.info("All inventory books are already in the pipeline.")
    else:
        book_opts = {b["id"]: f"{b['title']}  —  {b['authors'] or '—'}" for b in available}
        sel_book = st.selectbox(
            "Select book",
            options=list(book_opts.keys()),
            format_func=lambda i: book_opts[i],
            key="add_pipe_book",
        )
        col1, col2 = st.columns(2)
        with col1:
            add_stage    = st.selectbox("Starting stage", ALL_STAGES, key="add_pipe_stage")
            add_assigned = st.selectbox("Assign to", _PEOPLE, key="add_pipe_assigned")
        with col2:
            add_notes = st.text_area("Notes", key="add_pipe_notes", height=100)
        if st.button("Add to Pipeline", type="primary", use_container_width=True):
            st.session_state["_do_add_pipeline"] = {
                "book_id":     sel_book,
                "stage":       add_stage,
                "assigned_to": add_assigned or None,
                "notes":       add_notes.strip() or None,
            }
            st.rerun()

st.markdown("---")

# ── Stage Tabs ────────────────────────────────────────────────────────
pipeline = get_pipeline()
tabs = st.tabs(STAGES)

for tab, stage in zip(tabs, STAGES):
    with tab:
        books_here = [b for b in pipeline if b["stage"] == stage]

        if not books_here:
            st.info(f"No books currently at **{stage}**.")
            continue

        # Reference table
        df = pd.DataFrame([{
            "Title":       b["title"],
            "Authors":     b["authors"] or "—",
            "Assigned To": b["assigned_to"] or "—",
            "Notes":       b["notes"] or "—",
            "Since":       str(b["created_at"])[:10] if b["created_at"] else "—",
            "Priority":    b["priority"] or "—",
        } for b in books_here])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Advance / history
        stage_key = stage.replace(" ", "_")
        with st.expander("Advance a book or view history"):
            book_opts = {b["book_id"]: b["title"] for b in books_here}
            sel_id = st.selectbox(
                "Select book",
                options=list(book_opts.keys()),
                format_func=lambda i: book_opts[i],
                key=f"adv_sel_{stage_key}",
            )

            # History
            history = get_history(sel_id)
            if history:
                st.markdown("**Stage history:**")
                hist_df = pd.DataFrame([{
                    "Stage":       h["stage"],
                    "Assigned To": h["assigned_to"] or "—",
                    "Notes":       h["notes"] or "—",
                    "Date":        str(h["created_at"])[:10] if h["created_at"] else "—",
                } for h in history])
                st.dataframe(hist_df, use_container_width=True, hide_index=True)

            # Advance form
            st.markdown("**Advance to next stage:**")
            current_idx = STAGES.index(stage)
            remaining_stages = ALL_STAGES[current_idx + 1:]

            col1, col2 = st.columns(2)
            with col1:
                next_stage = st.selectbox(
                    "Move to",
                    options=remaining_stages,
                    key=f"next_stage_{stage_key}",
                )
                next_assigned = st.selectbox(
                    "Assign to",
                    _PEOPLE,
                    key=f"next_assigned_{stage_key}",
                )
            with col2:
                next_notes = st.text_area(
                    "Notes",
                    key=f"next_notes_{stage_key}",
                    height=120,
                )

            if st.button("Advance", type="primary", key=f"adv_btn_{stage_key}"):
                st.session_state["_do_advance"] = {
                    "book_id":     sel_id,
                    "stage":       next_stage,
                    "assigned_to": next_assigned or None,
                    "notes":       next_notes.strip() or None,
                }
                st.rerun()
