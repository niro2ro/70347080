import streamlit as st
from database.db import get_watchlist
from services.stock_data import get_single_stock_summary

# ナビゲーション定義
_NAV_ITEMS = [
    ("🏠 メイン画面", "main"),
    ("🔍 スクリーニング", "screening"),
    ("📊 バックテスト", "backtest"),
    ("💬 AI質問", "ai_chat"),
    ("📊 銘柄比較", "comparison"),
    ("📜 分析履歴", "history"),
]


def show_watchlist_sidebar():
    """サイドバーにナビゲーション＋ウォッチリストを常駐表示"""
    with st.sidebar:
        # --- ユーザー情報 ---
        st.markdown(f"### 👤 {st.session_state.get('user_name', '')}")

        if st.button("ログアウト", key="sidebar_logout", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.session_state.page = "login"
            st.rerun()

        # --- ナビゲーション ---
        st.markdown("---")
        st.markdown("### 🧭 メニュー")
        current_page = st.session_state.get("page", "main")
        for label, page_key in _NAV_ITEMS:
            is_current = current_page == page_key
            btn_type = "primary" if is_current else "secondary"
            if st.button(label, key=f"nav_{page_key}", use_container_width=True, type=btn_type):
                st.session_state.page = page_key
                st.rerun()

        # --- ウォッチリスト ---
        st.markdown("---")
        st.markdown("### 📋 ウォッチリスト")

        rows = get_watchlist(st.session_state.user_id)
        tickers = [r["ticker"] for r in rows]

        if not tickers:
            st.info("ウォッチリストは空です")
            st.caption("銘柄詳細画面の ☆ ボタンで追加できます")
            return

        for ticker in tickers:
            _render_watchlist_item(ticker)


def _render_watchlist_item(ticker: str):
    data = get_single_stock_summary(ticker)

    with st.container():
        name = data["name"] if data else ticker
        display_name = name[:9] + "…" if len(name) > 9 else name

        col_btn, col_chg = st.columns([3, 1])

        with col_btn:
            if st.button(
                f"**{ticker}** {display_name}",
                key=f"wl_{ticker}",
                use_container_width=True,
            ):
                st.session_state.selected_ticker = ticker
                st.session_state.page = "detail"
                st.rerun()

        with col_chg:
            if data:
                chg = data["change_pct"]
                color = "green" if chg >= 0 else "red"
                st.markdown(
                    f"<span style='color:{color};font-size:0.8rem;'>{chg:+.1f}%</span>",
                    unsafe_allow_html=True,
                )

        if data:
            rsi = data.get("rsi", 50)
            trend = data.get("trend", "-")
            st.caption(f"RSI: {rsi:.0f}  |  {trend}")

        st.markdown(
            "<hr style='margin:4px 0; border-color:#333;'>",
            unsafe_allow_html=True,
        )
