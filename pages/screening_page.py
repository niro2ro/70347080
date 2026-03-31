"""
screening_page.py
戦略別スコアリングスクリーニング画面
"""

import streamlit as st
from services.screening import get_stock_screening
from services.news_analysis import enhance_with_ai


# ═══════════════════════════════════════════════════════════════════
#  モード定義
# ═══════════════════════════════════════════════════════════════════

_MODES = {
    "day": {
        "label":    "⚡ 短期",
        "subtitle": "当日の勢い重視 ─ 出来高急増・上昇率・RSI 傾きを評価",
        "score_items": [
            ("出来高急増（上位 20%）",   "+3"),
            ("上昇率高い（上位 30%）",   "+2"),
            ("RSI が上昇中（3 日傾き）", "+1"),
            ("上昇トレンド（MA25 > MA75）", "+1"),
            ("出来高増加トレンド（5 日 > 20 日平均）", "+1"),
        ],
        "risk_label":  "risk < 0.6",
        "score_max":   8,
        "color":       "#FF6B6B",
    },
    "swing": {
        "label":    "📊 中期",
        "subtitle": "数日～数週間の反発狙い ─ RSI 低位・MA 上向きを評価",
        "score_items": [
            ("RSI 低位（下位 40%：売られすぎ候補）", "+2"),
            ("MA25 が上向き（5 日傾き）",             "+2"),
            ("トレンド強度 > 1%（MA25/MA75 比）",    "+2"),
            ("出来高が中程度以上（上位 50%）",        "+1"),
            ("MA25 乖離 < 5%（乖離小さい）",          "+1"),
        ],
        "risk_label":  "risk < 0.4",
        "score_max":   8,
        "color":       "#4FC3F7",
    },
    "long": {
        "label":    "🏔 長期",
        "subtitle": "安定上昇トレンド ─ 低ボラ・強トレンド・小ドローダウンを評価",
        "score_items": [
            ("トレンド強い上昇（trend_strength > 3%）", "+3"),
            ("低ボラティリティ（日次標準偏差 < 3%）",  "+2"),
            ("ドローダウン小（-20% 以内）",             "+2"),
            ("MA25 上向き（5 日傾き）",                 "+1"),
            ("RSI 中立ゾーン（40～60%ile）",            "+1"),
        ],
        "risk_label":  "risk < 0.3",
        "score_max":   9,
        "color":       "#81C784",
    },
}

# ─── RSI カラー ────────────────────────────────────────────────────
def _rsi_color(rsi: float) -> str:
    if rsi >= 70:
        return "#FF4B4B"
    if rsi <= 30:
        return "#4B9EFF"
    return "#ECECEC"

# ─── 前日比カラー ──────────────────────────────────────────────────
def _chg_color(chg: float) -> str:
    return "#FF4B4B" if chg >= 0 else "#4B9EFF"

# ─── スコアバー HTML ───────────────────────────────────────────────
def _score_bar(score: int, max_score: int, color: str) -> str:
    pct = min(score / max_score * 100, 100)
    return (
        f"<div style='background:#2D2D3D;border-radius:4px;height:6px;margin-top:2px;'>"
        f"<div style='width:{pct:.0f}%;height:6px;border-radius:4px;"
        f"background:{color};'></div></div>"
    )

# ─── 詳細画面遷移コールバック ─────────────────────────────────────
def _go_to_detail(ticker: str):
    st.session_state.selected_ticker = ticker
    st.session_state.page = "detail"


# ═══════════════════════════════════════════════════════════════════
#  メイン描画
# ═══════════════════════════════════════════════════════════════════

