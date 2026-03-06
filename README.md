# ihs-web-app — Streamlit intake starter

This is a small Streamlit starter to intake book metadata and store into a MySQL database.

Quick start
1. Create a Python virtualenv and install requirements:
   pip install -r requirements.txt

2. Set DB credentials via environment variables. Preferred:
   export DATABASE_URL="mysql+pymysql://user:pass@host/dbname?charset=utf8mb4"

   Or set DB_USER, DB_PASS, DB_HOST, DB_NAME.

3. Run:
   streamlit run streamlit_app.py

What this does
- Presents a form to create a book record.
- Checks for duplicates by ISBN.
- Offers Open Library search to prefill fields (no API key).
- Saves to your MySQL DB using SQLAlchemy.

Integrating with your existing DB
- The SQLAlchemy model in `models.py` is a suggestion. If your DB already has a `books` table, adjust columns and types to match. If you want help mapping your current schema, paste the CREATE TABLE statement or a table dump and I will adapt models/queries.

Z39.50 / catalog searching
- Z39.50 is an older library protocol. For modern, open options, consider:
  - Open Library APIs (used in the example)
  - SRU/SRW endpoints (HTTP-based search protocol used by some libraries)
  - WorldCat Search API (requires OCLC credentials)
  - Google Books API (requires API key)
- If you must query Z39.50 endpoints, see `search.py` for a brief example using `PyZ3950` and `pymarc`. Z39.50 often returns MARC records that you then parse to extract title/author/isbn.

Next steps
- Share your production CREATE TABLE (books) SQL and I’ll adapt models.py to match exactly.
- Optionally I can add Alembic migrations, authentication, or containerized app service.