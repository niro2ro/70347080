"""
backtest_page.py
スクリーニングロジックのバックテスト画面（2022-01-01 ～ 2024-12-31）
"""

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

from services.backtest import run_backtest, run_all_modes, BACKTEST_START, BACKTEST_END


# ═══════════════════════════════════════════════════════════════════
#  定数・設定
# ═══════════════════════════════════════════════════════════════════

_MODE_META = {
    "day":   {"label": "⚡ 短期（1日保有）",  "color": "#FF6B6B"},
    "swing": {"label": "📊 中期（5日保有）",  "color": "#4FC3F7"},
    "long":  {"label": "🏔 長期（20日保有）", "color": "#81C784"},
}

_MARKET_LABEL = {"JP": "🇯🇵 日本株", "US": "🇺🇸 米国株"}


# ═══════════════════════════════════════════════════════════════════
#  エントリーポイント
# ═══════════════════════════════════════════════════════════════════

def show_backtest():
    st.markdown("# 📊 バックテスト")
    st.caption(
        f"スクリーニングロジックの有効性を過去データで検証します。"
        f"　対象期間：**{BACKTEST_START} ～ {BACKTEST_END}**"
        f"　｜　未来データは一切使用しません。"
    )

    st.markdown("---")

    # ── 設定パネル ─────────────────────────────────────────────────
    col_mkt, col_mode, col_run = st.columns([1, 2, 2])

    with col_mkt:
        market = st.selectbox(
            "市場",
            ["JP", "US"],
            format_func=lambda x: _MARKET_LABEL[x],
            key="bt_market",
        )

    with col_mode:
        run_mode = st.radio(
            "実行モード",
            ["単一モード", "全モード比較"],
            horizontal=True,
            key="bt_run_mode",
        )

    with col_run:
        if run_mode == "単一モード":
            mode = st.selectbox(
                "戦略モード",
                list(_MODE_META.keys()),
                format_func=lambda x: _MODE_META[x]["label"],
                key="bt_mode",
            )
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        run_btn = st.button(
            "▶ バックテスト実行",
            type="primary",
            use_container_width=True,
            key="bt_run_btn",
        )

    if not run_btn:
        _show_guide()
        return

    # ── 実行 ────────────────────────────────────────────────────────
    if run_mode == "全モード比較":
        _run_all(market)
    else:
        _run_single(market, mode)


# ═══════════════════════════════════════════════════════════════════
#  単一モード実行
# ═══════════════════════════════════════════════════════════════════

def _run_single(market: str, mode: str):
    meta = _MODE_META[mode]
    with st.spinner(f"{meta['label']} のバックテスト実行中…（初回は1～3分程度）"):
        result = run_backtest(market=market, mode=mode)

    if "error" in result:
        st.error(f"❌ {result['error']}")
        return

    st.markdown(f"### {meta['label']}　結果サマリー")

    # ── KPI カード ─────────────────────────────────────────────────
    _show_kpi_cards(result, meta["color"])

    st.markdown("---")

    # ── エクイティカーブ ───────────────────────────────────────────
    if "equity_curve" in result and not result["equity_curve"].empty:
        st.markdown("#### 📈 累積リターン推移（equity curve）")
        _show_equity_curve(result["equity_curve"], meta["color"], meta["label"])

    # ── リターン分布 ───────────────────────────────────────────────
    if "trades_df" in result and not result["trades_df"].empty:
        st.markdown("---")
        _show_return_distribution(result["trades_df"], meta["color"])
        st.markdown("---")
        _show_trade_log(result["trades_df"])


# ═══════════════════════════════════════════════════════════════════
#  全モード比較実行
# ═══════════════════════════════════════════════════════════════════

