"""
news_analysis.py
Google News RSS + yfinance のニュースを取得し、
Claude API で感情分析してスクリーニングスコアに統合するエンジン

処理フロー：
  ① get_stock_screening() の上位 N 銘柄を受け取る
  ② Google News RSS + yfinance でニュース取得
  ③ Claude API で感情分析（JSON 形式）
  ④ ai_score = sentiment_score × confidence
  ⑤ mode ごとの重みでテクニカルスコアに加算
  ⑥ final_score で再ソートして返却
"""

import json
import os
import re
import urllib.parse
from typing import Optional

import anthropic
import streamlit as st
import yfinance as yf

# feedparser はオプション依存（なくても RSS 以外で動作）
try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False


# ═══════════════════════════════════════════════════════════════════
#  定数
# ═══════════════════════════════════════════════════════════════════

_CLAUDE_MODEL   = "claude-sonnet-4-6"
_MAX_TOP_N      = 10       # AI 分析を行う上位銘柄数
_MAX_RSS_NEWS   = 5        # RSS から取得するニュース件数
_MAX_YF_NEWS    = 3        # yfinance から取得するニュース件数
_NEWS_TTL       = 600      # ニュースキャッシュ：10 分
_AI_TTL         = 600      # AI 分析キャッシュ：10 分

# mode ごとの AI スコア重み
_AI_WEIGHT: dict = {
    "day":   3,
    "swing": 2,
    "long":  1,
}

# Google News RSS URL テンプレート
_RSS_URL_TMPL = (
    "https://news.google.com/rss/search"
    "?q={query}+株+OR+決算+OR+業績"
    "&hl=ja&gl=JP&ceid=JP:ja"
)


# ═══════════════════════════════════════════════════════════════════
#  メイン公開関数
# ═══════════════════════════════════════════════════════════════════

def enhance_with_ai(screening_results: list, mode: str) -> list:
    """
    スクリーニング結果の上位銘柄にニュース感情分析を統合する。

    Parameters
    ----------
    screening_results : list
        get_stock_screening() の出力（dict のリスト）
    mode : "day" | "swing" | "long"

    Returns
    -------
    list of dict
        {ticker, name, price, technical_score, ai_score,
         final_score, sentiment_score, confidence, summary}
        final_score 降順でソート済み
    """
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return _fallback_no_api(screening_results)

    weight   = _AI_WEIGHT.get(mode, 2)
    top_n    = screening_results[:_MAX_TOP_N]
    enhanced = []

    for item in top_n:
        ticker          = item["ticker"]
        name            = item["name"]
        technical_score = item.get("score", 0)

        # ── ニュース取得 ────────────────────────────────────────────
        news_texts = _fetch_all_news(ticker, name)

        # ── Claude 感情分析 ─────────────────────────────────────────
        analysis = _analyze_with_claude(
            ticker    = ticker,
            name      = name,
            news_text = "\n".join(news_texts),
            api_key   = api_key,
        )

        sentiment = analysis.get("sentiment_score", 0.0)
        confidence = analysis.get("confidence", 0.5)
        ai_score   = round(sentiment * confidence, 4)

        # ── スコア統合 ─────────────────────────────────────────────
        final_score = round(technical_score + ai_score * weight, 4)

        enhanced.append({
            **item,
            "technical_score": technical_score,
            "ai_score":        ai_score,
            "final_score":     final_score,
            "sentiment_score": round(sentiment, 4),
            "confidence":      round(confidence, 4),
            "summary":         analysis.get("summary", "分析データなし"),
            "news_count":      len(news_texts),
        })

    # final_score 降順で再ソート
    enhanced.sort(key=lambda x: x["final_score"], reverse=True)
    return enhanced


# ═══════════════════════════════════════════════════════════════════
#  ニュース取得
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=_NEWS_TTL, show_spinner=False)
def _fetch_all_news(ticker: str, name: str) -> list:
    """
    Google News RSS と yfinance の両方からニュースを取得して統合する。

    Returns
    -------
    list of str  各要素は「タイトル 説明」形式
    """
    news = []
    news.extend(_fetch_rss_news(name))
    news.extend(_fetch_yf_news(ticker))
    return news if news else ["ニュースが見つかりませんでした。"]


@st.cache_data(ttl=_NEWS_TTL, show_spinner=False)
def _fetch_rss_news(name: str) -> list:
    """Google News RSS からニュースを取得"""
    if not _HAS_FEEDPARSER:
        return []

    query = urllib.parse.quote(name)
    url   = _RSS_URL_TMPL.format(query=query)

    try:
        feed    = feedparser.parse(url)
        entries = feed.entries[:_MAX_RSS_NEWS]

        results = []
        for entry in entries:
            title   = entry.get("title", "").strip()
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()
            # タイトルと要約が両方ある場合は「タイトル 要約」形式に統一
            text = f"{title} {summary}".strip() if summary else title
            if text:
                results.append(text[:200])   # 1件あたり最大200文字

        return results

    except Exception:
        return []


