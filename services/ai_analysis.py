import os
from typing import Optional, Dict
import anthropic


def analyze_stock(ticker: str, company_name: str, stock_data: Dict) -> str:
    """Claude APIでテクニカル分析を実行"""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return "⚠️ APIキーが設定されていません。.envファイルに CLAUDE_API_KEY を設定してください。"

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""あなたは株式テクニカル分析の専門家です。以下のデータを基に、スイングトレーダー向けの客観的な分析を行ってください。

【銘柄情報】
銘柄コード: {ticker}
銘柄名: {company_name}
現在値: {stock_data.get('current_price', 'N/A')}
前日比: {stock_data.get('change_pct', 0):.2f}%

【テクニカル指標】
RSI(14): {stock_data.get('rsi', 'N/A'):.1f}（{stock_data.get('rsi_status', '')}）
MACD状況: {stock_data.get('macd_signal', '')}
MA25: {stock_data.get('ma25', 'N/A')}
MA75: {stock_data.get('ma75', 'N/A')}
トレンド: {stock_data.get('trend', '')}

【直近5日の値動き】
{stock_data.get('recent_data', '')}

以下の4点について日本語で分析してください。各項目は200字以内で簡潔にまとめてください。
※売買指示・売買推奨は絶対に行わないでください。

### 1. トレンド分析
現在のトレンドの方向性と強度を客観的に説明してください。

### 2. エントリーの優位性
現在のテクニカル的な特徴から、どのような局面にあるかを説明してください。

### 3. リスク要因
現在のチャート状況から考えられるリスクを説明してください。

### 4. 注視ポイント
今後トレーダーが注目すべき価格水準や指標の変化を説明してください。"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except anthropic.AuthenticationError:
        return "⚠️ APIキーが無効です。.envファイルの CLAUDE_API_KEY を確認してください。"
    except anthropic.RateLimitError:
        return "⚠️ APIレート制限に達しました。しばらく待ってから再試行してください。"
    except Exception as e:
        return f"⚠️ 分析中にエラーが発生しました: {str(e)}"
