import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
import streamlit as st
from db import SessionLocal
from models import Book
from search import (
    search_openlibrary_by_title,
    search_openlibrary_by_author,
    search_openlibrary_advanced,
    search_openlibrary_by_isbn,
)

st.set_page_config(page_title="Add Book — IHS Inventory", layout="centered")
st.title("Add Book to Inventory")

_MANUAL = "— Type name manually —"
_OWNERS = ["John Sharpe", "Jacob Hamm", "John Joyce", "Jonathan Tyler"]

_IMPRINTS = [
    "",
    "IHS Press",
    "Nota Tomus Gregoriana",
    "HarperCollins",
    "American Chesterton Society",
    "Liberty Fund",
    "Light in the Darkness Publications",
    "Family Publications",
    "Louisiana State University Press",
    "Gates of Vienna Books",
    "Australian Heritage Society",
    "Catholic Central Verein of America",
    "Enigma Editions",
    "Forgotten Voices Editions",
    "Freedom Publishing",
    "Intercollegiate Studies Institute",
    "Sapientia Press",
    "Tradibooks",
    "Traditionalist Press",
    "Transaction Publishers",
    "University of Chicago Press",
    "University of Notre Dame Press",
    "The Schoolman Bookshelf",
]

# ── Load contributors and publishers once per session ─────────────────
if "_contributors" not in st.session_state:
    session = SessionLocal()
    try:
        rows = session.execute(
            sqlalchemy.text("SELECT c_name FROM contributors ORDER BY c_lname, fname")
        )
        st.session_state["_contributors"] = [row[0] for row in rows if row[0]]
    finally:
        session.close()

if "_publishers" not in st.session_state:
    session = SessionLocal()
    try:
        rows = session.execute(
            sqlalchemy.text("SELECT op_name FROM original_publishers ORDER BY op_name")
        )
        st.session_state["_publishers"] = [row[0] for row in rows if row[0]]
    finally:
        session.close()

_DEFAULTS = {
    "f_title": "", "f_author_select": _MANUAL, "f_authors": "",
    "f_publisher_select": _MANUAL, "f_publisher": "",
    "f_isbn": "", "f_pub_year": "", "f_pages": 0,
    "f_language": "", "f_description": "",
    "f_condition": "Good", "f_scanned": False, "f_owner": _OWNERS[0],
    "f_priority": "Medium", "f_potential_imprint": _IMPRINTS[0], "f_notes": "",
    "_search_results": [],
}

# ── Apply pending form operations before any widget renders ───────────
if st.session_state.pop("_do_clear", False):
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v

new_pub = st.session_state.pop("_set_publisher_select", None)
if new_pub:
    st.session_state["f_publisher_select"] = new_pub

new_author = st.session_state.pop("_set_author_select", None)
if new_author:
    st.session_state["f_author_select"] = new_author

