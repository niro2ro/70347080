import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database.db import init_db
from pages.login import show_login
from pages.main_page import show_main
from pages.detail_page import show_detail
from pages.screening_page import show_screening
from pages.ai_chat_page import show_ai_chat
from pages.comparison_page import show_comparison
from pages.history_page import show_history
from pages.backtest_page import show_backtest
from components.watchlist import show_watchlist_sidebar

_PAGE_HANDLERS = {
    "login": show_login,
    "main": show_main,
    "detail": show_detail,
    "screening": show_screening,
    "ai_chat": show_ai_chat,
    "comparison": show_comparison,
    "history": show_history,
    "backtest": show_backtest,
}


def _init_session():
    defaults = {
        "page": "login",
        "user_id": None,
        "user_name": None,
        "selected_ticker": None,
        "market": "JP",
        "ai_result": {},
        "chat_history": [],
        "chat_context_ticker": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_HIDE_DEFAULT_NAV = """
<style>
/* StreamlitデフォルトのPagesナビゲーションタブを非表示 */
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
</style>
"""


def main():
    st.set_page_config(
        page_title="Hiro.exe — 株スクリーニングツール",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # デフォルトページタブを全画面で非表示
    st.markdown(_HIDE_DEFAULT_NAV, unsafe_allow_html=True)

    init_db()
    _init_session()

    # ログイン済み & ログイン画面以外はサイドバーを表示
    if st.session_state.user_id is not None and st.session_state.page != "login":
        show_watchlist_sidebar()

    # ページルーティング
    page = st.session_state.page
    handler = _PAGE_HANDLERS.get(page)
    if handler:
        handler()
    else:
        st.session_state.page = "login"
        st.rerun()


if __name__ == "__main__":
    main()
