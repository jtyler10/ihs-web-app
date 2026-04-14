import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from db import SessionLocal
from models import Book

if "delete_pending_id" not in st.session_state:
    st.session_state["delete_pending_id"] = None

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
    "Year": b.pub_year or "",
    "Condition": b.condition or "",
    "Scanned": bool(b.scanned),
    "Owner": b.owner or "",
    "Priority": b.priority or "",
    "Potential Imprint": b.potential_imprint or "",
    "Notes": b.notes or "",
    "Added": b.created_at.strftime("%Y-%m-%d") if b.created_at else "",
} for b in books])

# ── Filters ──────────────────────────────────────────────────────────
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

st.markdown(f"**{len(filtered)}** of **{len(df)}** books")

# ── Table / Cover Gallery tabs ────────────────────────────────────────
tab_table, tab_covers = st.tabs(["Table", "Cover Gallery"])

with tab_table:
    st.dataframe(filtered, use_container_width=True)
    csv = filtered.to_csv(index=False)
    st.download_button("Download as CSV", data=csv, file_name="ihs_inventory.csv", mime="text/csv")

with tab_covers:
    COLS = 4
    COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
    PLACEHOLDER = "https://via.placeholder.com/128x192.png?text=No+Cover"

    rows = [filtered.iloc[i:i+COLS] for i in range(0, len(filtered), COLS)]
    for row in rows:
        cols = st.columns(COLS)
        for col, (_, book) in zip(cols, row.iterrows()):
            with col:
                isbn = book["ISBN"].strip()
                img_url = COVER_URL.format(isbn=isbn) if isbn else PLACEHOLDER
                st.image(img_url, width=128)
                title = book["Title"]
                title_display = title if len(title) <= 40 else title[:37] + "…"
                authors = book["Authors"]
                authors_display = authors if len(authors) <= 35 else authors[:32] + "…"
                st.markdown(
                    f"**{title_display}**  \n"
                    f"<span style='font-size:0.8em;color:gray;'>{authors_display or '—'}</span>  \n"
                    f"<span style='font-size:0.8em;color:gray;'>ISBN: {isbn or '—'}</span>",
                    unsafe_allow_html=True,
                )

# ── Remove a Book ─────────────────────────────────────────────────────
st.markdown("---")
with st.expander("Remove a Book from Inventory"):
    if filtered.empty:
        st.info("No books match the current filters.")
    else:
        options = {
            row["ID"]: f"[id={row['ID']}]  {row['Title']}  —  {row['Authors'] or '—'}"
            for _, row in filtered.iterrows()
        }
        selected_id = st.selectbox(
            "Select book to remove",
            options=list(options.keys()),
            format_func=lambda i: options[i],
        )

        selected_label = options[selected_id]

        if st.session_state["delete_pending_id"] != selected_id:
            # Reset confirmation if a different book is chosen
            if st.button("Remove this book", use_container_width=True):
                st.session_state["delete_pending_id"] = selected_id
                st.experimental_rerun()
        else:
            st.warning(
                f"Are you sure you want to permanently remove **{filtered.loc[filtered['ID'] == selected_id, 'Title'].values[0]}**? "
                "This cannot be undone."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, remove it", type="primary", use_container_width=True):
                    session = SessionLocal()
                    try:
                        book = session.query(Book).filter(Book.id == selected_id).first()
                        if book:
                            session.delete(book)
                            session.commit()
                            st.success(f"Removed **{book.title}** from inventory.")
                        st.session_state["delete_pending_id"] = None
                        st.experimental_rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Error removing book: {e}")
                    finally:
                        session.close()
            with c2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["delete_pending_id"] = None
                    st.experimental_rerun()
