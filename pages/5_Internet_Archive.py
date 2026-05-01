import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import streamlit as st
from search import search_internet_archive, get_ia_pdfs

st.set_page_config(page_title="Internet Archive — IHS Inventory", layout="centered")
st.title("Internet Archive PDF Search")
st.caption(
    "Searches freely downloadable texts (public domain / open access). "
    "Click 'Get PDFs' on any result to see available files."
)

# ── Search form ────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    ia_title = st.text_input("Title", placeholder="e.g. The Servile State", key="ia_title")
with col2:
    ia_author = st.text_input("Author", placeholder="e.g. Belloc", key="ia_author")

if st.button("Search", use_container_width=True, type="primary"):
    if not ia_title.strip() and not ia_author.strip():
        st.warning("Enter a title and/or author.")
    else:
        with st.spinner("Searching Internet Archive…"):
            try:
                st.session_state["_ia_results"] = search_internet_archive(
                    title=ia_title.strip() or None,
                    author=ia_author.strip() or None,
                    limit=10,
                )
                # Clear stale PDF lists and downloaded bytes from previous search
                for key in list(st.session_state.keys()):
                    if key.startswith(("_ia_pdfs_", "_ia_bytes_")):
                        del st.session_state[key]
            except Exception as e:
                st.error(f"Search error: {e}")
                st.session_state["_ia_results"] = []

results = st.session_state.get("_ia_results")
if results is None:
    st.stop()

if not results:
    st.info("No freely downloadable PDFs found. Try broader search terms.")
    st.stop()

st.markdown(f"**{len(results)} result(s)**")
st.markdown("---")

for item in results:
    iid = item["identifier"]

    with st.container():
        hdr, link_col = st.columns([5, 1])
        with hdr:
            st.markdown(f"**{item['title']}**")
            parts = [p for p in [item["creator"], item["year"]] if p]
            if parts:
                st.caption(" · ".join(parts))
            if item["description"]:
                desc = item["description"]
                st.caption(desc[:200] + ("…" if len(desc) > 200 else ""))
        with link_col:
            st.markdown(
                f'<a href="{item["ia_url"]}" target="_blank">'
                f'View on<br>Archive.org ↗</a>',
                unsafe_allow_html=True,
            )

        # ── PDF file list ──────────────────────────────────────────────
        pdf_key = f"_ia_pdfs_{iid}"
        if pdf_key not in st.session_state:
            if st.button("Get PDFs", key=f"get_{iid}"):
                with st.spinner("Fetching file list…"):
                    try:
                        st.session_state[pdf_key] = get_ia_pdfs(iid)
                    except Exception as e:
                        st.error(f"Could not fetch files: {e}")
                        st.session_state[pdf_key] = []
                st.rerun()
        else:
            pdfs = st.session_state[pdf_key]
            if not pdfs:
                st.caption("No PDF files found for this item.")
            else:
                for pdf in pdfs:
                    bytes_key = f"_ia_bytes_{iid}_{pdf['name']}"
                    info_col, btn_col = st.columns([3, 2])
                    with info_col:
                        st.caption(f"{pdf['name']}  ({pdf['size_mb']} MB)")
                    with btn_col:
                        if bytes_key in st.session_state:
                            # Bytes already fetched — offer the save button
                            st.download_button(
                                label="⬇ Save PDF",
                                data=st.session_state[bytes_key],
                                file_name=pdf["name"],
                                mime="application/pdf",
                                key=f"save_{iid}_{pdf['name']}",
                                use_container_width=True,
                            )
                        else:
                            if st.button(
                                "⬇ Download",
                                key=f"dl_{iid}_{pdf['name']}",
                                use_container_width=True,
                            ):
                                with st.spinner(
                                    f"Downloading {pdf['size_mb']} MB…"
                                ):
                                    try:
                                        resp = requests.get(
                                            pdf["url"], timeout=300
                                        )
                                        resp.raise_for_status()
                                        st.session_state[bytes_key] = resp.content
                                    except Exception as e:
                                        st.error(f"Download failed: {e}")
                                st.rerun()

    st.markdown("---")
