import streamlit as st
from database.db import get_analysis_history
from services.stock_data import JP_TICKERS, US_TICKERS, TICKER_NAMES


def show_history():
    st.markdown("# 📜 分析履歴")
    st.caption("過去にAI分析を実行した結果の一覧です。")

    user_id = st.session_state.user_id
    all_tickers = JP_TICKERS + US_TICKERS

    # フィルター
    col_f, col_btn = st.columns([3, 1])
    with col_f:
        ticker_filter = st.selectbox(
            "銘柄で絞り込み",
            options=["すべて"] + all_tickers,
            format_func=lambda t: "すべて" if t == "すべて" else f"{t}  {TICKER_NAMES.get(t, '')}",
            key="hist_ticker",
        )
    with col_btn:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        refresh = st.button("🔄 更新", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    ticker_arg = None if ticker_filter == "すべて" else ticker_filter
    rows = get_analysis_history(user_id, ticker=ticker_arg, limit=50)

    st.markdown(f"---")
    st.markdown(f"### {len(rows)} 件の履歴")

    if not rows:
        st.info("分析履歴がありません。株式詳細画面でAI分析を実行すると記録されます。")
        return

    for row in rows:
        ticker = row["ticker"]
        name = TICKER_NAMES.get(ticker, ticker)
        created = row["created_at"]

        with st.expander(f"**{ticker}** {name}　｜　{created}"):
            st.markdown(row["ai_response"])

            col_d, _ = st.columns([1, 4])
            with col_d:
                if st.button(
                    "📈 詳細画面へ",
                    key=f"hist_detail_{ticker}_{created}",
                    use_container_width=True,
                ):
                    st.session_state.selected_ticker = ticker
                    st.session_state.page = "detail"
                    st.rerun()
