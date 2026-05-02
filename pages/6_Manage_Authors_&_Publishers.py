import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
import streamlit as st
from db import SessionLocal

st.set_page_config(page_title="Manage — IHS", layout="wide")
st.title("Manage Authors & Publishers")

auth_tab, pub_tab = st.tabs(["Authors", "Publishers"])


# ── shared helpers ────────────────────────────────────────────────────────────

def _run(sql, params=None):
    session = SessionLocal()
    try:
        session.execute(sqlalchemy.text(sql), params or {})
        session.commit()
    finally:
        session.close()


def _build_name(*parts):
    return " ".join(p for p in parts if p and p.strip())


# ══════════════════════════════════════════════════════════════════════════════
# AUTHORS
# ══════════════════════════════════════════════════════════════════════════════

with auth_tab:

    def _fetch_authors():
        session = SessionLocal()
        try:
            rows = session.execute(sqlalchemy.text(
                "SELECT c_ID, c_name, prefix, fname, mname, c_lname, suffix, "
                "birthyear, birthyear_ca, deathyear, deathyear_ca, title, short_bio, bio "
                "FROM contributors ORDER BY c_lname, fname"
            ))
            cols = ["id", "c_name", "prefix", "fname", "mname", "c_lname",
                    "suffix", "birthyear", "birthyear_ca", "deathyear",
                    "deathyear_ca", "title", "short_bio", "bio"]
            return [dict(zip(cols, r)) for r in rows]
        finally:
            session.close()

    authors = _fetch_authors()

    # ── search + add ─────────────────────────────────────────────────────────
    col_search, col_add = st.columns([4, 1])
    with col_search:
        a_search = st.text_input("Search authors", placeholder="Name, title, bio…", key="a_search")
    with col_add:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("+ Add New Author", use_container_width=True, key="a_add_btn"):
            st.session_state["a_mode"]       = "add"
            st.session_state["a_selected_id"] = None
        st.markdown("</div>", unsafe_allow_html=True)

    # ── filtered list ─────────────────────────────────────────────────────────
    q = a_search.lower()
    visible = [
        a for a in authors
        if not q or any(q in str(a.get(f) or "").lower()
                        for f in ("c_name", "title", "short_bio", "bio"))
    ]

    if visible:
        h1, h2, h3, h4, h5 = st.columns([3, 2, 3, 5, 1])
        with h1: st.markdown("**Name**")
        with h2: st.markdown("**Born – Died**")
        with h3: st.markdown("**Title / Role**")
        with h4: st.markdown("**Short Bio**")
        st.divider()

        for a in visible:
            born  = ("c. " if a["birthyear_ca"] else "") + (a["birthyear"] or "")
            died  = ("c. " if a["deathyear_ca"] else "") + (a["deathyear"] or "")
            dates = " – ".join(filter(None, [born, died])) or "—"
            bio_p = (a["short_bio"] or "")[:80] + ("…" if len(a["short_bio"] or "") > 80 else "")

            c1, c2, c3, c4, c5 = st.columns([3, 2, 3, 5, 1])
            with c1: st.markdown(a["c_name"])
            with c2: st.markdown(dates)
            with c3: st.markdown(a["title"] or "—")
            with c4: st.markdown(bio_p or "—")
            with c5:
                if st.button("✏️", key=f"edit_a_{a['id']}", help="Edit"):
                    st.session_state["a_mode"]        = "edit"
                    st.session_state["a_selected_id"] = a["id"]
                    st.session_state["a_data"]        = a
                    st.rerun()
    else:
        st.info("No authors match your search." if q else "No authors found.")

    # ── add / edit form ───────────────────────────────────────────────────────
    mode = st.session_state.get("a_mode")
    if mode in ("add", "edit"):
        d = st.session_state.get("a_data", {}) if mode == "edit" else {}
        st.markdown("---")
        st.subheader("Edit Author" if mode == "edit" else "Add New Author")

        with st.form("author_form", clear_on_submit=False):
            nc1, nc2, nc3, nc4, nc5 = st.columns([1, 2, 2, 2, 1])
            with nc1:
                prefix = st.text_input("Prefix", value=d.get("prefix") or "")
            with nc2:
                fname  = st.text_input("First name *", value=d.get("fname") or "")
            with nc3:
                mname  = st.text_input("Middle name", value=d.get("mname") or "")
            with nc4:
                lname  = st.text_input("Last name *", value=d.get("c_lname") or "")
            with nc5:
                suffix = st.text_input("Suffix", value=d.get("suffix") or "")

            dc1, dc2, dc3, dc4, dc5 = st.columns([2, 1, 2, 1, 2])
            with dc1:
                birthyear    = st.text_input("Birth year", value=d.get("birthyear") or "")
            with dc2:
                birthyear_ca = st.checkbox("c.", value=bool(d.get("birthyear_ca")), help="Circa")
            with dc3:
                deathyear    = st.text_input("Death year", value=d.get("deathyear") or "")
            with dc4:
                deathyear_ca = st.checkbox("c. ", value=bool(d.get("deathyear_ca")), help="Circa")
            with dc5:
                title = st.text_input("Title / role", value=d.get("title") or "")

            short_bio = st.text_area("Short bio", value=d.get("short_bio") or "", height=100)
            bio       = st.text_area("Full bio",  value=d.get("bio") or "",       height=200)

            save_col, del_col, cancel_col = st.columns([2, 1, 1])
            with save_col:
                submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
            with del_col:
                delete = (
                    st.form_submit_button("Delete", use_container_width=True)
                    if mode == "edit" else False
                )
            with cancel_col:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            st.session_state.pop("a_mode", None)
            st.session_state.pop("a_data", None)
            st.rerun()

        if delete and mode == "edit":
            author_id = st.session_state["a_selected_id"]
            try:
                _run("DELETE FROM contributors WHERE c_ID = :id", {"id": author_id})
                st.success("Author deleted.")
                st.session_state.pop("a_mode", None)
                st.session_state.pop("a_data", None)
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

        if submitted:
            if not fname.strip() or not lname.strip():
                st.error("First name and last name are required.")
            else:
                c_name = _build_name(prefix, fname, mname, lname, suffix)
                params = {
                    "c_name":       c_name,
                    "prefix":       prefix.strip() or None,
                    "fname":        fname.strip(),
                    "mname":        mname.strip() or None,
                    "c_lname":      lname.strip(),
                    "suffix":       suffix.strip() or None,
                    "birthyear":    birthyear.strip() or None,
                    "birthyear_ca": int(birthyear_ca),
                    "deathyear":    deathyear.strip() or None,
                    "deathyear_ca": int(deathyear_ca),
                    "title":        title.strip() or None,
                    "short_bio":    short_bio.strip(),
                    "bio":          bio.strip() or None,
                }
                try:
                    if mode == "add":
                        _run(
                            "INSERT INTO contributors "
                            "(c_name, prefix, fname, mname, c_lname, suffix, "
                            "birthyear, birthyear_ca, deathyear, deathyear_ca, title, short_bio, bio) "
                            "VALUES (:c_name, :prefix, :fname, :mname, :c_lname, :suffix, "
                            ":birthyear, :birthyear_ca, :deathyear, :deathyear_ca, :title, :short_bio, :bio)",
                            params,
                        )
                        st.success(f"Added **{c_name}**.")
                    else:
                        params["id"] = st.session_state["a_selected_id"]
                        _run(
                            "UPDATE contributors SET "
                            "c_name=:c_name, prefix=:prefix, fname=:fname, mname=:mname, "
                            "c_lname=:c_lname, suffix=:suffix, birthyear=:birthyear, "
                            "birthyear_ca=:birthyear_ca, deathyear=:deathyear, "
                            "deathyear_ca=:deathyear_ca, title=:title, short_bio=:short_bio, bio=:bio "
                            "WHERE c_ID=:id",
                            params,
                        )
                        st.success(f"Updated **{c_name}**.")
                    st.session_state.pop("a_mode", None)
                    st.session_state.pop("a_data", None)
                    # Refresh _contributors cache used by Add Book
                    st.session_state.pop("_contributors", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLISHERS
# ══════════════════════════════════════════════════════════════════════════════

with pub_tab:

    def _fetch_publishers():
        session = SessionLocal()
        try:
            rows = session.execute(sqlalchemy.text(
                "SELECT id, op_name, op_city FROM original_publishers ORDER BY op_name"
            ))
            return [{"id": r[0], "op_name": r[1] or "", "op_city": r[2] or ""} for r in rows]
        finally:
            session.close()

    publishers = _fetch_publishers()

    # ── search + add ─────────────────────────────────────────────────────────
    pc1, pc2 = st.columns([4, 1])
    with pc1:
        p_search = st.text_input("Search publishers", placeholder="Name or city…", key="p_search")
    with pc2:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("+ Add New Publisher", use_container_width=True, key="p_add_btn"):
            st.session_state["p_mode"]        = "add"
            st.session_state["p_selected_id"] = None
        st.markdown("</div>", unsafe_allow_html=True)

    # ── filtered list ─────────────────────────────────────────────────────────
    pq = p_search.lower()
    pub_visible = [
        p for p in publishers
        if not pq or pq in p["op_name"].lower() or pq in p["op_city"].lower()
    ]

    if pub_visible:
        ph1, ph2, ph3 = st.columns([5, 4, 1])
        with ph1: st.markdown("**Name**")
        with ph2: st.markdown("**City**")
        st.divider()

        for p in pub_visible:
            pc1, pc2, pc3 = st.columns([5, 4, 1])
            with pc1: st.markdown(p["op_name"])
            with pc2: st.markdown(p["op_city"] or "—")
            with pc3:
                if st.button("✏️", key=f"edit_p_{p['id']}", help="Edit"):
                    st.session_state["p_mode"]        = "edit"
                    st.session_state["p_selected_id"] = p["id"]
                    st.session_state["p_data"]        = p
                    st.rerun()
    else:
        st.info("No publishers match your search." if pq else "No publishers found.")

    # ── add / edit form ───────────────────────────────────────────────────────
    p_mode = st.session_state.get("p_mode")
    if p_mode in ("add", "edit"):
        pd_ = st.session_state.get("p_data", {}) if p_mode == "edit" else {}
        st.markdown("---")
        st.subheader("Edit Publisher" if p_mode == "edit" else "Add New Publisher")

        with st.form("publisher_form", clear_on_submit=False):
            pf1, pf2 = st.columns(2)
            with pf1:
                op_name = st.text_input("Publisher name *", value=pd_.get("op_name") or "")
            with pf2:
                op_city = st.text_input("City", value=pd_.get("op_city") or "")

            ps_col, pd_col, pc_col = st.columns([2, 1, 1])
            with ps_col:
                p_submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
            with pd_col:
                p_delete = (
                    st.form_submit_button("Delete", use_container_width=True)
                    if p_mode == "edit" else False
                )
            with pc_col:
                p_cancel = st.form_submit_button("Cancel", use_container_width=True)

        if p_cancel:
            st.session_state.pop("p_mode", None)
            st.session_state.pop("p_data", None)
            st.rerun()

        if p_delete and p_mode == "edit":
            try:
                _run("DELETE FROM original_publishers WHERE id = :id",
                     {"id": st.session_state["p_selected_id"]})
                st.success("Publisher deleted.")
                st.session_state.pop("p_mode", None)
                st.session_state.pop("p_data", None)
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

        if p_submitted:
            if not op_name.strip():
                st.error("Publisher name is required.")
            else:
                params = {"op_name": op_name.strip(), "op_city": op_city.strip()}
                try:
                    if p_mode == "add":
                        _run(
                            "INSERT INTO original_publishers (op_name, op_city) VALUES (:op_name, :op_city)",
                            params,
                        )
                        st.success(f"Added **{op_name}**.")
                    else:
                        params["id"] = st.session_state["p_selected_id"]
                        _run(
                            "UPDATE original_publishers SET op_name=:op_name, op_city=:op_city WHERE id=:id",
                            params,
                        )
                        st.success(f"Updated **{op_name}**.")
                    st.session_state.pop("p_mode", None)
                    st.session_state.pop("p_data", None)
                    # Refresh publisher cache used by Add Book
                    st.session_state.pop("_publishers", None)
                    st.session_state.pop("_publisher_cities", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
