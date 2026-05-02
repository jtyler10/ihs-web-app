import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from nextcloud import nc_configured, nc_list, nc_download, nc_upload

st.set_page_config(page_title="NextCloud — IHS", layout="wide")
from auth import require_login
require_login()
st.title("NextCloud Files")

if not nc_configured():
    st.error(
        "NextCloud is not configured. "
        "Add **NC_URL**, **NC_USER**, and **NC_PASSWORD** to your `.env` file."
    )
    st.stop()

# ── Navigation state ──────────────────────────────────────────────────
if "nc_path" not in st.session_state:
    st.session_state["nc_path"] = ""

path  = st.session_state["nc_path"]
parts = [p for p in path.split("/") if p]

# ── Breadcrumb ────────────────────────────────────────────────────────
breadcrumb = [("Home", "")] + [(p, "/".join(parts[:i + 1])) for i, p in enumerate(parts)]
bc_parts   = []
for label, bc_path in breadcrumb[:-1]:
    bc_parts.append(f"[{label}](#)")
    if st.button(label, key=f"bc_{bc_path}", help=f"Go to {label}"):
        st.session_state["nc_path"] = bc_path
        for k in list(st.session_state):
            if k.startswith("_nc_dl_"):
                del st.session_state[k]
        st.rerun()

current_label = breadcrumb[-1][0]
st.markdown(" / ".join(bc_parts + [f"**{current_label}**"]))

st.markdown("---")

# ── List directory ────────────────────────────────────────────────────
browse_tab, upload_tab = st.tabs(["Browse & Download", "Upload"])

with browse_tab:
    try:
        with st.spinner("Loading…"):
            items = nc_list(path)
    except Exception as e:
        st.error(f"Could not list directory: {e}")
        st.stop()

    dirs  = [i for i in items if i["type"] == "directory"]
    files = [i for i in items if i["type"] == "file"]

    if not dirs and not files:
        st.info("This folder is empty.")

    # Folders
    if dirs:
        st.subheader("Folders")
        folder_cols = st.columns(4)
        for idx, d in enumerate(dirs):
            with folder_cols[idx % 4]:
                if st.button(f"📁 {d['name']}", key=f"dir_{d['path']}", use_container_width=True):
                    st.session_state["nc_path"] = d["path"]
                    for k in list(st.session_state):
                        if k.startswith("_nc_dl_"):
                            del st.session_state[k]
                    st.rerun()

    # Files
    if files:
        st.subheader("Files")
        for f in files:
            is_pdf   = f["name"].lower().endswith(".pdf")
            dl_key   = f"_nc_dl_{f['path']}"
            err_key  = f"_nc_err_{f['path']}"
            ext_key  = "_nc_pdf_bytes"

            col_name, col_dl, col_ext = st.columns([5, 2, 2])

            with col_name:
                icon = "📄" if not is_pdf else "📕"
                st.markdown(f"{icon} **{f['name']}** &nbsp; <small>{f['size_mb']} MB</small>",
                            unsafe_allow_html=True)

            with col_dl:
                if dl_key in st.session_state:
                    st.download_button(
                        "⬇ Save",
                        data=st.session_state[dl_key],
                        file_name=f["name"],
                        mime="application/pdf" if is_pdf else "application/octet-stream",
                        key=f"save_{f['path']}",
                        use_container_width=True,
                    )
                else:
                    if st.session_state.get(err_key):
                        st.error(st.session_state.pop(err_key))
                    if st.button("⬇ Fetch", key=f"dl_{f['path']}", use_container_width=True):
                        with st.spinner(f"Downloading {f['name']}…"):
                            try:
                                st.session_state[dl_key] = nc_download(f["path"])
                                st.rerun()
                            except Exception as e:
                                st.session_state[err_key] = f"Download failed: {e}"
                                st.rerun()

            with col_ext:
                if is_pdf:
                    if st.button("Run Extraction", key=f"ext_{f['path']}", use_container_width=True):
                        with st.spinner(f"Fetching {f['name']} for extraction…"):
                            try:
                                data = st.session_state.get(dl_key) or nc_download(f["path"])
                                st.session_state[ext_key]          = data
                                st.session_state["_nc_pdf_name"]   = f["name"]
                                st.success(
                                    f"**{f['name']}** loaded. "
                                    "Navigate to **PDF Extraction** in the sidebar to process it."
                                )
                            except Exception as e:
                                st.error(f"Could not load PDF: {e}")

with upload_tab:
    st.markdown(f"Uploading to: **/{path}**" if path else "Uploading to: **root**")

    up_file = st.file_uploader("Choose a file to upload", key="nc_up_file")
    if up_file:
        default_path = f"{path}/{up_file.name}".strip("/")
        up_path = st.text_input(
            "Save as (path relative to your NC root)",
            value=default_path,
            key="nc_up_path",
        )
        if st.button("Upload to NextCloud", type="primary", use_container_width=True):
            target = up_path.strip()
            if not target:
                st.warning("Enter a destination path.")
            else:
                with st.spinner(f"Uploading to {target}…"):
                    try:
                        nc_upload(target, up_file.read())
                        st.success(f"Uploaded to **{target}**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")
