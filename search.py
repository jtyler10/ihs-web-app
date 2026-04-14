import re
import requests

_TIMEOUT = 30  # seconds


def _parse_docs(docs):
    """Convert raw Open Library search docs into simplified dicts."""
    results = []
    for d in docs:
        all_isbns = list(dict.fromkeys(d.get("isbn", [])))
        all_publishers = list(dict.fromkeys(d.get("publisher", [])))
        results.append({
            "title": d.get("title"),
            "authors": ", ".join(d.get("author_name", [])) or None,
            "isbn": all_isbns[0] if all_isbns else None,
            "all_isbns": all_isbns,
            "publisher": all_publishers[0] if all_publishers else None,
            "all_publishers": all_publishers,
            "pub_year": str(d["first_publish_year"]) if d.get("first_publish_year") else None,
            "pages": d.get("number_of_pages_median"),
            "language": ", ".join(d.get("language", [])) if d.get("language") else None,
        })
    return results


def search_openlibrary_by_title(title, limit=5):
    resp = requests.get(
        "https://openlibrary.org/search.json",
        params={"title": title, "limit": limit},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_docs(resp.json().get("docs", []))


def search_openlibrary_by_author(author, limit=5):
    resp = requests.get(
        "https://openlibrary.org/search.json",
        params={"author": author, "limit": limit},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_docs(resp.json().get("docs", []))


def search_openlibrary_advanced(title=None, author=None, limit=5):
    """Search by title and/or author combined."""
    params = {"limit": limit}
    if title:
        params["title"] = title
    if author:
        params["author"] = author
    resp = requests.get(
        "https://openlibrary.org/search.json",
        params=params,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_docs(resp.json().get("docs", []))


def search_openlibrary_by_isbn(isbn):
    """Look up a single book by ISBN using the Open Library Books API."""
    isbn_clean = isbn.replace("-", "").replace(" ", "")
    resp = requests.get(
        "https://openlibrary.org/api/books",
        params={"bibkeys": f"ISBN:{isbn_clean}", "format": "json", "jscmd": "data"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    key = f"ISBN:{isbn_clean}"
    if key not in data:
        return None
    d = data[key]
    pub_date = d.get("publish_date", "") or ""
    year_match = re.search(r"\b(\d{4})\b", pub_date)
    publishers = [p.get("name", "") for p in d.get("publishers", []) if p.get("name")]
    return {
        "title": d.get("title"),
        "authors": ", ".join(a.get("name", "") for a in d.get("authors", [])) or None,
        "isbn": isbn_clean,
        "all_isbns": [isbn_clean],
        "publisher": publishers[0] if publishers else None,
        "all_publishers": publishers,
        "pub_year": year_match.group(1) if year_match else (pub_date or None),
        "pages": d.get("number_of_pages"),
        "language": None,
    }
