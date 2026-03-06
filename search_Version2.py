import requests

def search_openlibrary_by_title(title, limit=5):
    """
    Query Open Library search API and return a list of simplified records.
    Each result is a dict containing keys like title, authors, isbn, publisher, pub_year, pages, language.
    """
    url = "https://openlibrary.org/search.json"
    resp = requests.get(url, params={"title": title, "limit": limit}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    docs = data.get("docs", [])
    results = []
    for d in docs:
        r = {
            "title": d.get("title"),
            "authors": ", ".join(d.get("author_name", [])) if d.get("author_name") else None,
            "isbn": d.get("isbn", [None])[0] if d.get("isbn") else None,
            "publisher": ", ".join(d.get("publisher", [])) if d.get("publisher") else None,
            "pub_year": str(d.get("first_publish_year")) if d.get("first_publish_year") else None,
            "pages": d.get("number_of_pages_median"),
            "language": ", ".join(d.get("language", [])) if d.get("language") else None,
        }
        results.append(r)
    return results


# Optional: Z39.50 note (requires PyZ3950 and pymarc)
def search_z3950_example(host, port, title, databaseName="WorldCat"):
    """
    Example pseudo-code showing how to call a Z39.50 server with PyZ3950.zoom.
    This function will require 'PyZ3950' and 'pymarc' installed and a reachable Z39.50 server.
    """
    try:
        from PyZ3950 import zoom
    except Exception as e:
        raise RuntimeError("PyZ3950 is not installed. See README for installation.") from e

    conn = zoom.Connection(host, port)
    conn.databaseName = databaseName
    query = f'@attr 1=4 "{title}"'
    rs = conn.search(query)
    results = []
    for rec in rs:
        results.append({"raw": str(rec)})
    conn.close()
    return results