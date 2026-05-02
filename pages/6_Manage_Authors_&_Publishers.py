import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy
import streamlit as st
from db import SessionLocal

st.set_page_config(page_title="Manage — IHS", layout="wide")
from auth import require_login
require_login()
st.title("Manage Authors & Publishers")

_is_admin = st.session_state.get("role") == "admin"
_tabs = ["Authors", "Publishers"] + (["Users"] if _is_admin else [])
auth_tab, pub_tab, *_rest = st.tabs(_tabs)
user_tab = _rest[0] if _rest else None


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

    # ── search + add button ───────────────────────────────────────────────────
    col_search, col_add = st.columns([4, 1])
    with col_search:
        a_search = st.text_input("Search authors", placeholder="Name, title, bio…", key="a_search")
    with col_add:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("+ Add New Author", use_container_width=True, key="a_add_btn"):
            st.session_state["a_mode"]        = "add"
            st.session_state["a_selected_id"] = None
            st.session_state.pop("a_data", None)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── add / edit form (rendered BEFORE the list) ────────────────────────────
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
            try:
                _run("DELETE FROM contributors WHERE c_ID = :id",
                     {"id": st.session_state["a_selected_id"]})
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
                    st.session_state.pop("_contributors", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        st.markdown("---")

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

    # ── search + add button ───────────────────────────────────────────────────
    pc1, pc2 = st.columns([4, 1])
    with pc1:
        p_search = st.text_input("Search publishers", placeholder="Name or city…", key="p_search")
    with pc2:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("+ Add New Publisher", use_container_width=True, key="p_add_btn"):
            st.session_state["p_mode"]        = "add"
            st.session_state["p_selected_id"] = None
            st.session_state.pop("p_data", None)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── add / edit form (rendered BEFORE the list) ────────────────────────────
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
                    st.session_state.pop("_publishers", None)
                    st.session_state.pop("_publisher_cities", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")

        st.markdown("---")

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


# ══════════════════════════════════════════════════════════════════════════════
# USERS  (admin only)
# ══════════════════════════════════════════════════════════════════════════════

if user_tab:
    with user_tab:
        from auth import hash_password, check_password

        def _fetch_users():
            session = SessionLocal()
            try:
                rows = session.execute(sqlalchemy.text(
                    "SELECT id, username, display_name, role, created_at "
                    "FROM users ORDER BY username"
                ))
                return [{"id": r[0], "username": r[1], "display_name": r[2] or "",
                         "role": r[3] or "user", "created_at": str(r[4] or "")} for r in rows]
            finally:
                session.close()

        users = _fetch_users()

        # ── add button ────────────────────────────────────────────────────────
        uc1, uc2 = st.columns([4, 1])
        with uc2:
            st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
            if st.button("+ Add New User", use_container_width=True, key="u_add_btn"):
                st.session_state["u_mode"]        = "add"
                st.session_state["u_selected_id"] = None
                st.session_state.pop("u_data", None)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── add / edit form (before list) ─────────────────────────────────────
        u_mode = st.session_state.get("u_mode")
        if u_mode in ("add", "edit"):
            ud = st.session_state.get("u_data", {}) if u_mode == "edit" else {}
            st.markdown("---")
            st.subheader("Edit User" if u_mode == "edit" else "Add New User")

            with st.form("user_form", clear_on_submit=False):
                uf1, uf2, uf3 = st.columns([2, 2, 1])
                with uf1:
                    u_username = st.text_input("Username *", value=ud.get("username") or "")
                with uf2:
                    u_display  = st.text_input("Display name", value=ud.get("display_name") or "")
                with uf3:
                    u_role = st.selectbox("Role", ["user", "admin"],
                                          index=0 if ud.get("role") != "admin" else 1)

                st.markdown("**Password**" + (" — leave blank to keep current" if u_mode == "edit" else ""))
                up1, up2 = st.columns(2)
                with up1:
                    u_pass1 = st.text_input("Password", type="password",
                                            placeholder="New password" if u_mode == "edit" else "")
                with up2:
                    u_pass2 = st.text_input("Confirm password", type="password")

                us_col, ud_col, uc_col = st.columns([2, 1, 1])
                with us_col:
                    u_submitted = st.form_submit_button("Save", type="primary", use_container_width=True)
                with ud_col:
                    u_delete = (
                        st.form_submit_button("Delete", use_container_width=True)
                        if u_mode == "edit" else False
                    )
                with uc_col:
                    u_cancel = st.form_submit_button("Cancel", use_container_width=True)

            if u_cancel:
                st.session_state.pop("u_mode", None)
                st.session_state.pop("u_data", None)
                st.rerun()

            if u_delete and u_mode == "edit":
                if st.session_state["u_selected_id"] == st.session_state.get("username"):
                    st.error("You cannot delete your own account.")
                else:
                    try:
                        _run("DELETE FROM users WHERE id = :id",
                             {"id": st.session_state["u_selected_id"]})
                        st.success("User deleted.")
                        st.session_state.pop("u_mode", None)
                        st.session_state.pop("u_data", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

            if u_submitted:
                if not u_username.strip():
                    st.error("Username is required.")
                elif u_mode == "add" and not u_pass1:
                    st.error("Password is required for new users.")
                elif u_pass1 and u_pass1 != u_pass2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        if u_mode == "add":
                            _run(
                                "INSERT INTO users (username, password_hash, display_name, role) "
                                "VALUES (:u, :h, :d, :r)",
                                {"u": u_username.strip(),
                                 "h": hash_password(u_pass1),
                                 "d": u_display.strip() or u_username.strip(),
                                 "r": u_role},
                            )
                            st.success(f"Added user **{u_username}**.")
                        else:
                            uid = st.session_state["u_selected_id"]
                            if u_pass1:
                                _run(
                                    "UPDATE users SET username=:u, display_name=:d, role=:r, "
                                    "password_hash=:h WHERE id=:id",
                                    {"u": u_username.strip(), "d": u_display.strip(),
                                     "r": u_role, "h": hash_password(u_pass1), "id": uid},
                                )
                            else:
                                _run(
                                    "UPDATE users SET username=:u, display_name=:d, role=:r WHERE id=:id",
                                    {"u": u_username.strip(), "d": u_display.strip(),
                                     "r": u_role, "id": uid},
                                )
                            st.success(f"Updated user **{u_username}**.")
                        st.session_state.pop("u_mode", None)
                        st.session_state.pop("u_data", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Save failed: {e}")

            st.markdown("---")

        # ── user list ─────────────────────────────────────────────────────────
        if users:
            uh1, uh2, uh3, uh4 = st.columns([3, 3, 2, 1])
            with uh1: st.markdown("**Username**")
            with uh2: st.markdown("**Display Name**")
            with uh3: st.markdown("**Role**")
            st.divider()

            for u in users:
                uc1, uc2, uc3, uc4 = st.columns([3, 3, 2, 1])
                with uc1: st.markdown(u["username"])
                with uc2: st.markdown(u["display_name"] or "—")
                with uc3: st.markdown(u["role"])
                with uc4:
                    if st.button("✏️", key=f"edit_u_{u['id']}", help="Edit"):
                        st.session_state["u_mode"]        = "edit"
                        st.session_state["u_selected_id"] = u["id"]
                        st.session_state["u_data"]        = u
                        st.rerun()
        else:
            st.info("No users found.")
