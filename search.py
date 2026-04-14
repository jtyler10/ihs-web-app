import re
import requests


def search_openlibrary_by_title(title, limit=5):
    """Search Open Library by title. Returns a list of simplified book dicts."""
    resp = requests.get(
        "https://openlibrary.org/search.json",
        params={"title": title, "limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    results = []
    for d in resp.json().get("docs", []):
        results.append({
            "title": d.get("title"),
            "authors": ", ".join(d.get("author_name", [])) or None,
            "isbn": d.get("isbn", [None])[0] if d.get("isbn") else None,
            "publisher": ", ".join(d.get("publisher", [])) if d.get("publisher") else None,
            "pub_year": str(d["first_publish_year"]) if d.get("first_publish_year") else None,
            "pages": d.get("number_of_pages_median"),
            "language": ", ".join(d.get("language", [])) if d.get("language") else None,
        })
    return results


def search_openlibrary_by_isbn(isbn):
    """Look up a single book by ISBN using the Open Library Books API.
    Returns a dict or None if not found."""
    isbn_clean = isbn.replace("-", "").replace(" ", "")
    resp = requests.get(
        "https://openlibrary.org/api/books",
        params={"bibkeys": f"ISBN:{isbn_clean}", "format": "json", "jscmd": "data"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    key = f"ISBN:{isbn_clean}"
    if key not in data:
        return None
    d = data[key]
    pub_date = d.get("publish_date", "") or ""
    year_match = re.search(r"\b(\d{4})\b", pub_date)
    return {
        "title": d.get("title"),
        "authors": ", ".join(a.get("name", "") for a in d.get("authors", [])) or None,
        "isbn": isbn_clean,
        "publisher": ", ".join(p.get("name", "") for p in d.get("publishers", [])) or None,
        "pub_year": year_match.group(1) if year_match else (pub_date or None),
        "pages": d.get("number_of_pages"),
        "language": None,
    }
