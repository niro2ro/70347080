import streamlit as st

from services.stock_data import get_stock_history, get_stock_info, TICKER_NAMES
from services.jp_stock_master import JP_STOCK_MASTER
from services.technical import (
    calculate_rsi,
    calculate_macd,
    calculate_moving_averages,
    get_trend,
    get_rsi_status,
    get_macd_signal,
)
from services.ai_analysis import analyze_stock
from components.charts import create_stock_chart
from database.db import (
    add_to_watchlist,
    remove_from_watchlist,
    is_in_watchlist,
    get_memo,
    save_memo,
    save_analysis_history,
)

PERIOD_OPTIONS = {
    "1ヶ月": "1mo",
    "3ヶ月": "3mo",
    "6ヶ月": "6mo",
    "1年": "1y",
}


def show_detail():
    ticker = st.session_state.get("selected_ticker")

    if not ticker:
        st.error("銘柄が選択されていません")
        if st.button("← メイン画面へ"):
            st.session_state.page = "main"
            st.rerun()
        return

    # 戻るボタン
    col_back, col_ticker_info, col_watch = st.columns([1, 5, 1])

    with col_back:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        if st.button("← 戻る"):
            st.session_state.page = "main"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # データ取得
    with st.spinner(f"データを取得中..."):
        df = get_stock_history(ticker, period="3mo")
        stock_info = get_stock_info(ticker)

    if df is None or df.empty:
        st.error(f"{ticker} のデータを取得できませんでした。ティッカーを確認してください。")
        return

    closes = df["Close"]
    # 日本語名マスター → 旧辞書 → yfinance info → ティッカーコード の順で解決
    company_name = (
        JP_STOCK_MASTER.get(ticker)
        or TICKER_NAMES.get(ticker)
        or (stock_info.get("name") if stock_info else None)
        or ticker
    )

    with col_ticker_info:
        st.markdown(f"## {company_name}")
        st.caption(ticker)

    # ウォッチリスト登録ボタン
    user_id = st.session_state.user_id
    with col_watch:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        in_wl = is_in_watchlist(user_id, ticker)
        if in_wl:
            if st.button("★ 登録済", key="unwatch"):
                remove_from_watchlist(user_id, ticker)
                st.rerun()
        else:
            if st.button("☆ ウォッチ", key="watch"):
                add_to_watchlist(user_id, ticker)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # テクニカル指標計算
    rsi = calculate_rsi(closes)
    macd_line, signal_line, histogram = calculate_macd(closes)
    mas = calculate_moving_averages(closes)
    trend = get_trend(closes)
    rsi_status = get_rsi_status(rsi)
    macd_status = get_macd_signal(macd_line, signal_line)

    current_price = closes.iloc[-1]
    prev_price = closes.iloc[-2]
    change_pct = (current_price - prev_price) / prev_price * 100

    # サマリー指標
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("現在値", f"{current_price:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("RSI (14)", f"{rsi:.1f}", rsi_status, delta_color="off")
    c3.metric("トレンド", trend)
    c4.metric("MACD", macd_status)

    # 期間選択
    selected_label = st.radio(
        "表示期間",
        options=list(PERIOD_OPTIONS.keys()),
        index=1,
        horizontal=True,
        key="chart_period",
    )
    selected_period = PERIOD_OPTIONS[selected_label]

    # 期間が変わった場合は再取得
    if selected_period != "3mo":
        with st.spinner("チャートデータ更新中..."):
            df_chart = get_stock_history(ticker, period=selected_period)
    else:
        df_chart = df

    # チャート
    if df_chart is not None and not df_chart.empty:
        fig = create_stock_chart(df_chart, ticker)
        st.plotly_chart(fig, use_container_width=True)

    # テクニカル指標の詳細テーブル
    st.markdown("---")
    st.markdown("### 📊 テクニカル指標詳細")

    tc1, tc2, tc3 = st.columns(3)

    with tc1:
        st.markdown("**RSI (14)**")
        rsi_icon = "🔴" if rsi >= 70 else ("🟢" if rsi <= 30 else "🟡")
        st.markdown(f"{rsi_icon} **{rsi:.1f}** — {rsi_status}")
        st.progress(rsi / 100)

    with tc2:
        st.markdown("**MACD**")
        curr_macd = macd_line.iloc[-1]
        curr_sig = signal_line.iloc[-1]
        st.markdown(f"MACD: `{curr_macd:.4f}`")
        st.markdown(f"シグナル: `{curr_sig:.4f}`")
        st.markdown(f"→ **{macd_status}**")

    with tc3:
        st.markdown("**移動平均線との乖離**")
        for ma_name, ma_vals in mas.items():
            if ma_vals is not None:
                ma_val = ma_vals.iloc[-1]
                diff_pct = (current_price - ma_val) / ma_val * 100
                arrow = "↑" if diff_pct >= 0 else "↓"
                st.markdown(
                    f"{ma_name}: `{ma_val:,.2f}` "
                    f"({arrow}{abs(diff_pct):.1f}%)"
                )
            else:
                st.markdown(f"{ma_name}: データ不足")

    # 会社情報
    if stock_info:
        with st.expander("📋 会社情報"):
            ic1, ic2 = st.columns(2)
            with ic1:
                if stock_info.get("sector") and stock_info["sector"] != "-":
                    st.write(f"**セクター:** {stock_info['sector']}")
                if stock_info.get("market_cap"):
                    mc = stock_info["market_cap"]
                    if mc >= 1e12:
                        mc_str = f"{mc/1e12:.2f}T"
                    elif mc >= 1e9:
                        mc_str = f"{mc/1e9:.2f}B"
                    else:
                        mc_str = f"{mc/1e6:.2f}M"
                    st.write(f"**時価総額:** {mc_str}")
            with ic2:
                if stock_info.get("pe_ratio"):
                    st.write(f"**PER:** {stock_info['pe_ratio']:.1f}x")
                if stock_info.get("dividend_yield"):
                    st.write(f"**配当利回り:** {stock_info['dividend_yield']*100:.2f}%")

    # AI分析
    st.markdown("---")
    st.markdown("### 🤖 AI分析（Claude）")

    if "ai_result" not in st.session_state:
        st.session_state.ai_result = {}

    if st.button("🔍 AI分析を実行", type="primary"):
        with st.spinner("Claude が分析中...（数秒かかります）"):
            recent_lines = []
            for i in range(max(-5, -len(df)), 0):
                row = df.iloc[i]
                date_str = df.index[i].strftime("%Y-%m-%d")
                recent_lines.append(
                    f"  {date_str}: 始{row['Open']:.2f} 高{row['High']:.2f} "
                    f"安{row['Low']:.2f} 終{row['Close']:.2f}"
                )

            ma25_val = mas["MA25"].iloc[-1] if mas["MA25"] is not None else None
            ma75_val = mas["MA75"].iloc[-1] if mas["MA75"] is not None else None

            stock_data = {
                "current_price": current_price,
                "change_pct": change_pct,
                "rsi": rsi,
                "rsi_status": rsi_status,
                "macd_signal": macd_status,
                "ma25": f"{ma25_val:.2f}" if ma25_val else "N/A",
                "ma75": f"{ma75_val:.2f}" if ma75_val else "N/A",
                "trend": trend,
                "recent_data": "\n".join(recent_lines),
            }

            result = analyze_stock(ticker, company_name, stock_data)
            st.session_state.ai_result[ticker] = result
            save_analysis_history(user_id, ticker, result)

    if ticker in st.session_state.ai_result:
        with st.container():
            st.markdown(st.session_state.ai_result[ticker])
    else:
        st.info(
            "「AI分析を実行」ボタンをクリックすると、Claude によるテクニカル分析が表示されます。\n\n"
            "※ `.env` ファイルに `CLAUDE_API_KEY` が設定されている必要があります。"
        )

    # 銘柄メモ
    st.markdown("---")
    st.markdown("### 📝 銘柄メモ")

    current_memo = get_memo(user_id, ticker)
    memo_text = st.text_area(
        "メモ",
        value=current_memo,
        placeholder="この銘柄に関するメモを自由に入力してください...",
        height=100,
        key=f"memo_{ticker}",
    )

    col_save, _ = st.columns([1, 4])
    with col_save:
        if st.button("💾 メモを保存", key="save_memo"):
            save_memo(user_id, ticker, memo_text)
            st.success("メモを保存しました")