prefill = st.session_state.pop("_prefill", None)
if prefill:
    st.session_state["f_title"]    = prefill.get("title") or ""
    st.session_state["f_isbn"]     = prefill.get("isbn") or ""
    st.session_state["f_pub_year"] = prefill.get("pub_year") or ""
    # Try to match incoming publisher to the original_publishers table
    incoming_pub = (prefill.get("publisher") or "").strip().lower()
    pub_match = next(
        (p for p in st.session_state["_publishers"]
         if incoming_pub and (incoming_pub in p.lower() or p.lower() in incoming_pub)),
        None,
    )
    if pub_match:
        st.session_state["f_publisher_select"] = pub_match
    else:
        st.session_state["f_publisher_select"] = _MANUAL
        st.session_state["f_publisher"] = prefill.get("publisher") or ""
    st.session_state["f_language"]  = prefill.get("language") or ""
    if prefill.get("pages"):
        st.session_state["f_pages"] = int(prefill["pages"])
    # Try to match incoming author to a contributor name
    incoming = (prefill.get("authors") or "").strip().lower()
    match = next(
        (c for c in st.session_state["_contributors"]
         if incoming and (incoming in c.lower() or c.lower() in incoming)),
        None,
    )
    if match:
        st.session_state["f_author_select"] = match
    else:
        st.session_state["f_author_select"] = _MANUAL
        st.session_state["f_authors"] = prefill.get("authors") or ""

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Open Library Search ───────────────────────────────────────────────
with st.expander("Search Open Library to autofill", expanded=True):
    s_type = st.radio(
        "Search by",
        ["Title", "Author", "ISBN", "Title + Author"],
        horizontal=True,
    )

    if s_type in ("Title", "Title + Author"):
        st.text_input("Title", placeholder="Enter title…", key="s_title")
    if s_type in ("Author", "Title + Author"):
        st.text_input("Author", placeholder="Enter author…", key="s_author")
    if s_type == "ISBN":
        st.text_input("ISBN", placeholder="Enter ISBN…", key="s_isbn")

    if st.button("Search", use_container_width=True):
        # Clear old per-result checkbox states
        for i in range(len(st.session_state.get("_search_results", []))):
            st.session_state.pop(f"chk_{i}", None)

        with st.spinner("Searching Open Library…"):
            try:
                if s_type == "Title":
                    q = st.session_state.get("s_title", "").strip()
                    if not q:
                        st.warning("Enter a title.")
                    else:
                        st.session_state["_search_results"] = search_openlibrary_by_title(q)

                elif s_type == "Author":
                    q = st.session_state.get("s_author", "").strip()
                    if not q:
                        st.warning("Enter an author.")
                    else:
                        st.session_state["_search_results"] = search_openlibrary_by_author(q)

                elif s_type == "ISBN":
                    q = st.session_state.get("s_isbn", "").strip()
                    if not q:
                        st.warning("Enter an ISBN.")
                    else:
                        result = search_openlibrary_by_isbn(q)
                        st.session_state["_search_results"] = [result] if result else []

                elif s_type == "Title + Author":
                    qt = st.session_state.get("s_title", "").strip()
                    qa = st.session_state.get("s_author", "").strip()
                    if not qt and not qa:
                        st.warning("Enter a title and/or author.")
                    else:
                        st.session_state["_search_results"] = search_openlibrary_advanced(
                            title=qt, author=qa
                        )

                if st.session_state["_search_results"] == []:
                    st.info("No results found. Fill in the form below manually.")

            except Exception as e:
                st.error(f"Search error: {e}")
                st.session_state["_search_results"] = []

    # ── Results: reference table + edition picker ─────────────────────
    if st.session_state["_search_results"]:
        import pandas as pd

        results = st.session_state["_search_results"]

        # Build a flat reference table — one row per edition
        rows = []
        for r in results:
            isbns = r.get("all_isbns") or ([r["isbn"]] if r.get("isbn") else ["—"])
            pubs  = r.get("all_publishers") or ([r["publisher"]] if r.get("publisher") else ["—"])
            # Cross all ISBNs with all publishers for this result
            for isbn in (isbns or ["—"]):
                for pub in (pubs or ["—"]):
                    rows.append({
                        "Title":     r.get("title") or "—",
                        "Authors":   r.get("authors") or "—",
                        "Year":      r.get("pub_year") or "—",
                        "Publisher": pub or "—",
                        "ISBN":      isbn or "—",
                    })

        ref_df = pd.DataFrame(rows)
        st.markdown("**All editions found — use as reference:**")
        st.dataframe(ref_df, use_container_width=True)

        # Edition picker — one entry per top-level result
        st.markdown("**Select the specific edition you are holding to autofill the form:**")
        edition_labels = {
            i: (
                f"{r.get('title', '—')}  |  "
                f"{r.get('publisher') or '—'}  |  "
                f"ISBN: {r.get('isbn') or '—'}  |  "
                f"{r.get('pub_year') or '—'}"
            )
            for i, r in enumerate(results)
        }
        chosen = st.selectbox(
            "Edition",
            options=list(edition_labels.keys()),
            format_func=lambda i: edition_labels[i],
            label_visibility="collapsed",
        )
        if st.button("Autofill from this edition", use_container_width=True):
            st.session_state["_prefill"] = results[chosen]
            st.session_state["_search_results"] = []
            st.experimental_rerun()

st.markdown("---")
st.subheader("Book Details")

