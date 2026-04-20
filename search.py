import os
import re
import requests

_TIMEOUT = 120  # seconds


# ── helpers ──────────────────────────────────────────────────────────────

def _coerce_str(val):
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""


# ── Open Library ─────────────────────────────────────────────────────────

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
            "source": "Open Library",
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
    places = [p.get("name", "") for p in d.get("publish_places", []) if p.get("name")]
    return {
        "title": d.get("title"),
        "authors": ", ".join(a.get("name", "") for a in d.get("authors", [])) or None,
        "isbn": isbn_clean,
        "all_isbns": [isbn_clean],
        "publisher": publishers[0] if publishers else None,
        "all_publishers": publishers,
        "publish_place": places[0] if places else None,
        "pub_year": year_match.group(1) if year_match else (pub_date or None),
        "pages": d.get("number_of_pages"),
        "language": None,
        "source": "Open Library",
    }


# ── Library of Congress ───────────────────────────────────────────────────

def _parse_loc_results(results):
    parsed = []
    for r in results:
        title = _coerce_str(r.get("title")).rstrip("/").strip()
        if not title:
            continue

        contributors = r.get("contributor") or []
        if isinstance(contributors, str):
            contributors = [contributors]
        authors = ", ".join(c for c in contributors if c) or None

        date = _coerce_str(r.get("date"))
        year_match = re.search(r"\b(\d{4})\b", date)
        year = year_match.group(1) if year_match else None

        pub_name = None
        pub_city = None
        item = r.get("item") or {}
        created_pub = _coerce_str(item.get("created_published") or "")
        if created_pub:
            # typical format: "[City] : Publisher Name, Year."
            cp_parts = created_pub.split(":", 1)
            if len(cp_parts) == 2:
                pub_city = cp_parts[0].strip().strip("[]").strip()
                rest = cp_parts[1].strip()
                pub_name = re.sub(r",?\s*\d{4}[\.,]?\s*$", "", rest).strip().rstrip(",").strip()

        parsed.append({
            "title": title,
            "authors": authors,
            "isbn": None,
            "all_isbns": [],
            "publisher": pub_name or None,
            "all_publishers": [pub_name] if pub_name else [],
            "publish_place": pub_city or None,
            "pub_year": year,
            "pages": None,
            "language": None,
            "source": "Library of Congress",
        })
    return parsed


def search_loc_by_title(title, limit=5):
    resp = requests.get(
        "https://www.loc.gov/books/",
        params={"q": title, "fo": "json", "c": str(limit)},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_loc_results(resp.json().get("results", [])[:limit])


def search_loc_by_author(author, limit=5):
    resp = requests.get(
        "https://www.loc.gov/books/",
        params={"q": author, "fo": "json", "c": str(limit)},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_loc_results(resp.json().get("results", [])[:limit])


def search_loc_by_isbn(isbn):
    isbn_clean = isbn.replace("-", "").replace(" ", "")
    resp = requests.get(
        "https://www.loc.gov/books/",
        params={"q": isbn_clean, "fo": "json", "c": "3"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    results = _parse_loc_results(resp.json().get("results", [])[:1])
    return results[0] if results else None


def search_loc_advanced(title=None, author=None, limit=5):
    parts = [p for p in [title, author] if p]
    if not parts:
        return []
    resp = requests.get(
        "https://www.loc.gov/books/",
        params={"q": " ".join(parts), "fo": "json", "c": str(limit)},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_loc_results(resp.json().get("results", [])[:limit])


# ── WorldCat (requires OCLC_CLIENT_ID + OCLC_CLIENT_SECRET) ──────────────

def worldcat_available():
    return bool(os.environ.get("OCLC_CLIENT_ID") and os.environ.get("OCLC_CLIENT_SECRET"))


def _get_worldcat_token():
    from bookops_worldcat import WorldcatAccessToken
    return WorldcatAccessToken(
        key=os.environ["OCLC_CLIENT_ID"],
        secret=os.environ["OCLC_CLIENT_SECRET"],
        options={"scope": ["WorldCatMetadataAPI"]},
    )


def _parse_worldcat_results(records):
    parsed = []
    for r in records:
        isbns = r.get("isbns") or []
        year = str(r.get("date") or "").strip() or None
        if year:
            m = re.search(r"\b(\d{4})\b", year)
            year = m.group(1) if m else year
        parsed.append({
            "title": r.get("title") or "",
            "authors": r.get("creator") or None,
            "isbn": isbns[0] if isbns else None,
            "all_isbns": isbns,
            "publisher": r.get("publisher") or None,
            "all_publishers": [r["publisher"]] if r.get("publisher") else [],
            "publish_place": r.get("publicationPlace") or None,
            "pub_year": year,
            "pages": None,
            "language": r.get("language") or None,
            "source": "WorldCat",
        })
    return parsed


def search_worldcat_by_title(title, limit=5):
    from bookops_worldcat import MetadataSession
    token = _get_worldcat_token()
    with MetadataSession(authorization=token) as session:
        resp = session.bib_search(q=f'ti:"{title}"', itemType="book", limit=limit)
        resp.raise_for_status()
        return _parse_worldcat_results(resp.json().get("briefRecords", []))


def search_worldcat_by_author(author, limit=5):
    from bookops_worldcat import MetadataSession
    token = _get_worldcat_token()
    with MetadataSession(authorization=token) as session:
        resp = session.bib_search(q=f'au:"{author}"', itemType="book", limit=limit)
        resp.raise_for_status()
        return _parse_worldcat_results(resp.json().get("briefRecords", []))


def search_worldcat_by_isbn(isbn):
    from bookops_worldcat import MetadataSession
    isbn_clean = isbn.replace("-", "").replace(" ", "")
    token = _get_worldcat_token()
    with MetadataSession(authorization=token) as session:
        resp = session.bib_search(q=f'bn:{isbn_clean}', itemType="book", limit=1)
        resp.raise_for_status()
        records = resp.json().get("briefRecords", [])
        results = _parse_worldcat_results(records)
        return results[0] if results else None


def search_worldcat_advanced(title=None, author=None, limit=5):
    from bookops_worldcat import MetadataSession
    parts = []
    if title:
        parts.append(f'ti:"{title}"')
    if author:
        parts.append(f'au:"{author}"')
    if not parts:
        return []
    token = _get_worldcat_token()
    with MetadataSession(authorization=token) as session:
        resp = session.bib_search(q=" AND ".join(parts), itemType="book", limit=limit)
        resp.raise_for_status()
        return _parse_worldcat_results(resp.json().get("briefRecords", []))
