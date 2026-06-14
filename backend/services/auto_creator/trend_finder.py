"""
Trend Finder — Google Trends + YouTube RSS (miễn phí)
"""
import xml.etree.ElementTree as ET
from datetime import datetime

import requests


def get_google_trends(keywords: list[str], timeframe: str = "now 7-d", geo: str = "VN") -> dict:
    """Lấy xu hướng Google Trends tại Việt Nam."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="vi-VN", tz=420)
        pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
        interest_df = pytrends.interest_over_time()
        related_queries = pytrends.related_queries()

        results = {}
        for kw in keywords:
            score = int(interest_df[kw].mean()) if kw in interest_df.columns else 0
            top_queries = []
            if kw in related_queries and related_queries[kw]["top"] is not None:
                top_queries = related_queries[kw]["top"]["query"].head(5).tolist()
            results[kw] = {"trend_score": score, "related_searches": top_queries}
        return results
    except ImportError:
        # pytrends chưa cài — trả về fallback
        return {kw: {"trend_score": 50, "related_searches": []} for kw in keywords}
    except Exception as e:
        return {kw: {"trend_score": 0, "related_searches": [], "error": str(e)} for kw in keywords}


def get_youtube_trending_titles() -> list[str]:
    """Lấy tiêu đề video trending YouTube qua RSS (không cần API key)."""
    try:
        url = "https://www.youtube.com/feeds/videos.xml?hl=vi"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        return [
            e.find("atom:title", ns).text
            for e in root.findall("atom:entry", ns)[:10]
            if e.find("atom:title", ns) is not None
        ]
    except Exception:
        return []


def analyze_trend(topic: str, audience: str) -> dict:
    """Phân tích trend và trả về data để AI viết script."""
    keywords = [topic, f"{topic} 2025", f"mẹo {topic}"]
    trend_data = get_google_trends(keywords)

    best_keyword = max(trend_data, key=lambda k: trend_data[k]["trend_score"])
    all_related: list[str] = []
    for kw_data in trend_data.values():
        all_related.extend(kw_data["related_searches"])

    yt_titles = get_youtube_trending_titles()

    return {
        "topic": topic,
        "audience": audience,
        "best_keyword": best_keyword,
        "trend_score": trend_data[best_keyword]["trend_score"],
        "content_angles": all_related[:8],
        "youtube_trending": yt_titles[:5],
        "analyzed_at": datetime.now().isoformat(),
    }
