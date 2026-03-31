import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from services.technical import (
    calculate_rsi_series,
    calculate_macd,
    calculate_moving_averages,
)

# カラーパレット
COLOR_UP = "#FF4B4B"
COLOR_DOWN = "#4B9EFF"
COLOR_MA25 = "#FF9500"
COLOR_MA75 = "#34C759"
COLOR_MA200 = "#AF52DE"
COLOR_RSI = "#FF9500"
COLOR_MACD = "#FF9500"
COLOR_SIGNAL = "#5856D6"
BG_COLOR = "#0E1117"
GRID_COLOR = "#2D2D2D"


def create_stock_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """ローソク足 + MA + RSI + MACD の複合チャートを生成"""
    closes = df["Close"]

    rsi = calculate_rsi_series(closes)
    macd_line, signal_line, histogram = calculate_macd(closes)
    mas = calculate_moving_averages(closes)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.58, 0.21, 0.21],
        subplot_titles=(f"{ticker}  チャート", "RSI (14)", "MACD (12, 26, 9)"),
    )

    # --- ローソク足 ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="株価",
            increasing_line_color=COLOR_UP,
            decreasing_line_color=COLOR_DOWN,
            increasing_fillcolor=COLOR_UP,
            decreasing_fillcolor=COLOR_DOWN,
        ),
        row=1, col=1,
    )

    # --- 移動平均線 ---
    ma_styles = {
        "MA25": (COLOR_MA25, "solid"),
        "MA75": (COLOR_MA75, "solid"),
        "MA200": (COLOR_MA200, "dash"),
    }
    for ma_name, (color, dash) in ma_styles.items():
        if mas[ma_name] is not None:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=mas[ma_name],
                    mode="lines",
                    name=ma_name,
                    line=dict(color=color, width=1.5, dash=dash),
                    opacity=0.9,
                ),
                row=1, col=1,
            )

    # --- RSI ---
    fig.add_trace(
        go.Scatter(
            x=df.index, y=rsi,
            mode="lines", name="RSI",
            line=dict(color=COLOR_RSI, width=2),
        ),
        row=2, col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color=COLOR_UP, opacity=0.6, row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="#666666", opacity=0.4, row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color=COLOR_DOWN, opacity=0.6, row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor=COLOR_UP, opacity=0.05, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor=COLOR_DOWN, opacity=0.05, row=2, col=1)

    # --- MACD ヒストグラム ---
    bar_colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in histogram]
    fig.add_trace(
        go.Bar(
            x=df.index, y=histogram,
            name="ヒストグラム",
            marker_color=bar_colors,
            opacity=0.6,
        ),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=macd_line,
            mode="lines", name="MACD",
            line=dict(color=COLOR_MACD, width=2),
        ),
        row=3, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.index, y=signal_line,
            mode="lines", name="シグナル",
            line=dict(color=COLOR_SIGNAL, width=2),
        ),
        row=3, col=1,
    )

    fig.update_layout(
        height=720,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=BG_COLOR,
        font=dict(color="white", size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=60, b=10),
    )

    for axis in ["xaxis", "xaxis2", "xaxis3", "yaxis", "yaxis2", "yaxis3"]:
        fig.update_layout(**{axis: dict(gridcolor=GRID_COLOR, showgrid=True)})

    fig.update_yaxes(row=2, col=1, range=[0, 100])

    return fig
