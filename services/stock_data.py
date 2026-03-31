import yfinance as yf
import pandas as pd
import streamlit as st
from typing import Optional, Dict, List

from services.technical import calculate_rsi, get_trend

# --- ティッカーリスト ---

JP_TICKERS = [
    "7203.T", "6758.T", "9984.T", "8306.T", "6861.T",
    "7974.T", "4063.T", "8035.T", "6367.T", "9432.T",
    "6594.T", "4502.T", "6981.T", "7267.T", "8058.T",
    "6954.T", "3382.T", "5108.T", "4519.T", "8316.T",
]

US_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "JNJ", "V",
    "PG", "UNH", "HD", "MA", "NFLX",
    "INTC", "AMD", "DIS", "BAC", "GS",
]

TICKER_NAMES: Dict[str, str] = {
    "7203.T": "トヨタ自動車",
    "6758.T": "ソニーグループ",
    "9984.T": "ソフトバンクG",
    "8306.T": "三菱UFJ FG",
    "6861.T": "キーエンス",
    "7974.T": "任天堂",
    "4063.T": "信越化学",
    "8035.T": "東京エレクトロン",
    "6367.T": "ダイキン工業",
    "9432.T": "NTT",
    "6594.T": "ニデック",
    "4502.T": "武田薬品",
    "6981.T": "村田製作所",
    "7267.T": "本田技研",
    "8058.T": "三菱商事",
    "6954.T": "ファナック",
    "3382.T": "セブン&アイ",
    "5108.T": "ブリヂストン",
    "4519.T": "中外製薬",
    "8316.T": "三井住友FG",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "META": "Meta",
    "TSLA": "Tesla",
    "JPM": "JPMorgan",
    "JNJ": "J&J",
    "V": "Visa",
    "PG": "P&G",
    "UNH": "UnitedHealth",
    "HD": "Home Depot",
    "MA": "Mastercard",
    "NFLX": "Netflix",
    "INTC": "Intel",
    "AMD": "AMD",
    "DIS": "Disney",
    "BAC": "Bank of America",
    "GS": "Goldman Sachs",
}


