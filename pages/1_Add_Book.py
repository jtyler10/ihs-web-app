import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests as _requests
import sqlalchemy
import streamlit as st
from db import SessionLocal
from models import Book, Production
from search import (
    search_openlibrary_by_title,
    search_openlibrary_by_author,
    search_openlibrary_advanced,
    search_openlibrary_by_isbn,
    search_loc_by_title,
    search_loc_by_author,
    search_loc_by_isbn,
    search_loc_advanced,
    search_internet_archive,
    get_ia_pdfs,
)

st.set_page_config(page_title="Add Book — IHS Inventory", layout="centered")
st.title("Add Book to Inventory")

_MANUAL = "— Type name manually —"
_OWNERS = ["John Sharpe", "Jacob Hamm", "John Joyce", "Jonathan Tyler", "Aaron Carroll", "Acquisitions"]

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
            sqlalchemy.text("SELECT op_name, op_city FROM original_publishers ORDER BY op_name")
        )
        data = [(r[0], r[1] or "") for r in rows if r[0]]
        st.session_state["_publishers"] = [d[0] for d in data]
        st.session_state["_publisher_cities"] = {d[0]: d[1] for d in data}
    finally:
        session.close()

_DEFAULTS = {
    "f_title": "", "f_author_select": _MANUAL, "f_authors": "",
    "f_publisher_select": _MANUAL, "f_publisher": "", "f_publisher_city": "",
    "f_isbn": "", "f_pub_year": "", "f_pages": 0,
    "f_language": "", "f_description": "",
    "f_condition": "Good", "f_scanned": False, "f_owner": _OWNERS[0],
    "f_priority": "Medium", "f_potential_imprint": _IMPRINTS[0], "f_notes": "",
    "f_add_to_pipeline": False,
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
        st.session_state["f_publisher_city"] = st.session_state.get("_publisher_cities", {}).get(pub_match, "")
    else:
        st.session_state["f_publisher_select"] = _MANUAL
        st.session_state["f_publisher"] = prefill.get("publisher") or ""
        st.session_state["f_publisher_city"] = prefill.get("publish_place") or ""
    st.session_state["f_language"]    = prefill.get("language") or ""
    st.session_state["f_description"] = prefill.get("description") or ""
    if prefill.get("pages"):
        st.session_state["f_pages"] = int(prefill["pages"])
    # Try to match incoming author to a contributor name.
    # LoC returns MARC-style "Last, First" — also try the inverted form.
    def _invert_name(name):
        """'Penty, Arthur J.' → 'Arthur J. Penty'"""
        parts = name.split(",", 1)
        return (parts[1].strip() + " " + parts[0].strip()) if len(parts) == 2 else name

    incoming_raw = (prefill.get("authors") or "").strip()
    incoming_variants = {incoming_raw.lower(), _invert_name(incoming_raw).lower()}
    match = next(
        (c for c in st.session_state["_contributors"]
         if incoming_raw and any(
             v in c.lower() or c.lower() in v for v in incoming_variants
         )),
        None,
    )
    if match:
        st.session_state["f_author_select"] = match
    else:
        st.session_state["f_author_select"] = _MANUAL
        # Store the natural-order form so it's readable in the text input
        st.session_state["f_authors"] = _invert_name(incoming_raw) if incoming_raw else ""

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Catalog Search ────────────────────────────────────────────────────
with st.expander("Search catalogs to autofill", expanded=True):
    # Source selection
    src_col, _ = st.columns([2, 1])
    with src_col:
        selected_sources = st.multiselect(
            "Search in",
            options=["Open Library", "Library of Congress"],
            default=["Open Library"],
            key="s_sources",
        )
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
        for i in range(len(st.session_state.get("_search_results", []))):
            st.session_state.pop(f"chk_{i}", None)

        qt = st.session_state.get("s_title", "").strip()
        qa = st.session_state.get("s_author", "").strip()
        qi = st.session_state.get("s_isbn", "").strip()

        missing = False
        if s_type == "Title" and not qt:
            st.warning("Enter a title.")
            missing = True
        elif s_type == "Author" and not qa:
            st.warning("Enter an author.")
            missing = True
        elif s_type == "ISBN" and not qi:
            st.warning("Enter an ISBN.")
            missing = True
        elif s_type == "Title + Author" and not qt and not qa:
            st.warning("Enter a title and/or author.")
            missing = True

        if not missing:
            active = selected_sources
            if not active:
                st.warning("Select at least one search source.")
            else:
                with st.spinner(f"Searching {', '.join(active)}…"):
                    all_results = []
                    for source in active:
                        try:
                            if source == "Open Library":
                                if s_type == "Title":
                                    all_results += search_openlibrary_by_title(qt)
                                elif s_type == "Author":
                                    all_results += search_openlibrary_by_author(qa)
                                elif s_type == "ISBN":
                                    r = search_openlibrary_by_isbn(qi)
                                    if r:
                                        all_results.append(r)
                                else:
                                    all_results += search_openlibrary_advanced(title=qt, author=qa)

                            elif source == "Library of Congress":
                                if s_type == "Title":
                                    all_results += search_loc_by_title(qt)
                                elif s_type == "Author":
                                    all_results += search_loc_by_author(qa)
                                elif s_type == "ISBN":
                                    r = search_loc_by_isbn(qi)
                                    if r:
                                        all_results.append(r)
                                else:
                                    all_results += search_loc_advanced(title=qt, author=qa)

                        except Exception as src_err:
                            st.warning(f"{source} search failed: {src_err}")

                    st.session_state["_search_results"] = all_results
                    if not all_results:
                        st.info("No results found. Fill in the form below manually.")

    # ── Results: reference table + edition picker ─────────────────────
    if st.session_state["_search_results"]:
        import pandas as pd

        results = st.session_state["_search_results"]

        rows = []
        for r in results:
            isbns = r.get("all_isbns") or ([r["isbn"]] if r.get("isbn") else ["—"])
            pubs  = r.get("all_publishers") or ([r["publisher"]] if r.get("publisher") else ["—"])
            for isbn in (isbns or ["—"]):
                for pub in (pubs or ["—"]):
                    rows.append({
                        "Source":    r.get("source") or "—",
                        "Title":     r.get("title") or "—",
                        "Authors":   r.get("authors") or "—",
                        "Year":      r.get("pub_year") or "—",
                        "Publisher": pub or "—",
                        "ISBN":      isbn or "—",
                    })

        ref_df = pd.DataFrame(rows)
        st.markdown("**All editions found — use as reference:**")
        st.dataframe(ref_df, use_container_width=True)

        st.markdown("**Select the specific edition you are holding to autofill the form:**")
        edition_labels = {
            i: (
                f"[{r.get('source', '—')}]  "
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
            st.rerun()

# ── Internet Archive PDF search ───────────────────────────────────────
with st.expander("Search Internet Archive for PDF", expanded=False):
    # Resolve current title/author from form state
    _ia_title = st.session_state.get("f_title", "").strip()
    _ia_author_sel = st.session_state.get("f_author_select", "")
    _ia_author = (
        _ia_author_sel if _ia_author_sel and _ia_author_sel != _MANUAL
        else st.session_state.get("f_authors", "")
    ).strip()

    if _ia_title or _ia_author:
        st.caption(
            f"Searching for: **{_ia_title or '(no title)'}**"
            + (f" by {_ia_author}" if _ia_author else "")
        )
    else:
        st.info("Fill in the Title and/or Author fields below first, then come back here.")

    if st.button("Search Internet Archive", use_container_width=True, key="ia_search_btn"):
        if not _ia_title and not _ia_author:
            st.warning("Enter a title or author in the form below first.")
        else:
            with st.spinner("Searching Internet Archive…"):
                try:
                    st.session_state["_ia_results"] = search_internet_archive(
                        title=_ia_title or None,
                        author=_ia_author or None,
                        limit=8,
                    )
                    for k in list(st.session_state):
                        if k.startswith(("_ia_pdfs_", "_ia_bytes_")):
                            del st.session_state[k]
                except Exception as e:
                    st.error(f"Search error: {e}")
                    st.session_state["_ia_results"] = []

    ia_results = st.session_state.get("_ia_results")
    if ia_results is not None:
        if not ia_results:
            st.info("No freely downloadable PDFs found on Internet Archive for this title.")
        for item in ia_results:
            iid = item["identifier"]
            st.markdown(f"**{item['title']}**  —  {item['creator']}  ({item['year']})")
            pdf_key   = f"_ia_pdfs_{iid}"
            col_link, col_btn = st.columns([1, 1])
            with col_link:
                st.markdown(
                    f'<a href="{item["ia_url"]}" target="_blank">View on Archive.org ↗</a>',
                    unsafe_allow_html=True,
                )
            with col_btn:
                if pdf_key not in st.session_state:
                    if st.button("Get PDFs", key=f"ia_get_{iid}"):
                        with st.spinner("Fetching file list…"):
                            try:
                                st.session_state[pdf_key] = get_ia_pdfs(iid)
                            except Exception as e:
                                st.error(f"Could not fetch files: {e}")
                                st.session_state[pdf_key] = []
                        st.rerun()
            if pdf_key in st.session_state:
                pdfs = st.session_state[pdf_key]
                if not pdfs:
                    st.caption("  No PDF files found for this item.")
                for pdf in pdfs:
                    bytes_key = f"_ia_bytes_{iid}_{pdf['name']}"
                    fc, bc = st.columns([3, 2])
                    with fc:
                        st.caption(f"  {pdf['name']}  ({pdf['size_mb']} MB)")
                    with bc:
                        if bytes_key in st.session_state:
                            st.download_button(
                                "⬇ Save PDF",
                                data=st.session_state[bytes_key],
                                file_name=pdf["name"],
                                mime="application/pdf",
                                key=f"ia_save_{iid}_{pdf['name']}",
                                use_container_width=True,
                            )
                        else:
                            err_key = f"_ia_err_{iid}_{pdf['name']}"
                            if st.session_state.get(err_key):
                                st.error(st.session_state.pop(err_key))
                            if st.button(
                                "⬇ Download",
                                key=f"ia_dl_{iid}_{pdf['name']}",
                                use_container_width=True,
                            ):
                                with st.spinner(f"Downloading {pdf['size_mb']} MB…"):
                                    try:
                                        r = _requests.get(pdf["url"], timeout=300, allow_redirects=True)
                                        r.raise_for_status()
                                        st.session_state[bytes_key] = r.content
                                        st.rerun()
                                    except _requests.exceptions.HTTPError as e:
                                        if e.response is not None and e.response.status_code == 401:
                                            st.session_state[err_key] = (
                                                "This file requires an Internet Archive account. "
                                                f"Download it directly at: {item['ia_url']}"
                                            )
                                        else:
                                            st.session_state[err_key] = f"Download failed: {e}"
                                        st.rerun()
                                    except Exception as e:
                                        st.session_state[err_key] = f"Download failed: {e}"
                                        st.rerun()
            st.markdown("---")

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
                            "INSERT INTO contributors (c_name, fname, c_lname, short_bio) "
                            "VALUES (:name, :fname, :lname, '')"
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
                    st.rerun()
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

    def _on_pub_change():
        sel = st.session_state.get("f_publisher_select")
        if sel and sel != _MANUAL:
            st.session_state["f_publisher_city"] = st.session_state.get("_publisher_cities", {}).get(sel, "")

    st.selectbox("Publisher", pub_opts, key="f_publisher_select", on_change=_on_pub_change)
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
                            "SELECT op_name, op_city FROM original_publishers ORDER BY op_name"
                        )
                    )
                    data = [(r[0], r[1] or "") for r in rows if r[0]]
                    st.session_state["_publishers"] = [d[0] for d in data]
                    st.session_state["_publisher_cities"] = {d[0]: d[1] for d in data}
                    st.session_state["_set_publisher_select"] = manual_pub
                    st.success(f'Added "{manual_pub}" to publishers.')
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Could not add publisher: {e}")
                finally:
                    session.close()

    st.text_input("Publisher City", key="f_publisher_city")
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
st.checkbox("Add to Production Pipeline", key="f_add_to_pipeline")

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

        # Determine pipeline stage
        if st.session_state.f_owner == "Acquisitions":
            pipeline_stage = "Acquisitions"
        elif st.session_state.f_scanned:
            pipeline_stage = "Transcription"
        else:
            pipeline_stage = "In Hand"

        session = SessionLocal()
        try:
            new_book = Book(
                title=title_val,
                authors=authors_val,
                isbn=st.session_state.f_isbn.strip() or None,
                publisher=publisher_val,
                publisher_city=st.session_state.f_publisher_city.strip() or None,
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
            session.flush()  # get new_book.id before commit

            if st.session_state.f_add_to_pipeline:
                session.add(Production(
                    book_id=new_book.id,
                    stage=pipeline_stage,
                ))

            session.commit()
            pipeline_msg = f" → added to pipeline at **{pipeline_stage}**" if st.session_state.f_add_to_pipeline else ""
            st.success(f"Saved **{new_book.title}**{pipeline_msg}")
            st.session_state["_do_clear"] = True
            st.rerun()
        except Exception as e:
            session.rollback()
            st.error(f"Error saving: {e}")
        finally:
            session.close()
