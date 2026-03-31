import streamlit as st
from services.stock_data import get_market_overview, get_rankings, search_stocks_combined

# サジェストUI用CSS + ランキングヘルプツールチップCSS
_SUGGEST_CSS = """
<style>
/* サジェストボタンをリスト行風に整形 */
div[data-testid="stVerticalBlock"] .suggest-item button {
    text-align: left !important;
    background: #1E1E2E !important;
    border: none !important;
    border-bottom: 1px solid #2D2D3D !important;
    border-radius: 0 !important;
    padding: 8px 14px !important;
    font-size: 0.9rem !important;
    color: #ECECEC !important;
}
div[data-testid="stVerticalBlock"] .suggest-item button:hover {
    background: #2D2D4E !important;
}

/* ─── ランキングタイトル ヘルプアイコン ─── */
.rank-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
}
.rank-title-text {
    font-size: 1.05rem;
    font-weight: 700;
    color: #ECECEC;
}
.help-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
}
.help-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 17px;
    height: 17px;
    border-radius: 50%;
    background: #3A3A5A;
    color: #A0A0C0;
    font-size: 0.68rem;
    font-weight: bold;
    cursor: default;
    border: 1px solid #5A5A7A;
    line-height: 1;
    flex-shrink: 0;
}
.help-tooltip {
    visibility: hidden;
    opacity: 0;
    transition: opacity 0.18s ease;
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    width: 280px;
    background: #1A1A2E;
    border: 1px solid #4A4A6A;
    border-radius: 8px;
    padding: 10px 13px;
    font-size: 0.75rem;
    line-height: 1.65;
    color: #D0D0F0;
    z-index: 9999;
    box-shadow: 0 4px 18px rgba(0,0,0,0.55);
    white-space: pre-line;
}
/* 右端が見切れないよう反転 */
.help-wrap.flip .help-tooltip {
    left: auto;
    right: 0;
}
.help-wrap:hover .help-tooltip {
    visibility: visible;
    opacity: 1;
}
</style>
"""

# ─── 各ランキングのヘルプテキスト ───────────────────────────────
_HELP = {
    "gainers": (
        "📈 値上がり率\n"
        "計算式：\n"
        "  (当日終値 − 前日終値) ÷ 前日終値 × 100\n\n"
        "データ：yfinance 1年間の日足終値\n"
        "比較基準：前営業日終値との1日変化率\n"
        "ソート：降順（上昇率が高い順）TOP3"
    ),
    "losers": (
        "📉 値下がり率\n"
        "計算式：\n"
        "  (当日終値 − 前日終値) ÷ 前日終値 × 100\n\n"
        "データ：yfinance 1年間の日足終値\n"
        "比較基準：前営業日終値との1日変化率\n"
        "ソート：昇順（下落率が大きい順）TOP3"
    ),
    "volume": (
        "📊 出来高\n"
        "計算式：\n"
        "  直近営業日の出来高（株数）\n\n"
        "データ：yfinance Volume（1年間の日足）\n"
        "意味：売買が成立した株式の総数\n"
        "ソート：降順（出来高が多い順）TOP3"
    ),
    "volume_ratio": (
        "🔊 出来高増加率（平均比）\n"
        "計算式：\n"
        "  直近出来高 ÷ 過去20日平均出来高\n\n"
        "例：2.50x ＝ 20日平均の2.5倍\n"
        "データ：yfinance Volume（1年間の日足）\n"
        "意味：平均より大きく売買が増えた銘柄\n"
        "ソート：降順（増加率が高い順）TOP3"
    ),
    "rsi_low": (
        "🟢 RSI低位（売られすぎ候補）\n"
        "計算式：RSI(14) Wilder法\n"
        "  ① 上昇幅・下落幅を計算\n"
        "  ② 指数移動平均(α=1/14)で平滑化\n"
        "  ③ RS = 平均上昇 ÷ 平均下落\n"
        "  ④ RSI = 100 − 100 ÷ (1 + RS)\n\n"
        "目安：RSI 30以下 → 売られすぎ\n"
        "ソート：昇順（RSIが低い順）TOP3"
    ),
    "rsi_high": (
        "🔴 RSI高位（買われすぎ候補）\n"
        "計算式：RSI(14) Wilder法\n"
        "  ① 上昇幅・下落幅を計算\n"
        "  ② 指数移動平均(α=1/14)で平滑化\n"
        "  ③ RS = 平均上昇 ÷ 平均下落\n"
        "  ④ RSI = 100 − 100 ÷ (1 + RS)\n\n"
        "目安：RSI 70以上 → 買われすぎ\n"
        "ソート：降順（RSIが高い順）TOP3"
    ),
}


