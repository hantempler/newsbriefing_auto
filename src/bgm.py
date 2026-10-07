import json
import os
import re
import sys
from urllib.parse import quote

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


ALLOWED_LICENSE_MARKERS = (
    "/by/",
    "/by-sa/",
    "/zero/",
)


def _is_youtube_safe_license(track: dict) -> bool:
    license_url = (track.get("license_ccurl") or "").lower()
    if not license_url or any(marker in license_url for marker in ("/by-nc", "/by-nd")):
        return False
    return any(marker in license_url for marker in ALLOWED_LICENSE_MARKERS)


def _music_tag(topic: str) -> str:
    topic_text = (topic or "").lower()
    if any(word in topic_text for word in ("과학", "의료", "기술", "원리", "우주")):
        return "documentary"
    if any(word in topic_text for word in ("경제", "금리", "물가", "사회", "정치")):
        return "corporate"
    return "news"


def download_bgm(topic: str, output_dir: str = None):
    """Jamendo에서 CC 라이선스 음악을 내려받고 라이선스 정보를 저장한다."""
    client_id = os.getenv("JAMENDO_CLIENT_ID")
    if not client_id:
        print("JAMENDO_CLIENT_ID가 없어 BGM 없이 진행합니다.")
        return None

    if output_dir is None:
        output_dir = config.DATA_DIR
    os.makedirs(output_dir, exist_ok=True)
    bgm_path = os.path.join(output_dir, "bgm.mp3")
    license_path = os.path.join(output_dir, "bgm_license.json")
    for stale_path in (bgm_path, license_path):
        if os.path.exists(stale_path):
            os.remove(stale_path)

    tag = _music_tag(topic)
    try:
        tracks = []
        for search_tag in dict.fromkeys((tag, "news", "documentary")):
            params = {
                "client_id": client_id,
                "format": "json",
                "limit": 50,
                "tags": search_tag,
                "audioformat": "mp32",
                "include": "licenses",
                "vocal": 0,
                "order": "popularity_total",
            }
            response = requests.get(
                "https://api.jamendo.com/v3.0/tracks/",
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            tracks.extend(response.json().get("results", []))
        if not tracks:
            print(f"Jamendo에서 {tag} BGM을 찾지 못했습니다.")
            return None

        track = next((candidate for candidate in tracks if _is_youtube_safe_license(candidate)), None)
        if not track:
            print("YouTube 상업적 이용에 적합한 CC 라이선스 BGM을 찾지 못했습니다.")
            return None
        audio_url = track.get("audio")
        if not audio_url:
            return None

        with requests.get(audio_url, stream=True, timeout=60) as audio_response:
            audio_response.raise_for_status()
            with open(bgm_path, "wb") as file:
                for chunk in audio_response.iter_content(chunk_size=8192):
                    file.write(chunk)

        license_info = {
            "provider": "Jamendo",
            "track_id": track.get("id"),
            "title": track.get("name"),
            "artist": track.get("artist_name"),
            "url": track.get("shareurl"),
            "license": track.get("license_ccurl") or track.get("license"),
            "youtube_use": "commercial_use_allowed_with_attribution",
            "attribution_required": True,
            "tag": tag,
        }
        with open(license_path, "w", encoding="utf-8") as file:
            json.dump(license_info, file, ensure_ascii=False, indent=2)
        return bgm_path
    except (requests.RequestException, ValueError) as error:
        print(f"BGM 다운로드 오류: {error}")
        return None
