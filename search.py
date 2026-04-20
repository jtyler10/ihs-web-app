import os
import re
import requests
import xml.etree.ElementTree as ET

_TIMEOUT = 120  # seconds
_MODS_NS = "http://www.loc.gov/mods/v3"
_LOC_SRU = "https://lx2.loc.gov/sru/catalog"


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


# ── Library of Congress (SRU catalog) ────────────────────────────────────

def _parse_mods_xml(xml_text):
    """Parse SRU/MODS XML response into result dicts."""
    root = ET.fromstring(xml_text)
    results = []
    for mods in root.iter(f"{{{_MODS_NS}}}mods"):
        # Title (+ optional subtitle)
        ti = mods.find(f".//{{{_MODS_NS}}}titleInfo[not(@type)]/{{{_MODS_NS}}}title")
        if ti is None:
            ti = mods.find(f".//{{{_MODS_NS}}}titleInfo/{{{_MODS_NS}}}title")
        title = (ti.text or "").strip() if ti is not None else ""
        if not title:
            continue
        sub = mods.find(f".//{{{_MODS_NS}}}titleInfo/{{{_MODS_NS}}}subTitle")
        if sub is not None and sub.text:
            title = title.rstrip(":").strip() + ": " + sub.text.strip()

        # Authors — collect all personal name entries
        authors = []
        for name in mods.findall(f".//{{{_MODS_NS}}}name[@type='personal']"):
            parts = [np.text.strip() for np in name.findall(f"{{{_MODS_NS}}}namePart") if np.text]
            if parts:
                authors.append(", ".join(parts))
        author_str = "; ".join(authors) or None

        # Publication info
        origin = mods.find(f".//{{{_MODS_NS}}}originInfo")
        publisher = place = year = None
        if origin is not None:
            pub_el = origin.find(f"{{{_MODS_NS}}}publisher")
            if pub_el is not None:
                publisher = (pub_el.text or "").strip() or None

            for pt in [f".//{{{_MODS_NS}}}place/{{{_MODS_NS}}}placeTerm[@type='text']",
                       f".//{{{_MODS_NS}}}place/{{{_MODS_NS}}}placeTerm"]:
                place_el = origin.find(pt)
                if place_el is not None and place_el.text:
                    place = place_el.text.strip() or None
                    break

            for tag in [f"{{{_MODS_NS}}}dateIssued", f"{{{_MODS_NS}}}copyrightDate"]:
                date_el = origin.find(tag)
                if date_el is not None and date_el.text:
                    m = re.search(r"\b(\d{4})\b", date_el.text)
                    if m:
                        year = m.group(1)
                        break

        # ISBNs
        all_isbns = [
            ident.text.strip().replace("-", "")
            for ident in mods.findall(f".//{{{_MODS_NS}}}identifier[@type='isbn']")
            if ident.text
        ]

        # Language
        lang_el = mods.find(f".//{{{_MODS_NS}}}language/{{{_MODS_NS}}}languageTerm")
        language = lang_el.text if lang_el is not None else None

        results.append({
            "title": title,
            "authors": author_str,
            "isbn": all_isbns[0] if all_isbns else None,
            "all_isbns": all_isbns,
            "publisher": publisher,
            "all_publishers": [publisher] if publisher else [],
            "publish_place": place,
            "pub_year": year,
            "pages": None,
            "language": language,
            "source": "Library of Congress",
        })
    return results


def _loc_sru_search(query, limit=5):
    resp = requests.get(
        _LOC_SRU,
        params={
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": query,
            "maximumRecords": str(limit),
            "recordSchema": "mods",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return _parse_mods_xml(resp.text)


def search_loc_by_title(title, limit=5):
    return _loc_sru_search(f'dc.title="{title}"', limit)


def search_loc_by_author(author, limit=5):
    return _loc_sru_search(f'dc.creator="{author}"', limit)


def search_loc_by_isbn(isbn):
    isbn_clean = isbn.replace("-", "").replace(" ", "")
    results = _loc_sru_search(f'bath.isbn="{isbn_clean}"', 1)
    return results[0] if results else None


def search_loc_advanced(title=None, author=None, limit=5):
    parts = []
    if title:
        parts.append(f'dc.title="{title}"')
    if author:
        parts.append(f'dc.creator="{author}"')
    if not parts:
        return []
    return _loc_sru_search(" AND ".join(parts), limit)


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
