import streamlit as st
from services.ai_chat import chat
from services.stock_data import TICKER_NAMES


def show_ai_chat():
    st.markdown("# 💬 AI質問（Claude）")

    ticker = st.session_state.get("selected_ticker")

    # コンテキスト表示
    col_ctx, col_clear = st.columns([4, 1])
    with col_ctx:
        if ticker:
            name = TICKER_NAMES.get(ticker, ticker)
            st.info(f"📌 銘柄コンテキスト自動連携中：**{name}（{ticker}）**\n\n"
                    f"「この銘柄のリスクは？」のように質問できます。")
        else:
            st.info("銘柄コンテキストなし（株式詳細画面からAI質問を使うと銘柄データが自動連携されます）")

    with col_clear:
        st.markdown("<div style='padding-top:8px'>", unsafe_allow_html=True)
        if st.button("🗑️ 履歴クリア", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # セッション初期化
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    # コンテキスト銘柄が変わったら履歴クリアを提案
    if "chat_context_ticker" not in st.session_state:
        st.session_state.chat_context_ticker = ticker
    elif st.session_state.chat_context_ticker != ticker and st.session_state.chat_history:
        st.warning(
            f"銘柄が変わりました（{st.session_state.chat_context_ticker} → {ticker}）。"
            "「履歴クリア」で会話をリセットできます。"
        )
        st.session_state.chat_context_ticker = ticker

    st.markdown("---")

    # 過去のメッセージを表示
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 入力欄
    if prompt := st.chat_input("質問を入力してください...（例：このRSIの水準はどう評価できますか？）"):
        # ユーザーメッセージ追加
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Claude に問い合わせ（会話履歴をそのまま渡す）
        with st.chat_message("assistant"):
            with st.spinner("考え中..."):
                response = chat(
                    messages=st.session_state.chat_history,
                    ticker=ticker,
                )
            st.markdown(response)

        st.session_state.chat_history.append({"role": "assistant", "content": response})

    # 使用例
    if not st.session_state.chat_history:
        st.markdown("#### 💡 質問例")
        examples = [
            "このRSIの水準はどう評価できますか？",
            "今のトレンドの強さはどの程度ですか？",
            "MACDゴールデンクロスの意味を教えてください",
            "この銘柄の現在のリスク要因は何ですか？",
            "移動平均線の乖離率はどう読めばいいですか？",
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.chat_history.append({"role": "user", "content": ex})
                    with st.spinner("考え中..."):
                        response = chat(
                            messages=[{"role": "user", "content": ex}],
                            ticker=ticker,
                        )
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": response}
                    )
                    st.rerun()
