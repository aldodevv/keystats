"""
Real-Time Indonesian Stock & Financial News Service with Sentiment and Catalyst Tagging.
Extracts live headlines from verified financial sources (KONTAN, IDNFinancials, Bisnis, CNBC, Bareksa)
via Google News RSS with zero external API key requirements.
"""

import time
import threading
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from email.utils import parsedate_to_datetime

from app.models.news import NewsItem, NewsResponse, NewsSentiment, SentimentSummary


class NewsService:
    def __init__(self, cache_ttl_seconds: int = 600):
        self._cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, NewsResponse]] = {}
        self._lock = threading.Lock()

    def _format_time_ago(self, dt: Optional[datetime]) -> str:
        if not dt:
            return ""
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "baru saja"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} menit lalu"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} jam lalu"
        else:
            days = seconds // 86400
            return f"{days} hari lalu"

    def _analyze_sentiment_and_tags(self, title: str) -> Tuple[NewsSentiment, List[str]]:
        t_lower = title.lower()

        bullish_keywords = [
            "naik", "menguat", "laba", "untung", "kinerja positif", "dividen",
            "rekomendasi beli", "tumbuh", "rekor", "lonjakan", "melejit", "target naik",
            "akumulasi", "ekspansi", "surplus", "rebound", "moncer", "terkerek"
        ]
        bearish_keywords = [
            "turun", "anjlok", "merosot", "rugi", "tekanan", "koreksi", "ambles",
            "waspada", "lemah", "jual", "sell", "beban", "utang", "macet",
            "denda", "suspensi", "defisit", "ambruk", "terpuruk"
        ]

        bull_score = sum(1 for w in bullish_keywords if w in t_lower)
        bear_score = sum(1 for w in bearish_keywords if w in t_lower)

        if bull_score > bear_score:
            sentiment = NewsSentiment.BULLISH
        elif bear_score > bull_score:
            sentiment = NewsSentiment.BEARISH
        else:
            sentiment = NewsSentiment.NEUTRAL

        tags = []
        if any(w in t_lower for w in ["dividen", "cum-date", "ex-date", "yield"]):
            tags.append("Dividen")
        if any(w in t_lower for w in ["laba", "rugi", "pendapatan", "kinerja", "lapkeu", "kuartal"]):
            tags.append("Laporan Keuangan")
        if any(w in t_lower for w in ["rekomendasi", "target harga", "analis", "potensi"]):
            tags.append("Rekomendasi Analis")
        if any(w in t_lower for w in ["akuisisi", "merger", "ekspansi", "investasi"]):
            tags.append("Aksi Korporasi")
        if any(w in t_lower for w in ["kredit", "dpk", "npl", "nim", "bunga"]):
            tags.append("Perbankan / Kredit")
        if any(w in t_lower for w in ["asing", "net buy", "net sell", "outflow", "inflow"]):
            tags.append("Foreign Flow")

        return sentiment, tags

    def _fetch_rss(self, url: str) -> List[Dict[str, str]]:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                raw_items = []
                for item in root.findall(".//item"):
                    title = item.findtext("title") or ""
                    link = item.findtext("link") or ""
                    pub_date = item.findtext("pubDate") or ""
                    source = item.findtext("source") or ""
                    if not source and " - " in title:
                        source = title.split(" - ")[-1].strip()
                    raw_items.append({
                        "title": title,
                        "link": link,
                        "pub_date": pub_date,
                        "source": source
                    })
                return raw_items
        except Exception:
            return []

    def get_ticker_news(self, ticker: str, max_items: int = 15) -> NewsResponse:
        clean_ticker = ticker.upper().replace(".JK", "").strip()
        cache_key = f"ticker:{clean_ticker}:{max_items}"

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached:
                cached_time, resp = cached
                if time.time() - cached_time < self._cache_ttl:
                    return resp

        # Query Google News RSS for IDX stock
        query_url = f"https://news.google.com/rss/search?q={clean_ticker}+saham+when:7d&hl=id&gl=ID&ceid=ID:id"
        raw_items = self._fetch_rss(query_url)

        items: List[NewsItem] = []
        bullish_cnt = 0
        bearish_cnt = 0
        neutral_cnt = 0

        for r in raw_items[:max_items]:
            dt = None
            if r["pub_date"]:
                try:
                    dt = parsedate_to_datetime(r["pub_date"])
                except Exception:
                    pass

            sentiment, tags = self._analyze_sentiment_and_tags(r["title"])
            if sentiment == NewsSentiment.BULLISH:
                bullish_cnt += 1
            elif sentiment == NewsSentiment.BEARISH:
                bearish_cnt += 1
            else:
                neutral_cnt += 1

            items.append(
                NewsItem(
                    title=r["title"],
                    link=r["link"],
                    source=r["source"] or "Market News",
                    pub_date=r["pub_date"],
                    time_ago=self._format_time_ago(dt),
                    sentiment=sentiment,
                    catalyst_tags=tags,
                    ticker=clean_ticker
                )
            )

        total = len(items)
        bullish_pct = round((bullish_cnt / max(1, total)) * 100, 1)

        if bullish_cnt > bearish_cnt:
            overall = NewsSentiment.BULLISH
        elif bearish_cnt > bullish_cnt:
            overall = NewsSentiment.BEARISH
        else:
            overall = NewsSentiment.NEUTRAL

        summary = SentimentSummary(
            bullish_count=bullish_cnt,
            bearish_count=bearish_cnt,
            neutral_count=neutral_cnt,
            bullish_percentage=bullish_pct,
            overall_sentiment=overall
        )

        resp = NewsResponse(
            query_ticker=clean_ticker,
            total_items=total,
            sentiment_summary=summary,
            news=items,
            fetched_at=datetime.now().strftime("%d %b %Y, %H:%M WIB")
        )

        with self._lock:
            self._cache[cache_key] = (time.time(), resp)

        return resp

    def get_market_news(self, max_items: int = 20) -> NewsResponse:
        cache_key = f"market_overview:{max_items}"

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached:
                cached_time, resp = cached
                if time.time() - cached_time < self._cache_ttl:
                    return resp

        query_url = "https://news.google.com/rss/search?q=saham+IHSG+OR+bursa+efek+indonesia+when:3d&hl=id&gl=ID&ceid=ID:id"
        raw_items = self._fetch_rss(query_url)

        items: List[NewsItem] = []
        bullish_cnt = 0
        bearish_cnt = 0
        neutral_cnt = 0

        for r in raw_items[:max_items]:
            dt = None
            if r["pub_date"]:
                try:
                    dt = parsedate_to_datetime(r["pub_date"])
                except Exception:
                    pass

            sentiment, tags = self._analyze_sentiment_and_tags(r["title"])
            if sentiment == NewsSentiment.BULLISH:
                bullish_cnt += 1
            elif sentiment == NewsSentiment.BEARISH:
                bearish_cnt += 1
            else:
                neutral_cnt += 1

            items.append(
                NewsItem(
                    title=r["title"],
                    link=r["link"],
                    source=r["source"] or "Market News",
                    pub_date=r["pub_date"],
                    time_ago=self._format_time_ago(dt),
                    sentiment=sentiment,
                    catalyst_tags=tags,
                    ticker="IHSG"
                )
            )

        total = len(items)
        bullish_pct = round((bullish_cnt / max(1, total)) * 100, 1)

        if bullish_cnt > bearish_cnt:
            overall = NewsSentiment.BULLISH
        elif bearish_cnt > bullish_cnt:
            overall = NewsSentiment.BEARISH
        else:
            overall = NewsSentiment.NEUTRAL

        summary = SentimentSummary(
            bullish_count=bullish_cnt,
            bearish_count=bearish_cnt,
            neutral_count=neutral_cnt,
            bullish_percentage=bullish_pct,
            overall_sentiment=overall
        )

        resp = NewsResponse(
            query_ticker="IHSG",
            total_items=total,
            sentiment_summary=summary,
            news=items,
            fetched_at=datetime.now().strftime("%d %b %Y, %H:%M WIB")
        )

        with self._lock:
            self._cache[cache_key] = (time.time(), resp)

        return resp