def show_screening():
    st.markdown("# 🔍 スクリーニング")
    st.caption(
        "戦略モードを選択して実行してください。"
        "　データは **5 分キャッシュ**・スコア 5 点以上の銘柄を上位 20 件表示します。"
    )

    # ── モード選択タブ ──────────────────────────────────────────────
    tab_labels = [info["label"] for info in _MODES.values()]
    tabs = st.tabs(tab_labels)

    selected_mode = st.session_state.get("sc_mode", "swing")

    for tab, (mode_key, mode_info) in zip(tabs, _MODES.items()):
        with tab:
            # モード説明カード（f-string 内バックスラッシュ禁止対策：変数に切り出し）
            mc      = mode_info["color"]
            m_sub   = mode_info["subtitle"]
            m_risk  = mode_info["risk_label"]
            m_max   = mode_info["score_max"]
            score_rows = "　".join(
                f"<span style='color:#DDDDFF;'>{item}</span> "
                f"<span style='color:{mc};font-weight:bold;'>{pts}</span>"
                for item, pts in mode_info["score_items"]
            )
            st.markdown(
                f"""
                <div style='
                    background:#1E1E2E;
                    border-left: 3px solid {mc};
                    border-radius: 6px;
                    padding: 10px 14px;
                    margin-bottom: 10px;
                '>
                    <div style='font-weight:bold; color:{mc};
                                font-size:0.95rem; margin-bottom:6px;'>
                        {m_sub}
                    </div>
                    <div style='font-size:0.78rem; color:#AAAACC; line-height:1.7;'>
                        {score_rows}
                        <br>リスクフィルター：<span style='color:#FFD54F;'>{m_risk}</span>
                        　最高スコア：<span style='color:#FFD54F;'>{m_max} 点</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 設定行
            col_mkt, col_ai, col_run = st.columns([1, 1.4, 2])
            with col_mkt:
                market = st.selectbox(
                    "市場",
                    ["JP", "US"],
                    format_func=lambda x: "🇯🇵 日本株" if x == "JP" else "🇺🇸 米国株",
                    key=f"sc_market_{mode_key}",
                )
            with col_ai:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                ai_enabled = st.toggle(
                    "🧠 AIニュース分析",
                    value=False,
                    key=f"sc_ai_{mode_key}",
                    help=(
                        "Claude AI + Google News RSS で上位10銘柄のニュース感情分析を行い、\n"
                        "テクニカルスコアに加算します（追加で30秒〜1分かかります）"
                    ),
                )
            with col_run:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                run = st.button(
                    f"🔍 スクリーニング実行（{mode_info['label']}）",
                    key=f"sc_run_{mode_key}",
                    type="primary",
                    use_container_width=True,
                )

            if not run:
                st.info("「スクリーニング実行」をクリックすると結果が表示されます。")
                continue

            # ── テクニカルスクリーニング ────────────────────────────
            with st.spinner("全銘柄データを取得・分析中…（初回は30秒ほどかかる場合があります）"):
                results = get_stock_screening(market=market, mode=mode_key)

            # ── AI ニュース強化（トグル ON の場合）────────────────
            if ai_enabled and results:
                with st.spinner(
                    "🧠 AIニュース分析中…上位10銘柄のニュースを取得してClaudeで感情分析しています"
                ):
                    results = enhance_with_ai(results, mode=mode_key)
                _show_results_ai(results, mode_info)
            else:
                _show_results(results, mode_info)


# ═══════════════════════════════════════════════════════════════════
#  結果テーブル描画
# ═══════════════════════════════════════════════════════════════════

def _show_results(results: list, mode_info: dict):
    st.markdown("---")

    if not results:
        st.warning(
            "条件を満たす銘柄が見つかりませんでした。\n\n"
            "・スコア 5 点以上の銘柄がゼロ件です。\n"
            "・別の市場やモードを試してみてください。"
        )
        return

    st.markdown(
        f"<div style='font-size:1.1rem; font-weight:bold; margin-bottom:8px;'>"
        f"📋 結果：<span style='color:{mode_info['color']};'>{len(results)} 銘柄</span>"
        f"　<span style='font-size:0.78rem; color:#888;'>"
        f"（score ≥ 5 / スコア・出来高増加率 降順）</span></div>",
        unsafe_allow_html=True,
    )

    # ── ヘッダー ──────────────────────────────────────────────────
    H = [1.6, 2.2, 1.3, 1.2, 1.3, 1.0, 1.6, 1.4, 1.2]
    h0, h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(H)
    header_style = "font-weight:bold; font-size:0.82rem; color:#AAAACC;"
    h0.markdown(f"<span style='{header_style}'>ティッカー</span>", unsafe_allow_html=True)
    h1.markdown(f"<span style='{header_style}'>銘柄名</span>",     unsafe_allow_html=True)
    h2.markdown(f"<span style='{header_style}'>現在値</span>",     unsafe_allow_html=True)
    h3.markdown(f"<span style='{header_style}'>前日比</span>",     unsafe_allow_html=True)
    h4.markdown(f"<span style='{header_style}'>出来高比</span>",   unsafe_allow_html=True)
    h5.markdown(f"<span style='{header_style}'>RSI</span>",        unsafe_allow_html=True)
    h6.markdown(f"<span style='{header_style}'>トレンド</span>",   unsafe_allow_html=True)
    h7.markdown(f"<span style='{header_style}'>スコア</span>",     unsafe_allow_html=True)
    h8.markdown(f"<span style='{header_style}'>リスク</span>",     unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0; border-color:#333;'>", unsafe_allow_html=True)

    # ── データ行 ──────────────────────────────────────────────────
    score_max   = mode_info["score_max"]
    mode_color  = mode_info["color"]

    for idx, row in enumerate(results):
        c0, c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(H)

        # ティッカー（詳細ボタン）
        with c0:
            st.button(
                row["ticker"],
                key=f"sc_btn_{row['ticker']}_{idx}",
                on_click=_go_to_detail,
                args=(row["ticker"],),
                use_container_width=True,
                help="クリックで詳細画面へ",
            )

        # 銘柄名
        name = row["name"]
        c1.write(name[:15] + "…" if len(name) > 15 else name)

        # 現在値
        price = row["price"]
        c2.write(f"{'¥' if '.' in row['ticker'] else '$'}{price:,.0f}")

        # 前日比
        chg = row["change_pct"]
        c3.markdown(
            f"<span style='color:{_chg_color(chg)};font-weight:bold;'>{chg:+.2f}%</span>",
            unsafe_allow_html=True,
        )

        # 出来高比（平均比）
        vr = row["volume_ratio"]
        vr_color = "#FFD54F" if vr >= 2.0 else ("#81C784" if vr >= 1.5 else "#ECECEC")
        c4.markdown(
            f"<span style='color:{vr_color};'>{vr:.2f}x</span>",
            unsafe_allow_html=True,
        )

        # RSI
        rsi = row["rsi"]
        c5.markdown(
            f"<span style='color:{_rsi_color(rsi)};'>{rsi:.0f}</span>",
            unsafe_allow_html=True,
        )

        # トレンド
        trend = row["trend"]
        trend_color = {
            "強い上昇": "#FF4B4B",
            "やや上昇": "#FFB74D",
            "強い下降": "#4B9EFF",
            "やや下降": "#90A4AE",
        }.get(trend, "#ECECEC")
        c6.markdown(
            f"<span style='color:{trend_color};'>{trend}</span>",
            unsafe_allow_html=True,
        )

        # スコア（数値 + バー）
        score = int(row["score"])
        bar_html = _score_bar(score, score_max, mode_color)
        c7.markdown(
            f"<span style='font-weight:bold; color:{mode_color};'>{score}</span>"
            f"<span style='color:#666;font-size:0.72rem;'>/{score_max}</span>"
            f"{bar_html}",
            unsafe_allow_html=True,
        )

        # リスク
        risk = row["risk"]
        risk_color = "#FF4B4B" if risk >= 0.3 else ("#FFD54F" if risk >= 0.15 else "#81C784")
        c8.markdown(
            f"<span style='color:{risk_color};'>{risk:.3f}</span>",
            unsafe_allow_html=True,
        )

    # ── 凡例フッター ──────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='font-size:0.72rem; color:#666; line-height:2;'>
        💡 凡例 ─
        <b>出来高比</b>：過去20日平均比
        <b>RSI</b>：<span style='color:#FF4B4B;'>赤 ≥70（買われすぎ）</span> /
                    <span style='color:#4B9EFF;'>青 ≤30（売られすぎ）</span>
        <b>リスク</b>：<span style='color:#81C784;'>緑（低）</span> /
                       <span style='color:#FFD54F;'>黄（中）</span> /
                       <span style='color:#FF4B4B;'>赤（高）</span> /
                       算出式：|最大ドローダウン| × 日次ボラティリティ
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  AI 強化結果テーブル描画
# ═══════════════════════════════════════════════════════════════════

def _show_results_ai(results: list, mode_info: dict):
    """enhance_with_ai() の出力を表示する専用関数"""
    st.markdown("---")

    if not results:
        st.warning("条件を満たす銘柄が見つかりませんでした。")
        return

    mode_color = mode_info["color"]
    score_max  = mode_info["score_max"]

    st.markdown(
        f"<div style='font-size:1.1rem; font-weight:bold; margin-bottom:4px;'>"
        f"🧠 AI強化スクリーニング結果：<span style='color:{mode_color};'>{len(results)} 銘柄</span>"
        f"　<span style='font-size:0.78rem; color:#888;'>（final_score 降順）</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "final_score = テクニカルスコア + AIスコア × 重み　｜　"
        "AIスコア = sentiment_score × confidence"
    )

    # ── ヘッダー ──────────────────────────────────────────────────
    # 列構成：ticker / name / price / chg / rsi / trend / tech / ai / final
    AH = [1.5, 2.0, 1.2, 1.0, 0.9, 1.4, 1.1, 1.1, 1.3]
    ah = st.columns(AH)
    hs = "font-weight:bold; font-size:0.82rem; color:#AAAACC;"
    for col, label in zip(ah, [
        "ティッカー", "銘柄名", "現在値", "前日比",
        "RSI", "トレンド", "技術★", "AI 🧠", "総合⭐"
    ]):
        col.markdown(f"<span style='{hs}'>{label}</span>", unsafe_allow_html=True)

    st.markdown("<hr style='margin:4px 0; border-color:#333;'>", unsafe_allow_html=True)

    # ── データ行 ──────────────────────────────────────────────────
    for idx, row in enumerate(results):
        c0, c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(AH)

        # ティッカーボタン
        with c0:
            st.button(
                row["ticker"],
                key=f"ai_btn_{row['ticker']}_{idx}",
                on_click=_go_to_detail,
                args=(row["ticker"],),
                use_container_width=True,
                help="クリックで詳細画面へ",
            )

        # 銘柄名
        name = row["name"]
        c1.write(name[:14] + "…" if len(name) > 14 else name)

        # 現在値
        ccy = "¥" if "." in row["ticker"] else "$"
        c2.write(f"{ccy}{row['price']:,.0f}")

        # 前日比
        chg = row.get("change_pct", 0)
        c3.markdown(
            f"<span style='color:{_chg_color(chg)};font-weight:bold;'>{chg:+.2f}%</span>",
            unsafe_allow_html=True,
        )

        # RSI
        rsi = row.get("rsi", 50)
        c4.markdown(
            f"<span style='color:{_rsi_color(rsi)};'>{rsi:.0f}</span>",
            unsafe_allow_html=True,
        )

        # トレンド
        trend = row.get("trend", "-")
        tc = {"強い上昇": "#FF4B4B", "やや上昇": "#FFB74D",
               "強い下降": "#4B9EFF", "やや下降": "#90A4AE"}.get(trend, "#ECECEC")
        c5.markdown(
            f"<span style='color:{tc};'>{trend}</span>",
            unsafe_allow_html=True,
        )

        # テクニカルスコア + バー
        ts = int(row.get("technical_score", row.get("score", 0)))
        c6.markdown(
            f"<span style='font-weight:bold; color:{mode_color};'>{ts}</span>"
            f"<span style='color:#555; font-size:0.72rem;'>/{score_max}</span>"
            f"{_score_bar(ts, score_max, mode_color)}",
            unsafe_allow_html=True,
        )

        # AI スコア（感情を色で表現）
        ai  = row.get("ai_score", 0.0)
        conf = row.get("confidence", 0.0)
        ai_color = (
            "#FF4B4B" if ai > 0.2 else
            "#4B9EFF" if ai < -0.2 else
            "#888888"
        )
        ai_icon = "▲" if ai > 0.05 else ("▼" if ai < -0.05 else "─")
        c7.markdown(
            f"<span style='color:{ai_color}; font-weight:bold;'>{ai_icon} {ai:+.3f}</span>"
            f"<div style='font-size:0.65rem; color:#666;'>確度 {conf:.0%}</div>",
            unsafe_allow_html=True,
        )

        # 最終スコア（強調表示）
        fs = row.get("final_score", float(ts))
        fs_color = "#FFD700" if fs >= ts + 0.3 else ("#FF6B6B" if fs < ts - 0.3 else mode_color)
        c8.markdown(
            f"<span style='font-size:1.1rem; font-weight:bold; color:{fs_color};'>"
            f"{fs:.2f}</span>",
            unsafe_allow_html=True,
        )

        # ── ニュース要約（行下に小さく表示）──────────────────────
        summary = row.get("summary", "")
        news_n  = row.get("news_count", 0)
        if summary and summary not in ("分析データなし", "APIキー未設定のためAI分析スキップ"):
            sent = row.get("sentiment_score", 0)
            sent_label = (
                f"<span style='color:#FF4B4B;'>ポジティブ</span>" if sent > 0.1 else
                f"<span style='color:#4B9EFF;'>ネガティブ</span>" if sent < -0.1 else
                f"<span style='color:#888;'>中立</span>"
            )
            st.markdown(
                f"<div style='font-size:0.72rem; color:#AAAACC; padding:2px 4px 6px 8px;"
                f"border-left:2px solid #3A3A5A; margin-bottom:4px;'>"
                f"📰 {sent_label}　{summary}"
                f"<span style='color:#555; margin-left:6px;'>（取得{news_n}件）</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── フッター凡例 ───────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='font-size:0.72rem; color:#666; line-height:2;'>
        💡 凡例 ─
        <b>技術★</b>：テクニカルスコア（MA・RSI・出来高等）
        <b>AI 🧠</b>：<span style='color:#FF4B4B;'>▲正（好材料）</span> /
                       <span style='color:#4B9EFF;'>▼負（悪材料）</span> /
                       <span style='color:#888;'>─中立</span>
                       ＝ sentiment × confidence
        <b>総合⭐</b>：<span style='color:#FFD700;'>金色（AIが大幅加点）</span>
                　ニュース感情分析はあくまで補助情報です。投資判断は自己責任で行ってください。
        </div>
        """,
        unsafe_allow_html=True,
    )
