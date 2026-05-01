import os
import re
import requests

_TIMEOUT = 120  # seconds


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


# ── Library of Congress (Z39.50 / Voyager) ───────────────────────────────
# Direct Z39.50 connection — returns full MARC records including ISBNs,
# publisher city, page count, and summaries. Requires PyZ3950 + pymarc.

_LOC_HOST = "z3950.loc.gov"
_LOC_PORT = 7090
_LOC_DB   = "Voyager"

_LOC_LANG = {
    "eng": "English", "fre": "French", "ger": "German",
    "spa": "Spanish", "lat": "Latin",  "ita": "Italian",
    "por": "Portuguese", "dut": "Dutch", "rus": "Russian",
}


def _field(rec, tag):
    """Return the first MARC field with the given tag, or None."""
    fields = rec.get_fields(tag)
    return fields[0] if fields else None


def _sf(field, code):
    """Return the first value of a MARC subfield, or '' if absent."""
    if field is None:
        return ""
    vals = field.get_subfields(code)
    return vals[0] if vals else ""


def _parse_loc_marc(rec):
    """Convert a pymarc Record to the standard search-result dict."""
    f245 = _field(rec, "245")
    if not f245:
        return None
    title = (_sf(f245, "a") + " " + _sf(f245, "b")).strip().rstrip(" /:") or None
    if not title:
        return None

    f100 = _field(rec, "100")
    main = _sf(f100, "a").rstrip(", .") or None
    added = [_sf(f, "a").rstrip(", .") for f in rec.get_fields("700") if _sf(f, "a")]
    authors = ", ".join(filter(None, ([main] if main else []) + added)) or None

    isbns = []
    for f in rec.get_fields("020"):
        raw = _sf(f, "a")
        m = re.match(r"[\dX\-]+", raw, re.IGNORECASE)
        if m:
            isbns.append(m.group().replace("-", ""))

    pub = city = year_raw = None
    for f in rec.get_fields("264"):
        if f.indicator2 == "1":
            pub      = _sf(f, "b").rstrip(", .") or None
            city     = _sf(f, "a").rstrip(", :") or None
            year_raw = _sf(f, "c")
            break
    if not pub:
        f260 = _field(rec, "260")
        if f260:
            pub      = _sf(f260, "b").rstrip(", .") or None
            city     = _sf(f260, "a").rstrip(", :") or None
            year_raw = _sf(f260, "c")

    year = None
    if year_raw:
        m = re.search(r"\b(\d{4})\b", year_raw)
        year = m.group(1) if m else None

    pages = None
    pages_raw = _sf(_field(rec, "300"), "a")
    if pages_raw:
        m = re.search(r"(\d+)", pages_raw)
        pages = int(m.group(1)) if m else None

    lang_codes = [_sf(f, "a") for f in rec.get_fields("041") if _sf(f, "a")]
    if not lang_codes:
        f008 = _field(rec, "008")
        if f008 and len(f008.data) >= 38:
            lang_codes = [f008.data[35:38].strip()]
    language = ", ".join(_LOC_LANG.get(c, c) for c in lang_codes) or None

    description = _sf(_field(rec, "520"), "a") or None

    return {
        "title":          title,
        "authors":        authors,
        "isbn":           isbns[0] if isbns else None,
        "all_isbns":      isbns,
        "publisher":      pub,
        "all_publishers": [pub] if pub else [],
        "publish_place":  city,
        "pub_year":       year,
        "pages":          pages,
        "language":       language,
        "description":    description,
        "source":         "Library of Congress",
    }


def _loc_z3950_search(pqf, limit=5):
    from PyZ3950 import zoom
    import pymarc, io

    conn = zoom.Connection(_LOC_HOST, _LOC_PORT)
    conn.databaseName = _LOC_DB
    conn.preferredRecordSyntax = "USMARC"
    try:
        results = conn.search(zoom.Query("PQF", pqf))
        parsed = []
        for i in range(min(limit, len(results))):
            try:
                raw = results[i].data
                if isinstance(raw, str):
                    raw = raw.encode("latin-1")
                rec = next(pymarc.MARCReader(io.BytesIO(raw)))
                r = _parse_loc_marc(rec)
                if r:
                    parsed.append(r)
            except Exception:
                pass
        return parsed
    finally:
        conn.close()


def search_loc_by_title(title, limit=5):
    return _loc_z3950_search(f'@attr 1=4 @attr 4=1 "{title}"', limit)


def search_loc_by_author(author, limit=5):
    return _loc_z3950_search(f'@attr 1=1003 @attr 4=1 "{author}"', limit)


def search_loc_by_isbn(isbn):
    isbn_clean = re.sub(r"[^0-9X]", "", isbn.upper())
    results = _loc_z3950_search(f'@attr 1=7 "{isbn_clean}"', 1)
    return results[0] if results else None


def search_loc_advanced(title=None, author=None, limit=5):
    if title and author:
        pqf = (f'@and @attr 1=4 @attr 4=1 "{title}" '
               f'@attr 1=1003 @attr 4=1 "{author}"')
    elif title:
        pqf = f'@attr 1=4 @attr 4=1 "{title}"'
    elif author:
        pqf = f'@attr 1=1003 @attr 4=1 "{author}"'
    else:
        return []
    return _loc_z3950_search(pqf, limit)