def show_main():
    st.markdown(_SUGGEST_CSS, unsafe_allow_html=True)

    # ヘッダー
    st.markdown("# 📈 Hiro.exe")
    st.caption(
        f"ようこそ、**{st.session_state.user_name}** さん"
        "　｜　メニューはサイドバーから選択できます"
    )

    # ── マーケット概況 ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 マーケット概況")

    with st.spinner("マーケットデータ取得中..."):
        overview = get_market_overview()

    col1, col2 = st.columns(2)
    with col1:
        if overview and "nikkei" in overview:
            n = overview["nikkei"]
            st.metric("🇯🇵 日経平均", f"¥{n['price']:,.2f}", f"{n['change_pct']:+.2f}%")
        else:
            st.metric("🇯🇵 日経平均", "取得中...", None)
    with col2:
        if overview and "usdjpy" in overview:
            u = overview["usdjpy"]
            st.metric("💴 ドル円 (USD/JPY)", f"¥{u['price']:.2f}", f"{u['change_pct']:+.2f}%")
        else:
            st.metric("💴 ドル円", "取得中...", None)

    # ── 銘柄検索（Google 予測入力スタイル） ──────────────────────
    st.markdown("---")
    st.markdown("### 🔍 銘柄検索")
    st.caption("証券コード・銘柄名・企業名を入力してください（日本株・米国株・ETF 等すべて対応）")

    col_input, col_mkt = st.columns([5, 1])
    with col_mkt:
        search_market = st.selectbox(
            "市場絞り込み",
            ["すべて", "JP", "US"],
            format_func=lambda x: {
                "すべて": "🌐 すべて",
                "JP": "🇯🇵 日本株",
                "US": "🇺🇸 米国株",
            }[x],
            key="search_market_select",
        )
    with col_input:
        query = st.text_input(
            "銘柄を検索",
            placeholder="例：7203　トヨタ　ソフトバンク　NVIDIA　semiconductor...",
            key="search_input",
            label_visibility="collapsed",
        )

    # サジェスト表示（1文字以上で即時）
    if query and query.strip():
        _show_suggestions(query.strip(), search_market)

    # ── ランキング（市場は検索と独立） ─────────────────────────────
    st.markdown("---")

    col_rank_title, col_rank_mkt = st.columns([4, 1])
    with col_rank_title:
        st.markdown("### 🏆 ランキング")
    with col_rank_mkt:
        ranking_market = st.selectbox(
            "ランキング市場",
            ["JP", "US"],
            format_func=lambda x: "🇯🇵 日本株" if x == "JP" else "🇺🇸 米国株",
            key="ranking_market_select",
        )

    st.caption(f"対象：{'日本株' if ranking_market == 'JP' else '米国株'}")

    with st.spinner("ランキングデータ取得中...（初回は30秒ほどかかる場合があります）"):
        rankings = get_rankings(ranking_market)

    col_l, col_r = st.columns(2)
    with col_l:
        _show_ranking_cards(
            "📈 値上がり率 TOP3", rankings.get("gainers", []),
            help_text=_HELP["gainers"],
        )
        st.markdown("")
        _show_ranking_cards(
            "🟢 RSI 低位 TOP3（売られすぎ候補）", rankings.get("rsi_low", []),
            help_text=_HELP["rsi_low"],
        )
    with col_r:
        _show_ranking_cards(
            "📉 値下がり率 TOP3", rankings.get("losers", []),
            help_text=_HELP["losers"], flip=True,
        )
        st.markdown("")
        _show_ranking_cards(
            "🔴 RSI 高位 TOP3（買われすぎ候補）", rankings.get("rsi_high", []),
            help_text=_HELP["rsi_high"], flip=True,
        )

    st.markdown("")
    col_v, col_vr = st.columns(2)
    with col_v:
        _show_ranking_cards(
            "📊 出来高 TOP3", rankings.get("volume", []),
            help_text=_HELP["volume"],
        )
    with col_vr:
        _show_ranking_cards(
            "🔊 出来高増加率 TOP3（平均比）", rankings.get("volume_ratio", []),
            value_key="volume_ratio", value_fmt="{:.2f}x",
            help_text=_HELP["volume_ratio"], flip=True,
        )


# ── サジェスト表示 ──────────────────────────────────────────────