@st.cache_data(ttl=_NEWS_TTL, show_spinner=False)
def _fetch_yf_news(ticker: str) -> list:
    """yfinance からニュースタイトルを取得"""
    try:
        yf_ticker = yf.Ticker(ticker)
        news_raw  = yf_ticker.news or []

        results = []
        for item in news_raw[:_MAX_YF_NEWS]:
            # yfinance の news 構造: {title, link, publisher, ...}
            title     = item.get("title", "").strip()
            publisher = item.get("publisher", "")
            if title:
                text = f"{title}（{publisher}）" if publisher else title
                results.append(text[:200])

        return results

    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════
#  Claude 感情分析
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=_AI_TTL, show_spinner=False)
def _analyze_with_claude(
    ticker: str,
    name: str,
    news_text: str,
    api_key: str,
) -> dict:
    """
    ニューステキストを Claude API で感情分析する。

    Parameters
    ----------
    ticker    : 銘柄コード（キャッシュキー）
    name      : 銘柄名
    news_text : ニュース群を改行結合した文字列
    api_key   : Anthropic API キー

    Returns
    -------
    dict  {sentiment_score: float, confidence: float, summary: str}
    """
    # ニュースが空の場合は中立を返す
    if not news_text.strip() or news_text == "ニュースが見つかりませんでした。":
        return _neutral_result("ニュースが取得できませんでした")

    prompt = f"""あなたは金融アナリストです。
以下のニュースから銘柄の短期的な市場心理を分析してください。

【入力】
銘柄名：{name}
ニュース：
{news_text}

【出力（JSONのみ）】
{{
  "sentiment_score": -1.0～1.0,
  "confidence": 0.0～1.0,
  "summary": "100文字以内"
}}

【ルール】
・事実ベースで分析
・中立なら sentiment_score は 0
・過剰な予測は禁止
・必ず上記の JSON 形式のみで出力すること"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()
        return _parse_claude_json(raw_text)

    except anthropic.AuthenticationError:
        return _neutral_result("APIキーエラー")
    except anthropic.RateLimitError:
        return _neutral_result("レート制限")
    except Exception:
        return _neutral_result("API呼び出し失敗")


def _parse_claude_json(raw_text: str) -> dict:
    """
    Claude の出力テキストから JSON を抽出してパースする。
    余分なテキストが付いていても正規表現で JSON 部分を抽出。
    """
    # まず全体をそのままパース
    try:
        data = json.loads(raw_text)
        return _validate_result(data)
    except json.JSONDecodeError:
        pass

    # JSON ブロックを正規表現で抽出（```json ... ``` や { ... } 形式）
    patterns = [
        r"```(?:json)?\s*(\{.*?\})\s*```",   # コードブロック
        r"(\{[^{}]*\"sentiment_score\"[^{}]*\})",  # sentiment_score を含む {}
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return _validate_result(data)
            except json.JSONDecodeError:
                continue

    return _neutral_result("JSON パース失敗")


def _validate_result(data: dict) -> dict:
    """JSON の値を型・範囲チェックして正規化する"""
    sentiment = float(data.get("sentiment_score", 0.0))
    confidence = float(data.get("confidence", 0.5))
    summary    = str(data.get("summary", ""))

    # 範囲クリッピング
    sentiment  = max(-1.0, min(1.0, sentiment))
    confidence = max(0.0,  min(1.0, confidence))
    summary    = summary[:120]   # 最大120文字

    return {
        "sentiment_score": round(sentiment, 4),
        "confidence":      round(confidence, 4),
        "summary":         summary,
    }


def _neutral_result(reason: str) -> dict:
    """中立スコアを返すデフォルト値"""
    return {
        "sentiment_score": 0.0,
        "confidence":      0.0,
        "summary":         reason,
    }


# ═══════════════════════════════════════════════════════════════════
#  API キー未設定時のフォールバック
# ═══════════════════════════════════════════════════════════════════

def _fallback_no_api(screening_results: list) -> list:
    """
    CLAUDE_API_KEY が未設定の場合：
    技術スコアのみで final_score を設定して返す
    """
    result = []
    for item in screening_results[:_MAX_TOP_N]:
        ts = item.get("score", 0)
        result.append({
            **item,
            "technical_score": ts,
            "ai_score":        0.0,
            "final_score":     float(ts),
            "sentiment_score": 0.0,
            "confidence":      0.0,
            "summary":         "APIキー未設定のためAI分析スキップ",
            "news_count":      0,
        })
    return result
