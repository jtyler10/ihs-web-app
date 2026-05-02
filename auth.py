import bcrypt
import sqlalchemy
import streamlit as st
from db import SessionLocal


def _ensure_table():
    session = SessionLocal()
    try:
        session.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS users (
                id           INT PRIMARY KEY AUTO_INCREMENT,
                username     VARCHAR(64)  NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                display_name VARCHAR(128),
                role         VARCHAR(32)  DEFAULT 'user',
                created_at   DATETIME     DEFAULT NOW()
            )
        """))
        session.commit()
    finally:
        session.close()


def _user_count():
    session = SessionLocal()
    try:
        return session.execute(sqlalchemy.text("SELECT COUNT(*) FROM users")).scalar()
    finally:
        session.close()


def _get_user(username):
    session = SessionLocal()
    try:
        row = session.execute(
            sqlalchemy.text(
                "SELECT id, username, password_hash, display_name, role "
                "FROM users WHERE username = :u"
            ),
            {"u": username},
        ).fetchone()
        if row:
            return {"id": row[0], "username": row[1], "password_hash": row[2],
                    "display_name": row[3], "role": row[4]}
        return None
    finally:
        session.close()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def require_login():
    """Call immediately after st.set_page_config() on every page.
    Shows a login/setup form and halts the page if the user is not authenticated.
    Injects a logout button into the sidebar when authenticated.
    """
    _ensure_table()

    if st.session_state.get("authenticated"):
        with st.sidebar:
            name = st.session_state.get("display_name") or st.session_state.get("username", "")
            st.caption(f"Logged in as **{name}**")
            if st.button("Logout", key="_logout"):
                for k in ("authenticated", "username", "display_name", "role"):
                    st.session_state.pop(k, None)
                st.rerun()
        return  # authenticated — let the page render normally

    # ── not authenticated ─────────────────────────────────────────────────────
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("## IHS Inventory")
        st.markdown("---")

        try:
            count = _user_count()
        except Exception:
            count = 0

        if count == 0:
            # First run — create the initial admin account
            st.subheader("Create Admin Account")
            st.info("No users exist yet. Set up the first admin account to continue.")
            with st.form("setup_form"):
                su_user  = st.text_input("Username")
                su_name  = st.text_input("Display name (optional)")
                su_pass1 = st.text_input("Password", type="password")
                su_pass2 = st.text_input("Confirm password", type="password")
                setup_ok = st.form_submit_button("Create Admin", type="primary",
                                                 use_container_width=True)
            if setup_ok:
                if not su_user.strip():
                    st.error("Username is required.")
                elif not su_pass1:
                    st.error("Password is required.")
                elif su_pass1 != su_pass2:
                    st.error("Passwords do not match.")
                else:
                    session = SessionLocal()
                    try:
                        session.execute(sqlalchemy.text(
                            "INSERT INTO users (username, password_hash, display_name, role) "
                            "VALUES (:u, :h, :d, 'admin')"
                        ), {"u": su_user.strip(),
                            "h": hash_password(su_pass1),
                            "d": (su_name.strip() or su_user.strip())})
                        session.commit()
                        st.success("Admin account created. Please log in.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Could not create account: {e}")
                    finally:
                        session.close()
        else:
            st.subheader("Login")
            with st.form("login_form"):
                username  = st.text_input("Username")
                password  = st.text_input("Password", type="password")
                login_ok  = st.form_submit_button("Login", type="primary",
                                                  use_container_width=True)
            if login_ok:
                user = _get_user(username.strip())
                if user and check_password(password, user["password_hash"]):
                    st.session_state["authenticated"] = True
                    st.session_state["username"]      = user["username"]
                    st.session_state["display_name"]  = user["display_name"] or user["username"]
                    st.session_state["role"]          = user["role"]
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    st.stop()