def _run_all(market: str):
    with st.spinner("全3モードのバックテスト実行中…（初回は3～5分程度）"):
        all_res = run_all_modes(market=market)

    summary = all_res.get("summary", pd.DataFrame())
    results  = all_res.get("results", {})

    st.markdown("### 📋 全モード比較サマリー")

    if not summary.empty:
        # サマリーテーブル（色付き）
        st.dataframe(
            summary.style.format({
                "勝率 (%)":        "{:.1f}",
                "平均リターン (%)": "{:.3f}",
                "最大損失 (%)":    "{:.3f}",
                "シャープレシオ":  "{:.3f}",
            }).background_gradient(
                subset=["勝率 (%)"], cmap="RdYlGn"
            ).background_gradient(
                subset=["シャープレシオ"], cmap="RdYlGn"
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ── 全モードのエクイティカーブを重ねて表示 ─────────────────────
    valid_curves = {
        mode: res["equity_curve"]
        for mode, res in results.items()
        if "equity_curve" in res and not res.get("equity_curve", pd.Series()).empty
    }

    if valid_curves and _PLOTLY:
        st.markdown("---")
        st.markdown("#### 📈 全モード 累積リターン比較")
        fig = go.Figure()
        for mode, curve in valid_curves.items():
            fig.add_trace(go.Scatter(
                x=list(range(len(curve))),
                y=curve.values,
                name=_MODE_META[mode]["label"],
                line=dict(color=_MODE_META[mode]["color"], width=2),
            ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            yaxis_title="累積倍率",
            xaxis_title="トレード番号",
            height=400,
            legend=dict(x=0.01, y=0.99),
        )
        fig.add_hline(y=1.0, line_dash="dash", line_color="#555", annotation_text="基準 (1.0x)")
        st.plotly_chart(fig, use_container_width=True)

    # 各モードの詳細（折りたたみ）
    st.markdown("---")
    for mode, res in results.items():
        meta = _MODE_META[mode]
        with st.expander(f"{meta['label']} 詳細", expanded=False):
            if "error" in res:
                st.warning(res["error"])
            else:
                _show_kpi_cards(res, meta["color"])
                if "trades_df" in res:
                    _show_trade_log(res["trades_df"])


# ═══════════════════════════════════════════════════════════════════
#  KPI カード表示
# ═══════════════════════════════════════════════════════════════════

def _show_kpi_cards(result: dict, color: str):
    total   = result.get("total_trades", 0)
    win_r   = result.get("win_rate", 0) * 100
    avg_r   = result.get("avg_return", 0)
    max_l   = result.get("max_loss", 0)
    sharpe  = result.get("sharpe", 0)
    std     = result.get("std", 0)

    # 色判定
    avg_color    = "#FF4B4B" if avg_r >= 0 else "#4B9EFF"
    win_color    = "#81C784" if win_r >= 50 else "#FF6B6B"
    sharpe_color = "#81C784" if sharpe >= 0.1 else ("#FFD54F" if sharpe >= 0 else "#FF4B4B")
    max_l_color  = "#FF4B4B"

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    def _card(col, label, value, sub="", vcolor="#ECECEC"):
        col.markdown(
            f"""
            <div style='
                background:#1E1E2E;
                border-left:3px solid {color};
                border-radius:8px;
                padding:10px 12px;
                text-align:center;
            '>
                <div style='font-size:0.72rem; color:#888;'>{label}</div>
                <div style='font-size:1.3rem; font-weight:bold; color:{vcolor};'>{value}</div>
                <div style='font-size:0.68rem; color:#666;'>{sub}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _card(c1, "総トレード数",    f"{total:,}",         "件")
    _card(c2, "勝率",            f"{win_r:.1f}%",      f"{result.get('win_count',0)}勝", win_color)
    _card(c3, "平均リターン",    f"{avg_r:+.3f}%",     "1トレードあたり", avg_color)
    _card(c4, "最大損失",        f"{max_l:.3f}%",      "最悪1トレード", max_l_color)
    _card(c5, "標準偏差",        f"{std:.4f}",         "リターンのばらつき")
    _card(c6, "シャープレシオ",  f"{sharpe:.3f}",      "avg÷std", sharpe_color)


# ═══════════════════════════════════════════════════════════════════
#  エクイティカーブ表示
# ═══════════════════════════════════════════════════════════════════

def _show_equity_curve(curve: pd.Series, color: str, label: str):
    if not _PLOTLY:
        st.line_chart(curve)
        return

    x = list(range(len(curve)))
    final = curve.iloc[-1]
    peak  = curve.max()

    fig = go.Figure()

    # 基準線
    fig.add_hline(y=1.0, line_dash="dash", line_color="#555",
                  annotation_text="元本 (1.0x)")

    # エクイティカーブ
    fig.add_trace(go.Scatter(
        x=x, y=curve.values,
        name=label,
        fill="tozeroy",
        fillcolor=f"rgba({_hex_to_rgb(color)},0.08)",
        line=dict(color=color, width=2),
    ))

    # 最終値アノテーション
    fig.add_annotation(
        x=x[-1], y=float(curve.iloc[-1]),
        text=f" 最終: {final:.3f}x",
        showarrow=False,
        font=dict(color=color, size=11),
        xanchor="left",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        yaxis_title="累積倍率",
        xaxis_title="トレード番号",
        height=380,
        showlegend=False,
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 最終値サブキャプション
    pnl_color = "#81C784" if final >= 1 else "#FF4B4B"
    st.markdown(
        f"<div style='font-size:0.8rem; color:#888; text-align:right;'>"
        f"最終累積リターン：<span style='color:{pnl_color}; font-weight:bold;'>{final:.4f}x</span>"
        f"　ピーク：<span style='color:#FFD54F;'>{peak:.4f}x</span>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  リターン分布
# ═══════════════════════════════════════════════════════════════════

def _show_return_distribution(df_t: pd.DataFrame, color: str):
    st.markdown("#### 📊 リターン分布")
    if not _PLOTLY:
        st.bar_chart(df_t["return_pct"])
        return

    rets = df_t["return_pct"]
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=rets,
        nbinsx=40,
        marker_color=color,
        opacity=0.75,
        name="リターン分布",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#FF4B4B",
                  annotation_text=" ゼロライン")
    fig.add_vline(x=float(rets.mean()), line_dash="dot", line_color="#FFD54F",
                  annotation_text=f" 平均 {rets.mean():+.3f}%")
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis_title="リターン (%)",
        yaxis_title="頻度",
        height=300,
        margin=dict(l=40, r=40, t=20, b=40),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
#  トレードログ
# ═══════════════════════════════════════════════════════════════════

def _show_trade_log(df_t: pd.DataFrame):
    st.markdown("#### 📋 トレードログ（直近100件）")

    display = df_t.copy().tail(100).sort_values("date", ascending=False)
    display["date"]       = pd.to_datetime(display["date"]).dt.strftime("%Y-%m-%d")
    display["return_pct"] = display["return_pct"].map("{:+.3f}%".format)
    display["win"]        = display["win"].map({True: "✅ 勝", False: "❌ 負"})
    display["buy_price"]  = display["buy_price"].map("{:,.2f}".format)
    display["sell_price"] = display["sell_price"].map("{:,.2f}".format)

    display = display.rename(columns={
        "date":       "日付",
        "ticker":     "ティッカー",
        "name":       "銘柄名",
        "buy_price":  "買値",
        "sell_price": "売値",
        "return_pct": "リターン",
        "score":      "スコア",
        "win":        "勝敗",
    })

    st.dataframe(
        display[["日付", "ティッカー", "銘柄名", "買値", "売値", "リターン", "スコア", "勝敗"]],
        use_container_width=True,
        hide_index=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  ガイド表示（未実行時）
# ═══════════════════════════════════════════════════════════════════

def _show_guide():
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    for col, (mode, meta) in zip([c1, c2, c3], _MODE_META.items()):
        holding = {"day": 1, "swing": 5, "long": 20}[mode]
        col.markdown(
            f"""
            <div style='
                background:#1E1E2E;
                border-left:3px solid {meta["color"]};
                border-radius:8px;
                padding:14px 16px;
            '>
                <div style='font-size:1rem; font-weight:bold; color:{meta["color"]};
                            margin-bottom:8px;'>{meta["label"]}</div>
                <div style='font-size:0.78rem; color:#AAAACC; line-height:1.8;'>
                    保有期間：<b>{holding}営業日</b><br>
                    スコア条件：<b>5点以上</b><br>
                    最大同時保有：<b>5銘柄</b><br>
                    対象期間：2022 ～ 2024
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.info(
        "💡 バックテストは過去データ（2022〜2024年）でスクリーニングロジックの有効性を検証します。\n\n"
        "- 各営業日にスクリーニングを実行し、スコア上位5銘柄を仮想保有\n"
        "- 保有期間後の終値でリターンを計算（スリッページ・手数料は考慮外）\n"
        "- **シャープレシオ = 平均リターン ÷ 標準偏差**（高いほどリスク効率が良い）\n"
        "- 初回実行は1〜3分程度かかります（結果は1時間キャッシュ）"
    )


# ═══════════════════════════════════════════════════════════════════
#  ユーティリティ
# ═══════════════════════════════════════════════════════════════════

def _hex_to_rgb(hex_color: str) -> str:
    """#RRGGBB → 'R,G,B' 変換"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"