def _show_suggestions(query: str, market_filter: str):
    with st.spinner("検索中..."):
        results = search_stocks_combined(query)

    # 市場フィルター適用
    if market_filter == "JP":
        results = [r for r in results if r["symbol"].endswith(".T")]
    elif market_filter == "US":
        results = [r for r in results if not r["symbol"].endswith(".T")]

    if not results:
        st.markdown(
            "<div style='padding:8px 14px; color:#888; font-size:0.88rem;'>"
            "⚠️ 候補が見つかりません。別のキーワードや証券コードをお試しください。"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # 件数バッジ
    st.markdown(
        f"<div style='font-size:0.78rem; color:#888; padding:2px 4px;'>"
        f"🔍 {len(results)} 件の候補（クリックで詳細画面へ）</div>",
        unsafe_allow_html=True,
    )

    # 枠線付きコンテナ
    st.markdown(
        "<div style='border:1px solid #333; border-radius:8px; overflow:hidden; margin-bottom:8px;'>",
        unsafe_allow_html=True,
    )

    # 10件以上はスクロール（st.container height 指定）
    scroll = len(results) >= 10
    row_height = 46  # px per row (approximate)
    container_h = min(len(results) * row_height, 440)

    ctx = st.container(height=container_h) if scroll else st.container()

    with ctx:
        for r in results:
            sym = r["symbol"]
            name = r["name"]
            exch = r.get("exchange", "")
            exch_tag = (
                f"<span style='font-size:0.72rem; color:#888; margin-left:6px;'>[{exch}]</span>"
                if exch else ""
            )
            label_html = (
                f"<span style='font-size:0.78rem; color:#aaa;'>📊 </span>"
                f"<strong style='color:#4FC3F7;'>{sym}</strong>"
                f"<span style='margin: 0 4px; color:#555;'>：</span>"
                f"<span>{name}</span>"
                f"{exch_tag}"
            )

            # ボタンラベルはプレーンテキスト（HTML非対応）
            btn_label = f"📊  {sym}  ：  {name}" + (f"  [{exch}]" if exch else "")

            st.markdown(
                f"<div style='"
                f"border-bottom:1px solid #2D2D3D;"
                f"'>",
                unsafe_allow_html=True,
            )
            if st.button(
                btn_label,
                key=f"sug_{sym}",
                use_container_width=True,
            ):
                st.session_state.selected_ticker = sym
                st.session_state.page = "detail"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ── ランキングカード ────────────────────────────────────────────

def _show_ranking_cards(
    title: str,
    items: list,
    value_key: str = "change_pct",
    value_fmt: str = "{:+.2f}%",
    help_text: str = "",
    flip: bool = False,
):
    # タイトル行：ヘルプアイコン付き or プレーン
    if help_text:
        flip_cls = " flip" if flip else ""
        # 改行を <br> に変換してHTMLへ埋め込む
        tooltip_html = help_text.replace("\n", "<br>")
        st.markdown(
            f"""
            <div class="rank-title-row">
                <span class="rank-title-text">{title}</span>
                <span class="help-wrap{flip_cls}">
                    <span class="help-icon">?</span>
                    <div class="help-tooltip">{tooltip_html}</div>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"#### {title}")

    if not items:
        st.info("データ取得中...")
        return

    top3 = items[:3]
    cols = st.columns(3)

    for i in range(3):
        with cols[i]:
            if i >= len(top3):
                st.markdown(
                    "<div style='background:#111;padding:10px;border-radius:8px;"
                    "min-height:90px;opacity:0.3;'>—</div>",
                    unsafe_allow_html=True,
                )
                continue

            item = top3[i]
            chg = item.get("change_pct", 0)
            rsi = item.get("rsi", 50)
            trend = item.get("trend", "-")
            border_color = "#FF4B4B" if chg >= 0 else "#4B9EFF"
            chg_color = "#FF4B4B" if chg >= 0 else "#4B9EFF"
            name = item["name"]
            display_name = name[:10] + "…" if len(name) > 10 else name
            display_value = value_fmt.format(item.get(value_key, 0))

            st.markdown(
                f"""
                <div style='
                    background:#1E1E2E;
                    padding:10px 12px;
                    border-radius:8px;
                    border-left:3px solid {border_color};
                    margin-bottom:4px;
                    min-height:90px;
                '>
                    <div style='font-size:0.72rem; color:#888;'>{item['ticker']}</div>
                    <div style='font-weight:bold; font-size:0.88rem; white-space:nowrap;'>
                        {display_name}
                    </div>
                    <div style='font-size:1rem; color:{chg_color}; font-weight:bold;'>
                        {display_value}
                    </div>
                    <div style='font-size:0.72rem; color:#888;'>
                        RSI: {rsi:.0f} | {trend}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "詳細 →",
                key=f"rank_{title}_{item['ticker']}",
                use_container_width=True,
            ):
                st.session_state.selected_ticker = item["ticker"]
                st.session_state.page = "detail"
                st.rerun()
