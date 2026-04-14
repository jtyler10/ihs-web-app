import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from sqlalchemy import or_
from db import SessionLocal
from models import Book
from search import search_openlibrary_by_title, search_openlibrary_by_isbn

st.set_page_config(page_title="Add Book — IHS Inventory", layout="centered")
st.title("Add Book to Inventory")

# ── Session state defaults ───────────────────────────────────────────
_DEFAULTS = {
    "f_title": "", "f_authors": "", "f_isbn": "", "f_publisher": "",
    "f_pub_year": "", "f_pages": 0, "f_language": "", "f_description": "",
    "f_condition": "Good", "f_scanned": False, "f_owner": "",
    "f_priority": "Medium", "f_potential_imprint": "", "f_notes": "",
    "_search_results": [],
    "_inv_matches": [],
    "_confirmed_no_dup": False,
}
# Apply any pending form operations before widgets render
if st.session_state.pop("_do_clear", False):
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v

r = st.session_state.pop("_prefill", None)
if r:
    st.session_state["f_title"] = r.get("title") or ""
    st.session_state["f_authors"] = r.get("authors") or ""
    st.session_state["f_isbn"] = r.get("isbn") or ""
    st.session_state["f_publisher"] = r.get("publisher") or ""
    st.session_state["f_pub_year"] = r.get("pub_year") or ""
    st.session_state["f_language"] = r.get("language") or ""
    if r.get("pages"):
        st.session_state["f_pages"] = int(r["pages"])

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def check_inventory(title, isbn):
    """Return existing inventory rows that match the given title or ISBN."""
    session = SessionLocal()
    try:
        filters = []
        if isbn:
            filters.append(Book.isbn == isbn.strip())
        if title:
            filters.append(Book.title.ilike(f"%{title.strip()}%"))
        if not filters:
            return []
        return session.query(Book).filter(or_(*filters)).all()
    finally:
        session.close()


# ── Open Library search ──────────────────────────────────────────────
with st.expander("Search Open Library to autofill", expanded=True):
    s_col1, s_col2 = st.columns([4, 1])
    with s_col1:
        search_q = st.text_input(
            "Search", placeholder="Enter a title or ISBN…", label_visibility="collapsed"
        )
    with s_col2:
        s_type = st.radio("by", ["Title", "ISBN"], horizontal=True, label_visibility="collapsed")

    if st.button("Search", use_container_width=True):
        if not search_q.strip():
            st.warning("Enter a title or ISBN.")
        else:
            with st.spinner("Searching Open Library…"):
                try:
                    if s_type == "ISBN":
                        result = search_openlibrary_by_isbn(search_q.strip())
                        st.session_state["_search_results"] = [result] if result else []
                    else:
                        st.session_state["_search_results"] = search_openlibrary_by_title(
                            search_q.strip()
                        )
                    if not st.session_state["_search_results"]:
                        st.info("No results found on Open Library. Fill in the form below manually.")
                except Exception as e:
                    st.error(f"Search error: {e}")
                    st.session_state["_search_results"] = []

    if st.session_state["_search_results"]:
        st.markdown("**Select a result to autofill the form:**")
        for i, r in enumerate(st.session_state["_search_results"]):
            label = (
                f"{r.get('title', '—')}  |  "
                f"{r.get('authors') or '—'}  |  "
                f"{r.get('pub_year') or '—'}"
            )
            if st.button(f"Autofill: {label[:90]}", key=f"use_{i}"):
                st.session_state["_prefill"] = r
                st.session_state["_search_results"] = []
                st.session_state["_inv_matches"] = []
                st.session_state["_confirmed_no_dup"] = False
                st.experimental_rerun()

st.markdown("---")
st.subheader("Book Details")

col1, col2 = st.columns(2)
with col1:
    st.text_input("Title *", key="f_title")
    st.text_input("Authors (comma-separated)", key="f_authors")
    st.text_input("ISBN", key="f_isbn")
    st.text_input("Publisher", key="f_publisher")
    st.text_input("Publication Year", key="f_pub_year")
