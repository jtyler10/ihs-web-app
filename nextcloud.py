import os
import xml.etree.ElementTree as ET
from urllib.parse import unquote
import requests
from dotenv import load_dotenv

load_dotenv()

_NC_URL      = os.getenv("NC_URL", "").rstrip("/")
_NC_USER     = os.getenv("NC_USER", "")
_NC_PASSWORD = os.getenv("NC_PASSWORD", "")
_TIMEOUT     = 120

_DAV_NS = {"d": "DAV:"}

_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:">'
    "<d:prop>"
    "<d:displayname/>"
    "<d:resourcetype/>"
    "<d:getcontentlength/>"
    "</d:prop>"
    "</d:propfind>"
)


def nc_configured():
    return bool(_NC_URL and _NC_USER and _NC_PASSWORD)


def _dav_base():
    return f"{_NC_URL}/remote.php/dav/files/{_NC_USER}"


def _auth():
    return (_NC_USER, _NC_PASSWORD)


def _rel(href):
    """Strip the DAV prefix; return path relative to the user's NC root."""
    prefix = f"/remote.php/dav/files/{_NC_USER}/"
    if prefix in href:
        return unquote(href.split(prefix, 1)[1]).strip("/")
    return unquote(href).strip("/")


def nc_list(path=""):
    """List items at a path relative to the user's NC root.
    Returns a list sorted folders-first, then files alphabetically.
    Each item: {name, path, type ('directory'|'file'), size_mb}
    """
    base = f"{_dav_base()}/"
    url  = f"{_dav_base()}/{path.strip('/')}/" if path.strip("/") else base
    resp = requests.request(
        "PROPFIND", url,
        auth=_auth(),
        headers={"Depth": "1", "Content-Type": "application/xml"},
        data=_PROPFIND_BODY,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()

    root_el   = ET.fromstring(resp.content)
    current   = path.strip("/")
    items     = []

    for node in root_el.findall("d:response", _DAV_NS):
        href = node.findtext("d:href", default="", namespaces=_DAV_NS)
        rel  = _rel(href)

        if rel == current or (not rel and not current):
            continue

        propstat = node.find("d:propstat", _DAV_NS)
        if propstat is None:
            continue
        prop = propstat.find("d:prop", _DAV_NS)
        if prop is None:
            continue

        is_dir  = prop.find("d:resourcetype/d:collection", _DAV_NS) is not None
        size_el = prop.find("d:getcontentlength", _DAV_NS)
        size    = int(size_el.text) if size_el is not None and size_el.text else 0
        name    = rel.split("/")[-1] if rel else ""

        items.append({
            "name":    name,
            "path":    rel,
            "type":    "directory" if is_dir else "file",
            "size_mb": round(size / 1024 / 1024, 2),
        })

    items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
    return items


def nc_download(path):
    """Download a file from NC, return bytes."""
    resp = requests.get(
        f"{_dav_base()}/{path.strip('/')}",
        auth=_auth(),
        timeout=300,
    )
    resp.raise_for_status()
    return resp.content


def nc_upload(remote_path, data: bytes):
    """Upload bytes to NC. Parent directories are created as needed."""
    parts = remote_path.strip("/").split("/")
    for i in range(1, len(parts)):
        r = requests.request(
            "MKCOL",
            f"{_dav_base()}/{'/'.join(parts[:i])}/",
            auth=_auth(),
            timeout=_TIMEOUT,
        )
        if r.status_code not in (201, 405):  # 405 = already exists
            pass  # best-effort; failure will surface on the PUT

    resp = requests.put(
        f"{_dav_base()}/{remote_path.strip('/')}",
        data=data,
        auth=_auth(),
        timeout=300,
    )
    resp.raise_for_status()
