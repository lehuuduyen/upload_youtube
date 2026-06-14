"""
Script Generator — dùng Claude API để viết kịch bản video từ trend data.
Nếu API không khả dụng (hết credit, chưa cài key), tự động dùng template fallback.
"""
import json
import re


def generate_script(trend_data: dict, duration_seconds: int = 60) -> dict:
    """
    Dùng Claude API tạo script video hoàn chỉnh.
    Tự động fallback sang template nếu API lỗi.
    Trả về dict gồm title, hook, body, cta, hashtags, full_voiceover.
    """
    try:
        return _generate_with_claude(trend_data, duration_seconds)
    except Exception as e:
        err = str(e)
        # Billing / auth errors → fallback ngay, không retry
        if any(kw in err for kw in ["credit balance", "invalid_request_error", "ANTHROPIC_API_KEY", "anthropic"]):
            return _generate_fallback(trend_data, duration_seconds, reason=err)
        raise


def _generate_with_claude(trend_data: dict, duration_seconds: int) -> dict:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package chưa cài. Chạy: pip install anthropic")

    from config import settings
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY chưa được cài đặt. Thêm vào file .env")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Bạn là chuyên gia viết kịch bản video ngắn TikTok/YouTube Shorts.

DỮ LIỆU TREND THỰC TẾ:
- Keyword hot nhất: {trend_data.get('best_keyword', trend_data.get('topic'))}
- Điểm xu hướng: {trend_data.get('trend_score', 'N/A')}/100
- Câu hỏi người đang tìm: {json.dumps(trend_data.get('content_angles', []), ensure_ascii=False)}
- Video trending liên quan: {json.dumps(trend_data.get('youtube_trending', []), ensure_ascii=False)}

CHỦ ĐỀ: {trend_data.get('topic')}
ĐỐI TƯỢNG: {trend_data.get('audience')}
THỜI LƯỢNG: {duration_seconds} giây

Tạo kịch bản theo JSON sau, KHÔNG thêm text ngoài JSON:
{{
  "title": "Tiêu đề hấp dẫn dưới 100 ký tự",
  "description": "Mô tả 200-300 ký tự cho YouTube/TikTok",
  "hook": {{
    "duration": 3,
    "visual": "Mô tả hình ảnh/cảnh quay",
    "audio": "Lời nói hook gây tò mò"
  }},
  "body": [
    {{"point": 1, "duration": 15, "visual": "...", "audio": "...", "text_overlay": "Chữ hiển thị ngắn"}},
    {{"point": 2, "duration": 15, "visual": "...", "audio": "...", "text_overlay": "..."}},
    {{"point": 3, "duration": 15, "visual": "...", "audio": "...", "text_overlay": "..."}}
  ],
  "cta": {{
    "duration": 5,
    "visual": "...",
    "audio": "Follow để xem thêm!",
    "text_overlay": "Follow & Lưu lại!"
  }},
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "full_voiceover": "Toàn bộ lời thoại nối liền từ đầu đến cuối",
  "background_music_mood": "upbeat/calm/dramatic/inspirational"
}}"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("Claude không trả về JSON hợp lệ")
        script = json.loads(match.group())

    return script


def _generate_fallback(trend_data: dict, duration_seconds: int, reason: str = "") -> dict:
    """
    Template-based script khi Claude API không khả dụng.
    Dùng keyword từ trend_data để tạo nội dung cơ bản.
    """
    topic = trend_data.get("topic", "chủ đề hot")
    keyword = trend_data.get("best_keyword", topic)
    audience = trend_data.get("audience", "mọi người")
    angles = trend_data.get("content_angles", [])

    # Chọn 3 điểm nội dung từ content_angles hoặc tạo mặc định
    points = (angles[:3] if len(angles) >= 3 else angles + [
        f"Tại sao {keyword} quan trọng",
        f"Cách áp dụng {keyword} hiệu quả",
        f"Mẹo hay về {keyword}",
    ])[:3]

    body_duration = max(10, (duration_seconds - 8) // 3)

    script = {
        "title": f"{keyword.title()} - Bí quyết bạn chưa biết!",
        "description": (
            f"Khám phá những điều thú vị về {keyword} dành cho {audience}. "
            f"Xem ngay để không bỏ lỡ thông tin hữu ích!"
        ),
        "hook": {
            "duration": 3,
            "visual": f"Chữ lớn: '{keyword.upper()}' trên nền gradient",
            "audio": f"Bạn có biết sự thật về {keyword} chưa? Xem ngay!",
        },
        "body": [
            {
                "point": i + 1,
                "duration": body_duration,
                "visual": f"Text overlay với thông tin về điểm {i + 1}",
                "audio": f"Điểm thứ {i + 1}: {pt}",
                "text_overlay": pt[:30] if len(pt) > 30 else pt,
            }
            for i, pt in enumerate(points)
        ],
        "cta": {
            "duration": 5,
            "visual": "Animation nút Subscribe và Like",
            "audio": "Like và theo dõi kênh để xem thêm nội dung hay nhé!",
            "text_overlay": "Like & Follow!",
        },
        "hashtags": [
            keyword.replace(" ", ""),
            topic.replace(" ", ""),
            "shorts",
            "viral",
            "trending",
        ],
        "full_voiceover": (
            f"Bạn có biết sự thật về {keyword} chưa? Xem ngay! "
            + " ".join(f"Điểm thứ {i + 1}: {pt}." for i, pt in enumerate(points))
            + " Like và theo dõi kênh để xem thêm nội dung hay nhé!"
        ),
        "background_music_mood": "upbeat",
        "_fallback": True,
        "_fallback_reason": reason or "Claude API không khả dụng — dùng template tự động",
    }

    return script
