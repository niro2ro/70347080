from typing import List, Dict, Optional
import anthropic

from services.config import get_api_key
from services.stock_data import get_stock_history, TICKER_NAMES
from services.technical import (
    calculate_rsi, get_trend, get_rsi_status,
    calculate_macd, get_macd_signal, calculate_moving_averages,
)

SYSTEM_PROMPT = """あなたは株式投資の分析アシスタントです。
スイングトレーダーの判断を支援するために、テクニカル分析や市場動向について客観的に回答します。

【重要なルール】
- 売買の指示・推奨は絶対に行わない
- 「買い」「売り」という断定的な表現は使わない
- 分析・解説・情報提供にとどめる
- 回答は日本語で、簡潔かつ分かりやすく
"""


def build_ticker_context(ticker: str) -> str:
    """選択中銘柄のコンテキスト文字列を生成"""
    hist = get_stock_history(ticker, period="3mo")
    if hist is None or hist.empty:
        return ""

    closes = hist["Close"]
    rsi = calculate_rsi(closes)
    trend = get_trend(closes)
    rsi_status = get_rsi_status(rsi)
    macd_line, signal_line, _ = calculate_macd(closes)
    macd_status = get_macd_signal(macd_line, signal_line)
    mas = calculate_moving_averages(closes)

    current = closes.iloc[-1]
    prev = closes.iloc[-2]
    change_pct = (current - prev) / prev * 100

    ma_lines = []
    for ma_name, ma_vals in mas.items():
        if ma_vals is not None:
            val = ma_vals.iloc[-1]
            diff = (current - val) / val * 100
            ma_lines.append(f"  {ma_name}: {val:,.2f} ({diff:+.1f}%)")

    name = TICKER_NAMES.get(ticker, ticker)

    return f"""【現在表示中の銘柄データ】
銘柄: {name} ({ticker})
現在値: {current:,.2f} ({change_pct:+.2f}%)
RSI(14): {rsi:.1f}（{rsi_status}）
トレンド: {trend}
MACD: {macd_status}
移動平均:
{chr(10).join(ma_lines)}
"""


def chat(
    messages: List[Dict[str, str]],
    ticker: Optional[str] = None,
) -> str:
    """Claude に対してチャット形式で問い合わせ"""
    api_key = get_api_key()
    if not api_key:
        return "⚠️ APIキーが設定されていません。Streamlit secrets または .env ファイルに ANTHROPIC_API_KEY を設定してください。"

    system = SYSTEM_PROMPT
    if ticker:
        ctx = build_ticker_context(ticker)
        if ctx:
            system += f"\n\n{ctx}"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system,
            messages=messages,
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        return "⚠️ APIキーが無効です。"
    except anthropic.RateLimitError:
        return "⚠️ レート制限に達しました。しばらく待ってから再試行してください。"
    except Exception as e:
        return f"⚠️ エラーが発生しました: {str(e)}"
