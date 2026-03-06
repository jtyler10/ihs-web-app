import os
import streamlit as st
from sqlalchemy.exc import IntegrityError
from db import SessionLocal, engine, Base
from models import Book
from search import search_openlibrary_by_title

# only create tables when ALLOW_CREATE_TABLES=1 is set (development only)
if os.getenv("ALLOW_CREATE_TABLES") == "1":
    Base.metadata.create_all(bind=engine)

st.set_page_config(page_title="IHS Inventory Intake", layout="centered")

st.title("IHS — Book intake form")

with st.sidebar:
    st.markdown("## DB / App info")
    st.write("Database URL (masked):", "Yes" if os.getenv("DATABASE_URL") else "Not set")
    st.markdown("---")
    st.markdown("Search options")
    use_openlibrary = st.checkbox("Enable Open Library search", value=True)
    show_z3950 = st.checkbox("Show Z39.50 notes", value=False)

if show_z3950:
    st.info(
        "Z39.50 is an older library protocol. Consider SRU or APIs (Open Library, WorldCat) instead. "
        "See README for details."
    )

# Form for manual entry
st.header("Enter book information")
with st.form("book_form"):
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input("Title", key="title")
        authors = st.text_input("Authors (comma-separated)", key="authors")
        isbn = st.text_input("ISBN", key="isbn")
        publisher = st.text_input("Publisher", key="publisher")
    with col2:
        pub_year = st.text_input("Publication year", key="pub_year")
        pages = st.number_input("Pages", min_value=0, step=1, format="%d", key="pages")
        language = st.text_input("Language", key="language")
        description = st.text_area("Description", key="description")
    submit = st.form_submit_button("Save to database")

# Search / prefill from external source
st.header("Search external catalog (Open Library)")
if use_openlibrary:
    query = st.text_input("Search title", key="ol_query")
    if st.button("Search Open Library"):
        if not query:
            st.warning("Enter a title to search.")
        else:
            with st.spinner("Searching Open Library..."):
                results = search_openlibrary_by_title(query)
            if not results:
                st.info("No results from Open Library.")
            else:
                titles = [f"{r.get('title')} — {r.get('authors') or ''} — {r.get('pub_year') or ''}" for r in results]
                choice = st.radio("Choose match to prefill", options=list(range(len(results))), format_func=lambda i: titles[i])
                selected = results[int(choice)]
                st.success("Prefilled from Open Library (choose Save to write to DB).")
                st.json(selected)

                if st.button("Copy selected to form fields"):
                    st.session_state["title"] = selected.get("title") or st.session_state.get("title", "")
                    st.session_state["authors"] = selected.get("authors") or st.session_state.get("authors", "")
                    st.session_state["isbn"] = selected.get("isbn") or st.session_state.get("isbn", "")
                    st.session_state["publisher"] = selected.get("publisher") or st.session_state.get("publisher", "")
                    st.session_state["pub_year"] = selected.get("pub_year") or st.session_state.get("pub_year", "")
                    st.experimental_rerun()

# Duplicate check
st.header("Check database for existing record")
check_isbn = st.text_input("Check by ISBN", key="check_isbn")
if st.button("Check DB"):
    if check_isbn:
        session = SessionLocal()
        try:
            existing = session.query(Book).filter(Book.isbn == check_isbn).all()
            if existing:
                st.warning(f"Found {len(existing)} record(s) with ISBN {check_isbn}:")
                for b in existing:
                    st.write(dict(
                        id=b.id, title=b.title, authors=b.authors, isbn=b.isbn,
                        publisher=b.publisher, pub_year=b.pub_year, created_at=b.created_at
                    ))
            else:
                st.success("No records with that ISBN.")
        finally:
            session.close()
    else:
        st.warning("Enter an ISBN to check.")

# Save logic
if submit or st.button("Save current form to DB"):
    title_val = st.session_state.get("title", title)
    authors_val = st.session_state.get("authors", authors)
    isbn_val = st.session_state.get("isbn", isbn)
    publisher_val = st.session_state.get("publisher", publisher)
    pub_year_val = st.session_state.get("pub_year", pub_year)
    pages_val = int(st.session_state.get("pages", pages)) if pages else None
    language_val = st.session_state.get("language", language)
    description_val = st.session_state.get("description", description)

    if not title_val:
        st.error("Title is required.")
    else:
        session = SessionLocal()
        try:
            # Simple duplicate check by ISBN
            if isbn_val:
                already = session.query(Book).filter(Book.isbn == isbn_val).first()
                if already:
                    st.warning("A book with that ISBN already exists in the DB:")
                    st.write(dict(
                        id=already.id, title=already.title, authors=already.authors, isbn=already.isbn,
                        publisher=already.publisher, pub_year=already.pub_year
                    ))
                    if not st.checkbox("Force insert duplicate ISBN"):
                        st.stop()

            new_book = Book(
                title=title_val,
                authors=authors_val,
                isbn=isbn_val,
                publisher=publisher_val,
                pub_year=pub_year_val,
                pages=pages_val or None,
                language=language_val,
                description=description_val,
                source="web-form"
            )
            session.add(new_book)
            session.commit()
            st.success(f"Saved book (id={new_book.id}).")
        except IntegrityError as e:
            session.rollback()
            st.error("Unable to insert (possible duplicate key). Error: " + str(e.orig))
        except Exception as e:
            session.rollback()
            st.error("Unexpected error: " + str(e))
        finally:
            session.close()