@st.cache_data(ttl=300)
def get_market_overview() -> Optional[Dict]:
    """日経平均・ドル円を取得"""
    try:
        nikkei_hist = yf.Ticker("^N225").history(period="5d")
        usdjpy_hist = yf.Ticker("USDJPY=X").history(period="5d")

        result = {}

        if not nikkei_hist.empty and len(nikkei_hist) >= 2:
            curr = nikkei_hist["Close"].iloc[-1]
            prev = nikkei_hist["Close"].iloc[-2]
            result["nikkei"] = {
                "price": curr,
                "change_pct": (curr - prev) / prev * 100,
            }

        if not usdjpy_hist.empty and len(usdjpy_hist) >= 2:
            curr = usdjpy_hist["Close"].iloc[-1]
            prev = usdjpy_hist["Close"].iloc[-2]
            result["usdjpy"] = {
                "price": curr,
                "change_pct": (curr - prev) / prev * 100,
            }

        return result if result else None
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_stock_history(ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """個別銘柄の株価履歴を取得"""
    try:
        df = yf.Ticker(ticker).history(period=period)
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> Optional[Dict]:
    """銘柄の基本情報を取得"""
    try:
        info = yf.Ticker(ticker).info
        return {
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "-"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_single_stock_summary(ticker: str) -> Optional[Dict]:
    """単一銘柄のサマリー（ウォッチリスト用）"""
    try:
        hist = yf.Ticker(ticker).history(period="30d")
        if hist.empty or len(hist) < 2:
            return None

        closes = hist["Close"]
        current = closes.iloc[-1]
        prev = closes.iloc[-2]

        from services.jp_stock_master import JP_STOCK_MASTER
        name = JP_STOCK_MASTER.get(ticker) or TICKER_NAMES.get(ticker, ticker)
        return {
            "ticker": ticker,
            "name": name,
            "price": current,
            "change_pct": (current - prev) / prev * 100,
            "rsi": calculate_rsi(closes),
            "trend": get_trend(closes),
        }
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_rankings(market: str = "JP") -> Dict:
    """バッチ取得でランキングデータを生成（1年データ・6カテゴリ）"""
    tickers = JP_TICKERS if market == "JP" else US_TICKERS

    try:
        raw = yf.download(
            tickers,
            period="1y",
            interval="1d",
            threads=True,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
        raw.sort_index(inplace=True)
    except Exception:
        return _empty_rankings()

    results = []
    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                closes = raw[ticker]["Close"].dropna()
                volumes = raw[ticker]["Volume"].dropna()
            else:
                closes = raw["Close"].dropna()
                volumes = raw["Volume"].dropna()

            if len(closes) < 26 or len(volumes) < 21:
                continue

            current = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            change_pct = (current - prev) / prev * 100

            vol_last = float(volumes.iloc[-1])
            vol_avg20 = float(volumes.iloc[-20:].mean())
            volume_ratio = vol_last / vol_avg20 if vol_avg20 > 0 else 1.0

            rsi = calculate_rsi(closes)

            # トレンド判定：Close > MA25 > MA75 → 上昇 / Close < MA25 < MA75 → 下降 / else → 中立
            ma25 = float(closes.rolling(25).mean().iloc[-1])
            ma75 = float(closes.rolling(75).mean().iloc[-1]) if len(closes) >= 75 else None

            if ma75 is not None:
                if current > ma25 and ma25 > ma75:
                    trend = "上昇"
                elif current < ma25 and ma25 < ma75:
                    trend = "下降"
                else:
                    trend = "中立"
            else:
                trend = "上昇" if current > ma25 else "下降"

            results.append({
                "ticker": ticker,
                "name": TICKER_NAMES.get(ticker, ticker),
                "price": current,
                "change_pct": change_pct,
                "volume": vol_last,
                "volume_ratio": volume_ratio,
                "rsi": rsi,
                "trend": trend,
            })
        except Exception:
            continue

    if not results:
        return _empty_rankings()

    df = pd.DataFrame(results)
    return {
        "gainers":      df.nlargest(3, "change_pct").to_dict("records"),
        "losers":       df.nsmallest(3, "change_pct").to_dict("records"),
        "volume":       df.nlargest(3, "volume").to_dict("records"),
        "volume_ratio": df.nlargest(3, "volume_ratio").to_dict("records"),
        "rsi_low":      df.nsmallest(3, "rsi").to_dict("records"),
        "rsi_high":     df.nlargest(3, "rsi").to_dict("records"),
    }


def _empty_rankings() -> Dict:
    return {
        "gainers": [], "losers": [], "volume": [],
        "volume_ratio": [], "rsi_low": [], "rsi_high": [],
    }


@st.cache_data(ttl=300)
def get_comparison_data(tickers: tuple, period: str = "3mo") -> Dict[str, pd.DataFrame]:
    """複数銘柄の価格データを取得（比較チャート用）。tickers はキャッシュのためタプル渡し"""
    if not tickers:
        return {}
    try:
        tickers_list = list(tickers)
        raw = yf.download(
            tickers_list, period=period, progress=False,
            auto_adjust=True, group_by="ticker",
        )
        result = {}
        for ticker in tickers_list:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    df = raw[ticker].dropna(how="all")
                else:
                    df = raw.dropna(how="all")
                if not df.empty:
                    result[ticker] = df
            except Exception:
                continue
        return result
    except Exception:
        return {}


def search_ticker(query: str, market: str = "JP") -> List[Dict]:
    """後方互換用ラッパー"""
    return search_ticker_fuzzy(query, market)


def search_ticker_fuzzy(query: str, market: str = "JP") -> List[Dict]:
    """ローカル辞書に対するスコア付きファジーマッチング検索"""
    from difflib import SequenceMatcher

    tickers = JP_TICKERS if market == "JP" else US_TICKERS
    q = query.strip()
    if not q:
        return []

    q_lower = q.lower()
    scored: List[Dict] = []

    for ticker in tickers:
        name = TICKER_NAMES.get(ticker, ticker)
        t_lower = ticker.lower().replace(".t", "")
        n_lower = name.lower()
        score = 0

        if q_lower in (t_lower, n_lower, ticker.lower()):
            score = 100
        elif t_lower.startswith(q_lower) or n_lower.startswith(q_lower):
            score = 90
        elif q_lower in t_lower or q_lower in n_lower:
            score = 80
        elif all(c in n_lower for c in q_lower):
            score = 65
        else:
            ratio = max(
                SequenceMatcher(None, q_lower, n_lower).ratio(),
                SequenceMatcher(None, q_lower, t_lower).ratio(),
            )
            if ratio >= 0.45:
                score = int(ratio * 55)

        if score > 0:
            scored.append({"ticker": ticker, "name": name, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


@st.cache_data(ttl=60)
def search_stocks_combined(query: str) -> List[Dict]:
    """日本語名マスター ＋ yfinance Search API による広域検索。
    日本語名（例：ミロク）でも正確にヒットする。
    """
    from services.jp_stock_master import search_jp_master, JP_STOCK_MASTER

    q = query.strip()
    if not q:
        return []

    results: List[Dict] = []
    seen: set = set()

    # ① 4〜5桁の数字 → 東証コードとして直接解決
    if q.isdigit() and len(q) in (4, 5):
        sym = q + ".T"
        name = JP_STOCK_MASTER.get(sym) or TICKER_NAMES.get(sym) or f"{q}（東証上場株）"
        results.append({"symbol": sym, "name": name, "exchange": "東証"})
        seen.add(sym)

    # ② 「数字.T」形式をそのまま受け付ける（例：7203.T）
    if "." in q and q.split(".")[0].isdigit():
        sym = q.upper()
        if sym not in seen:
            name = JP_STOCK_MASTER.get(sym) or TICKER_NAMES.get(sym, sym)
            results.append({"symbol": sym, "name": name, "exchange": "東証"})
            seen.add(sym)

    # ③ 日本語名マスターでファジー検索（日本語入力に完全対応）
    jp_hits = search_jp_master(q)
    for item in jp_hits[:20]:
        sym = item["symbol"]
        if sym not in seen:
            results.append({
                "symbol": sym,
                "name": item["name"],
                "exchange": "東証",
            })
            seen.add(sym)

    # ④ yfinance Search API（米国株・ETF・マスター未収録銘柄）
    try:
        search = yf.Search(q, news_count=0, max_results=20)
        for item in search.quotes:
            sym = item.get("symbol", "")
            if not sym or sym in seen:
                continue
            # 日本株はマスター名を優先、なければAPIの英語名
            if sym.endswith(".T"):
                name = JP_STOCK_MASTER.get(sym) or (
                    item.get("longname") or item.get("shortname") or sym
                )
            else:
                name = item.get("longname") or item.get("shortname") or sym
            exchange_label = _exchange_label(item.get("exchange", ""))
            results.append({"symbol": sym, "name": name, "exchange": exchange_label})
            seen.add(sym)
    except Exception:
        pass

    # ⑤ 旧来のローカルリスト（20銘柄）でも補完
    if len(results) < 3:
        for item in search_ticker_fuzzy(q, "JP") + search_ticker_fuzzy(q, "US"):
            sym = item["ticker"]
            if sym not in seen:
                results.append({
                    "symbol": sym,
                    "name": item["name"],
                    "exchange": "東証" if sym.endswith(".T") else "米国",
                })
                seen.add(sym)

    return results[:25]


def _exchange_label(exchange: str) -> str:
    """取引所コードを日本語ラベルに変換"""
    mapping = {
        "JPX": "東証", "OSA": "大証", "TYO": "東証",
        "NMS": "NASDAQ", "NYQ": "NYSE", "NGM": "NASDAQ",
        "PCX": "NYSE ARCA", "BTS": "BATS",
    }
    return mapping.get(exchange.upper(), exchange) if exchange else ""