with col2:
    st.number_input("Pages", min_value=0, step=1, key="f_pages")
    st.text_input("Language", key="f_language")
    st.selectbox("Condition", ["New", "Good", "Fair", "Poor", "Damaged"], key="f_condition")
    st.selectbox("Priority", ["High", "Medium", "Low"], key="f_priority")
    st.text_input("Owner", key="f_owner")
    st.text_input("Potential Imprint", key="f_potential_imprint")
    st.checkbox("Scanned", key="f_scanned")

st.text_area("Description", key="f_description", height=80)
st.text_area("Notes", key="f_notes", height=80)

st.markdown("---")

# ── Inventory duplicate check ────────────────────────────────────────
if st.button("Check Inventory for Duplicates", use_container_width=True):
    title_val = st.session_state.f_title.strip()
    isbn_val = st.session_state.f_isbn.strip()
    if not title_val and not isbn_val:
        st.warning("Enter a title or ISBN above before checking.")
    else:
        matches = check_inventory(title_val, isbn_val)
        st.session_state["_inv_matches"] = [
            {"id": b.id, "title": b.title, "authors": b.authors or "—",
             "isbn": b.isbn or "—", "pub_year": b.pub_year or "—",
             "condition": b.condition or "—", "owner": b.owner or "—"}
            for b in matches
        ]
        st.session_state["_confirmed_no_dup"] = False

if st.session_state["_inv_matches"]:
    st.warning(f"Found {len(st.session_state['_inv_matches'])} matching record(s) already in inventory:")
    for m in st.session_state["_inv_matches"]:
        st.markdown(
            f"- **{m['title']}** | Authors: {m['authors']} | "
            f"ISBN: {m['isbn']} | Year: {m['pub_year']} | "
            f"Condition: {m['condition']} | Owner: {m['owner']} *(id={m['id']})*"
        )
    st.session_state["_confirmed_no_dup"] = st.checkbox(
        "I've reviewed the matches above — save as a new entry anyway",
        value=st.session_state["_confirmed_no_dup"],
        key="dup_confirm_checkbox",
    )
elif "dup_confirm_checkbox" not in st.session_state:
    # Check hasn't been run yet — show a neutral note
    st.caption("Tip: click **Check Inventory for Duplicates** before saving to avoid adding the same book twice.")

# ── Save ─────────────────────────────────────────────────────────────
save_blocked = bool(st.session_state["_inv_matches"]) and not st.session_state["_confirmed_no_dup"]

if st.button("Save to Inventory", type="primary", use_container_width=True, disabled=save_blocked):
    title_val = st.session_state.f_title.strip()
    if not title_val:
        st.error("Title is required.")
    else:
        session = SessionLocal()
        try:
            new_book = Book(
                title=title_val,
                authors=st.session_state.f_authors.strip() or None,
                isbn=st.session_state.f_isbn.strip() or None,
                publisher=st.session_state.f_publisher.strip() or None,
                pub_year=st.session_state.f_pub_year.strip() or None,
                pages=int(st.session_state.f_pages) if st.session_state.f_pages else None,
                language=st.session_state.f_language.strip() or None,
                description=st.session_state.f_description.strip() or None,
                condition=st.session_state.f_condition,
                scanned=st.session_state.f_scanned,
                owner=st.session_state.f_owner.strip() or None,
                priority=st.session_state.f_priority,
                potential_imprint=st.session_state.f_potential_imprint.strip() or None,
                notes=st.session_state.f_notes.strip() or None,
                source="web-form",
            )
            session.add(new_book)
            session.commit()
            st.success(f"Saved **{new_book.title}** (id={new_book.id})")
            st.session_state["_do_clear"] = True
            st.experimental_rerun()
        except Exception as e:
            session.rollback()
            st.error(f"Error saving: {e}")
        finally:
            session.close()