col1, col2 = st.columns(2)
with col1:
    st.text_input("Title *", key="f_title")

    # Authors — contributor dropdown with manual fallback
    contributors = st.session_state.get("_contributors", [])
    author_opts = [_MANUAL] + contributors
    if st.session_state.get("f_author_select") not in author_opts:
        st.session_state["f_author_select"] = _MANUAL
    st.selectbox("Authors", author_opts, key="f_author_select")
    if st.session_state["f_author_select"] == _MANUAL:
        st.text_input("Type author name", key="f_authors")
        manual_name = st.session_state.get("f_authors", "").strip()
        if manual_name and manual_name not in st.session_state["_contributors"]:
            if st.button(f'Add "{manual_name}" to contributors list'):
                # Parse name into parts (last word = last name, rest = first name)
                parts = manual_name.rsplit(" ", 1)
                fname = parts[0] if len(parts) == 2 else manual_name
                lname = parts[1] if len(parts) == 2 else ""
                session = SessionLocal()
                try:
                    session.execute(
                        sqlalchemy.text(
                            "INSERT INTO contributors (c_name, fname, c_lname) "
                            "VALUES (:name, :fname, :lname)"
                        ),
                        {"name": manual_name, "fname": fname, "lname": lname},
                    )
                    session.commit()
                    # Refresh contributors list and switch dropdown to new name
                    rows = session.execute(
                        sqlalchemy.text(
                            "SELECT c_name FROM contributors ORDER BY c_lname, fname"
                        )
                    )
                    st.session_state["_contributors"] = [r[0] for r in rows if r[0]]
                    st.session_state["_set_author_select"] = manual_name
                    st.success(f'Added "{manual_name}" to contributors.')
                    st.experimental_rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Could not add contributor: {e}")
                finally:
                    session.close()

    st.text_input("ISBN", key="f_isbn")

    # Publisher — original_publishers dropdown with manual fallback
    publishers = st.session_state.get("_publishers", [])
    pub_opts = [_MANUAL] + publishers
    if st.session_state.get("f_publisher_select") not in pub_opts:
        st.session_state["f_publisher_select"] = _MANUAL
    st.selectbox("Publisher", pub_opts, key="f_publisher_select")
    if st.session_state["f_publisher_select"] == _MANUAL:
        st.text_input("Type publisher name", key="f_publisher")
        manual_pub = st.session_state.get("f_publisher", "").strip()
        if manual_pub and manual_pub not in st.session_state["_publishers"]:
            if st.button(f'Add "{manual_pub}" to publishers list'):
                session = SessionLocal()
                try:
                    session.execute(
                        sqlalchemy.text(
                            "INSERT INTO original_publishers (op_name) VALUES (:name)"
                        ),
                        {"name": manual_pub},
                    )
                    session.commit()
                    rows = session.execute(
                        sqlalchemy.text(
                            "SELECT op_name FROM original_publishers ORDER BY op_name"
                        )
                    )
                    st.session_state["_publishers"] = [r[0] for r in rows if r[0]]
                    st.session_state["_set_publisher_select"] = manual_pub
                    st.success(f'Added "{manual_pub}" to publishers.')
                    st.experimental_rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Could not add publisher: {e}")
                finally:
                    session.close()

    st.text_input("Publication Year", key="f_pub_year")

with col2:
    st.number_input("Pages", min_value=0, step=1, key="f_pages")
    st.text_input("Language", key="f_language")
    st.selectbox("Condition", ["New", "Good", "Fair", "Poor", "Damaged"], key="f_condition")
    st.selectbox("Priority", ["High", "Medium", "Low"], key="f_priority")
    st.selectbox("Owner", _OWNERS, key="f_owner")
    st.selectbox("Potential Imprint", _IMPRINTS, key="f_potential_imprint")
    st.checkbox("Scanned", key="f_scanned")

st.text_area("Description", key="f_description", height=80)
st.text_area("Notes", key="f_notes", height=80)

st.markdown("---")
if st.button("Save to Inventory", type="primary", use_container_width=True):
    title_val = st.session_state.f_title.strip()
    if not title_val:
        st.error("Title is required.")
    else:
        # Resolve authors and publisher
        if st.session_state.f_author_select == _MANUAL:
            authors_val = st.session_state.get("f_authors", "").strip() or None
        else:
            authors_val = st.session_state.f_author_select

        if st.session_state.f_publisher_select == _MANUAL:
            publisher_val = st.session_state.get("f_publisher", "").strip() or None
        else:
            publisher_val = st.session_state.f_publisher_select

        session = SessionLocal()
        try:
            new_book = Book(
                title=title_val,
                authors=authors_val,
                isbn=st.session_state.f_isbn.strip() or None,
                publisher=publisher_val,
                pub_year=st.session_state.f_pub_year.strip() or None,
                pages=int(st.session_state.f_pages) if st.session_state.f_pages else None,
                language=st.session_state.f_language.strip() or None,
                description=st.session_state.f_description.strip() or None,
                condition=st.session_state.f_condition,
                scanned=st.session_state.f_scanned,
                owner=st.session_state.f_owner,
                priority=st.session_state.f_priority,
                potential_imprint=st.session_state.f_potential_imprint or None,
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
