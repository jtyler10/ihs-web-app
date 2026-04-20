import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
import streamlit as st
import pandas as pd
from db import SessionLocal
from models import Book

# ── Constants (mirrors Add Book page) ────────────────────────────────
_MANUAL  = "— Type name manually —"
_OWNERS  = ["John Sharpe", "Jacob Hamm", "John Joyce", "Jonathan Tyler", "Aaron Carroll", "Acquisitions"]
_IMPRINTS = [
    "",
    "IHS Press", "Nota Tomus Gregoriana", "HarperCollins",
    "American Chesterton Society", "Liberty Fund",
    "Light in the Darkness Publications", "Family Publications",
    "Louisiana State University Press", "Gates of Vienna Books",
    "Australian Heritage Society", "Catholic Central Verein of America",
    "Enigma Editions", "Forgotten Voices Editions", "Freedom Publishing",
    "Intercollegiate Studies Institute", "Sapientia Press", "Tradibooks",
    "Traditionalist Press", "Transaction Publishers",
    "University of Chicago Press", "University of Notre Dame Press",
    "The Schoolman Bookshelf",
]

# ── Session state init ────────────────────────────────────────────────
for key, val in [
    ("delete_pending_id", None),
    ("_editing_id", None),
    ("_inv_page", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── Load contributors & publishers once ──────────────────────────────
if "_contributors" not in st.session_state:
    _s = SessionLocal()
    try:
        _r = _s.execute(sqlalchemy.text("SELECT c_name FROM contributors ORDER BY c_lname, fname"))
        st.session_state["_contributors"] = [r[0] for r in _r if r[0]]
    finally:
        _s.close()

if "_publishers" not in st.session_state:
    _s = SessionLocal()
    try:
        _r = _s.execute(sqlalchemy.text("SELECT op_name, op_city FROM original_publishers ORDER BY op_name"))
        data = [(r[0], r[1] or "") for r in _r if r[0]]
        st.session_state["_publishers"] = [d[0] for d in data]
        st.session_state["_publisher_cities"] = {d[0]: d[1] for d in data}
    finally:
        _s.close()

# ── Deferred pre-render operations ───────────────────────────────────
load_id = st.session_state.pop("_load_edit_id", None)
if load_id:
    _s = SessionLocal()
    try:
        b = _s.query(Book).filter(Book.id == load_id).first()
        if b:
            st.session_state["_editing_id"]         = b.id
            st.session_state["e_title"]             = b.title or ""
            st.session_state["e_isbn"]              = b.isbn or ""
            st.session_state["e_pub_year"]          = b.pub_year or ""
            st.session_state["e_pages"]             = b.pages or 0
            st.session_state["e_language"]          = b.language or ""
            st.session_state["e_description"]       = b.description or ""
            st.session_state["e_notes"]             = b.notes or ""
            st.session_state["e_condition"]         = b.condition or "Good"
            st.session_state["e_scanned"]           = bool(b.scanned)
            st.session_state["e_owner"]             = b.owner if b.owner in _OWNERS else _OWNERS[0]
            st.session_state["e_priority"]          = b.priority or "Medium"
            st.session_state["e_potential_imprint"] = b.potential_imprint if b.potential_imprint in _IMPRINTS else ""
            if b.authors in st.session_state["_contributors"]:
                st.session_state["e_author_select"] = b.authors
            else:
                st.session_state["e_author_select"] = _MANUAL
                st.session_state["e_authors"]       = b.authors or ""
            if b.publisher in st.session_state["_publishers"]:
                st.session_state["e_publisher_select"] = b.publisher
                st.session_state["e_publisher_city"]   = st.session_state.get("_publisher_cities", {}).get(b.publisher, b.publisher_city or "")
            else:
                st.session_state["e_publisher_select"] = _MANUAL
                st.session_state["e_publisher"]        = b.publisher or ""
                st.session_state["e_publisher_city"]   = b.publisher_city or ""
    finally:
        _s.close()

new_ea = st.session_state.pop("_set_edit_author_select", None)
if new_ea:
    st.session_state["e_author_select"] = new_ea

new_ep = st.session_state.pop("_set_edit_publisher_select", None)
if new_ep:
    st.session_state["e_publisher_select"] = new_ep

# ── Page ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Inventory — IHS", layout="wide")
st.title("Inventory Overview")

session = SessionLocal()
try:
    books = session.query(Book).order_by(Book.created_at.desc()).all()
finally:
    session.close()

if not books:
    st.info("No books in inventory yet. Use **Add Book** in the sidebar to get started.")
    st.stop()

df = pd.DataFrame([{
    "ID": b.id,
    "Title": b.title,
    "Authors": b.authors or "",
    "ISBN": b.isbn or "",
    "Publisher": b.publisher or "",
    "Publisher City": b.publisher_city or "",
    "Year": b.pub_year or "",
    "Condition": b.condition or "",
    "Scanned": bool(b.scanned),
    "Owner": b.owner or "",
    "Priority": b.priority or "",
    "Potential Imprint": b.potential_imprint or "",
    "Notes": b.notes or "",
    "Added": b.created_at.strftime("%Y-%m-%d") if b.created_at else "",
} for b in books])

# ── Filters ───────────────────────────────────────────────────────────
with st.expander("Filters", expanded=True):
    f1, f2, f3 = st.columns(3)
    with f1:
        search_text = st.text_input("Search title / author / ISBN", placeholder="Type to filter…")
    with f2:
        cond_opts = ["All"] + sorted(c for c in df["Condition"].unique() if c)
        condition_filter = st.selectbox("Condition", cond_opts)
    with f3:
        scanned_filter = st.selectbox("Scanned", ["All", "Yes", "No"])
    f4, f5, _ = st.columns(3)
    with f4:
        owner_opts = ["All"] + sorted(o for o in df["Owner"].unique() if o)
        owner_filter = st.selectbox("Owner", owner_opts)
    with f5:
        priority_filter = st.selectbox("Priority", ["All", "High", "Medium", "Low"])

filtered = df.copy()
if search_text.strip():
    q = search_text.strip()
    mask = (
        filtered["Title"].str.contains(q, case=False, na=False)
        | filtered["Authors"].str.contains(q, case=False, na=False)
        | filtered["ISBN"].str.contains(q, case=False, na=False)
    )
    filtered = filtered[mask]
if condition_filter != "All":
    filtered = filtered[filtered["Condition"] == condition_filter]
if scanned_filter == "Yes":
    filtered = filtered[filtered["Scanned"]]
elif scanned_filter == "No":
    filtered = filtered[~filtered["Scanned"]]
if owner_filter != "All":
    filtered = filtered[filtered["Owner"] == owner_filter]
if priority_filter != "All":
    filtered = filtered[filtered["Priority"] == priority_filter]

st.markdown("""
<style>
[data-testid="stHorizontalBlock"] .stButton button {
    display: flex;
    align-items: center;
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"**{len(filtered)}** of **{len(df)}** books")

# ── Helpers ───────────────────────────────────────────────────────────
def _trunc(s, n):
    s = str(s) if s else "—"
    return s if len(s) <= n else s[:n - 1] + "…"

_W = [4, 2.5, 1.5, 1, 1.5, 1.5, 0.45, 0.45]
PAGE_SIZE = 25

# ── Table / Cover Gallery tabs ────────────────────────────────────────
tab_table, tab_covers = st.tabs(["Table", "Cover Gallery"])

with tab_table:
    # Clamp page if filtered set shrank
    n_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
    if st.session_state["_inv_page"] >= n_pages:
        st.session_state["_inv_page"] = 0
    page = st.session_state["_inv_page"]
    page_df = filtered.iloc[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    # Header row
    hcols = st.columns(_W)
    for col, label in zip(hcols, ["Title", "Authors", "ISBN", "Year", "Owner", "Condition", "", ""]):
        col.markdown(f"**{label}**")
    st.divider()

    # Data rows
    for _, row in page_df.iterrows():
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(_W)
        c1.write(_trunc(row["Title"], 45))
        c2.write(_trunc(row["Authors"], 30))
        c3.write(row["ISBN"] or "—")
        c4.write(row["Year"] or "—")
        c5.write(row["Owner"] or "—")
        c6.write(row["Condition"] or "—")
        if c7.button("✏️", key=f"edit_{row['ID']}", help="Edit", use_container_width=True):
            st.session_state["_load_edit_id"] = row["ID"]
            st.rerun()
        if c8.button("🗑️", key=f"del_{row['ID']}", help="Delete", use_container_width=True):
            st.session_state["delete_pending_id"] = row["ID"]
            st.rerun()

    # Pagination controls
    if n_pages > 1:
        pc1, pc2, pc3 = st.columns([1, 3, 1])
        with pc1:
            if page > 0 and st.button("← Prev", use_container_width=True):
                st.session_state["_inv_page"] = page - 1
                st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center;padding-top:6px'>Page {page + 1} of {n_pages}</div>",
                unsafe_allow_html=True,
            )
        with pc3:
            if page < n_pages - 1 and st.button("Next →", use_container_width=True):
                st.session_state["_inv_page"] = page + 1
                st.rerun()

    st.markdown("---")
    csv = filtered.to_csv(index=False)
    st.download_button("Download as CSV", data=csv, file_name="ihs_inventory.csv", mime="text/csv")

with tab_covers:
    COLS = 4
    COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
    PLACEHOLDER = "https://via.placeholder.com/128x192.png?text=No+Cover"
    cover_rows = [filtered.iloc[i:i+COLS] for i in range(0, len(filtered), COLS)]
    for cover_row in cover_rows:
        cols = st.columns(COLS)
        for col, (_, book) in zip(cols, cover_row.iterrows()):
            with col:
                isbn = book["ISBN"].strip()
                img_url = COVER_URL.format(isbn=isbn) if isbn else PLACEHOLDER
                st.image(img_url, width=128)
                title_display = book["Title"] if len(book["Title"]) <= 40 else book["Title"][:37] + "…"
                authors_display = book["Authors"] if len(book["Authors"]) <= 35 else book["Authors"][:32] + "…"
                st.markdown(
                    f"**{title_display}**  \n"
                    f"<span style='font-size:0.8em;color:gray;'>{authors_display or '—'}</span>  \n"
                    f"<span style='font-size:0.8em;color:gray;'>ISBN: {isbn or '—'}</span>",
                    unsafe_allow_html=True,
                )

# ── Edit form (triggered by ✏️) ───────────────────────────────────────
if st.session_state["_editing_id"] is not None:
    eid = st.session_state["_editing_id"]
    st.markdown("---")
    st.subheader(f"Editing — {st.session_state.get('e_title', '') or f'id={eid}'}")

    ec1, ec2 = st.columns(2)
    with ec1:
        st.text_input("Title *", key="e_title")

        contrib_opts = [_MANUAL] + st.session_state["_contributors"]
        if st.session_state.get("e_author_select") not in contrib_opts:
            st.session_state["e_author_select"] = _MANUAL
        st.selectbox("Authors", contrib_opts, key="e_author_select")
        if st.session_state["e_author_select"] == _MANUAL:
            st.text_input("Type author name", key="e_authors")
            e_manual_author = st.session_state.get("e_authors", "").strip()
            if e_manual_author and e_manual_author not in st.session_state["_contributors"]:
                if st.button(f'Add "{e_manual_author}" to contributors', key="e_add_contrib"):
                    parts = e_manual_author.rsplit(" ", 1)
                    fname = parts[0] if len(parts) == 2 else e_manual_author
                    lname = parts[1] if len(parts) == 2 else ""
                    _s = SessionLocal()
                    try:
                        _s.execute(
                            sqlalchemy.text("INSERT INTO contributors (c_name, fname, c_lname, short_bio) VALUES (:n, :f, :l, '')"),
                            {"n": e_manual_author, "f": fname, "l": lname},
                        )
                        _s.commit()
                        _r = _s.execute(sqlalchemy.text("SELECT c_name FROM contributors ORDER BY c_lname, fname"))
                        st.session_state["_contributors"] = [r[0] for r in _r if r[0]]
                        st.session_state["_set_edit_author_select"] = e_manual_author
                        st.rerun()
                    except Exception as e:
                        _s.rollback()
                        st.error(f"Could not add contributor: {e}")
                    finally:
                        _s.close()

        st.text_input("ISBN", key="e_isbn")

        pub_opts = [_MANUAL] + st.session_state["_publishers"]
        if st.session_state.get("e_publisher_select") not in pub_opts:
            st.session_state["e_publisher_select"] = _MANUAL

        def _on_edit_pub_change():
            sel = st.session_state.get("e_publisher_select")
            if sel and sel != _MANUAL:
                st.session_state["e_publisher_city"] = st.session_state.get("_publisher_cities", {}).get(sel, "")

        st.selectbox("Publisher", pub_opts, key="e_publisher_select", on_change=_on_edit_pub_change)
        if st.session_state["e_publisher_select"] == _MANUAL:
            st.text_input("Type publisher name", key="e_publisher")
            e_manual_pub = st.session_state.get("e_publisher", "").strip()
            if e_manual_pub and e_manual_pub not in st.session_state["_publishers"]:
                if st.button(f'Add "{e_manual_pub}" to publishers', key="e_add_pub"):
                    _s = SessionLocal()
                    try:
                        _s.execute(
                            sqlalchemy.text("INSERT INTO original_publishers (op_name) VALUES (:n)"),
                            {"n": e_manual_pub},
                        )
                        _s.commit()
                        _r = _s.execute(sqlalchemy.text("SELECT op_name, op_city FROM original_publishers ORDER BY op_name"))
                        data = [(r[0], r[1] or "") for r in _r if r[0]]
                        st.session_state["_publishers"] = [d[0] for d in data]
                        st.session_state["_publisher_cities"] = {d[0]: d[1] for d in data}
                        st.session_state["_set_edit_publisher_select"] = e_manual_pub
                        st.rerun()
                    except Exception as e:
                        _s.rollback()
                        st.error(f"Could not add publisher: {e}")
                    finally:
                        _s.close()

        st.text_input("Publisher City", key="e_publisher_city")
        st.text_input("Publication Year", key="e_pub_year")

    with ec2:
        st.number_input("Pages", min_value=0, step=1, key="e_pages")
        st.text_input("Language", key="e_language")
        st.selectbox("Condition", ["New", "Good", "Fair", "Poor", "Damaged"], key="e_condition")
        st.selectbox("Priority", ["High", "Medium", "Low"], key="e_priority")
        st.selectbox("Owner", _OWNERS, key="e_owner")
        st.selectbox("Potential Imprint", _IMPRINTS, key="e_potential_imprint")
        st.checkbox("Scanned", key="e_scanned")

    st.text_area("Description", key="e_description", height=80)
    st.text_area("Notes", key="e_notes", height=80)

    st.markdown("---")
    sv1, sv2 = st.columns(2)
    with sv1:
        if st.button("Save Changes", type="primary", use_container_width=True):
            e_title = st.session_state.e_title.strip()
            if not e_title:
                st.error("Title is required.")
            else:
                if st.session_state.e_author_select == _MANUAL:
                    e_authors = st.session_state.get("e_authors", "").strip() or None
                else:
                    e_authors = st.session_state.e_author_select

                if st.session_state.e_publisher_select == _MANUAL:
                    e_publisher = st.session_state.get("e_publisher", "").strip() or None
                else:
                    e_publisher = st.session_state.e_publisher_select

                _s = SessionLocal()
                try:
                    b = _s.query(Book).filter(Book.id == eid).first()
                    if b:
                        b.title             = e_title
                        b.authors           = e_authors
                        b.isbn              = st.session_state.e_isbn.strip() or None
                        b.publisher         = e_publisher
                        b.publisher_city    = st.session_state.e_publisher_city.strip() or None
                        b.pub_year          = st.session_state.e_pub_year.strip() or None
                        b.pages             = int(st.session_state.e_pages) if st.session_state.e_pages else None
                        b.language          = st.session_state.e_language.strip() or None
                        b.description       = st.session_state.e_description.strip() or None
                        b.condition         = st.session_state.e_condition
                        b.scanned           = st.session_state.e_scanned
                        b.owner             = st.session_state.e_owner
                        b.priority          = st.session_state.e_priority
                        b.potential_imprint = st.session_state.e_potential_imprint or None
                        b.notes             = st.session_state.e_notes.strip() or None
                        _s.commit()
                        st.success(f"Updated **{b.title}** (id={eid})")
                        st.session_state["_editing_id"] = None
                        st.rerun()
                except Exception as e:
                    _s.rollback()
                    st.error(f"Error saving: {e}")
                finally:
                    _s.close()
    with sv2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["_editing_id"] = None
            st.rerun()

# ── Delete confirmation (triggered by 🗑️) ─────────────────────────────
if st.session_state["delete_pending_id"] is not None:
    del_id = st.session_state["delete_pending_id"]
    del_row = df[df["ID"] == del_id]
    if del_row.empty:
        st.session_state["delete_pending_id"] = None
        st.rerun()
    del_title = del_row["Title"].values[0]
    st.markdown("---")
    st.warning(
        f"Are you sure you want to permanently remove **{del_title}**? "
        "This cannot be undone."
    )
    d1, d2 = st.columns(2)
    with d1:
        if st.button("Yes, remove it", type="primary", use_container_width=True):
            _s = SessionLocal()
            try:
                b = _s.query(Book).filter(Book.id == del_id).first()
                if b:
                    _s.delete(b)
                    _s.commit()
                    st.success(f"Removed **{b.title}** from inventory.")
                st.session_state["delete_pending_id"] = None
                st.rerun()
            except Exception as e:
                _s.rollback()
                st.error(f"Error removing book: {e}")
            finally:
                _s.close()
    with d2:
        if st.button("Cancel", key="del_cancel", use_container_width=True):
            st.session_state["delete_pending_id"] = None
            st.rerun()
