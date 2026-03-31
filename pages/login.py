import streamlit as st
from database.db import get_user, get_users


def show_login():
    st.markdown(
        """
        <div style='text-align:center; padding:60px 0 30px 0;'>
            <h1 style='font-size:3rem; font-weight:bold; margin-bottom:8px;'>📈 Hiro.exe</h1>
            <p style='color:#888; font-size:1.1rem;'>株スクリーニングツール（生成AI分析搭載）</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown("### ログイン")

        user_id_input = st.number_input(
            "ユーザーID（0〜4）",
            min_value=0, max_value=4, step=1, value=0,
        )

        if st.button("ログイン", type="primary", use_container_width=True):
            user = get_user(int(user_id_input))
            if user:
                st.session_state.user_id = user["user_id"]
                st.session_state.user_name = user["name"]
                st.session_state.page = "main"
                st.rerun()
            else:
                st.error("無効なユーザーIDです")

        st.markdown("---")
        st.markdown("**デフォルトユーザー一覧**")

        users = get_users()
        header_col, name_col = st.columns([1, 2])
        header_col.markdown("**ID**")
        name_col.markdown("**名前**")
        for u in users:
            header_col.write(str(u["user_id"]))
            name_col.write(u["name"])
