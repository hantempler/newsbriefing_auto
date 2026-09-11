import os
import sys
import argparse
from datetime import datetime, timezone, timedelta

# GitHub Actions 서버는 UTC 기준. 한국 시간(KST = UTC+9)으로 날짜/요일 판단
KST = timezone(timedelta(hours=9))

# Add src to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import scrape_naver_ranking_news
from src.script_gen import run_script_gen
from src.tts_gen import run_tts_gen
from src.renderer_1_thumb import run_renderer_thumb
from src.renderer_2_video import run_renderer_video
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

def _get_video_path(target_date, edition):
    """영상 파일 경로를 반환하는 공통 헬퍼"""
    from src.config import EDITION_CONFIG, get_daily_dir
    video_suffix = EDITION_CONFIG[edition]['video_suffix']
    daily_dir = get_daily_dir(target_date, edition)
    video_filename = f"{target_date}{video_suffix}"
    video_path = os.path.join(daily_dir, video_filename)
    return video_path, video_filename

def upload_video_to_gdrive(target_date, edition):
    """Google Drive에 영상 업로드 (OAuth 토큰 방식)"""
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("[GDrive] GDRIVE_FOLDER_ID 미설정. 업로드 건너뜀.")
        return

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(BASE_DIR, "config", "gdrive_token.json")
    if not os.path.exists(token_path):
        print(f"[GDrive] 토큰 파일 없음 ({token_path}). 업로드 건너뜀.")
        return

    video_path, video_filename = _get_video_path(target_date, edition)
    if not os.path.exists(video_path):
        print(f"[GDrive] 영상 파일 없음: {video_path}")
        return

    print(f"[GDrive] '{video_filename}' 업로드 중...")
    try:
        creds = Credentials.from_authorized_user_file(token_path)
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': video_filename, 'parents': [folder_id]}
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"[GDrive] 업로드 완료! File ID: {file.get('id')}")
    except Exception as e:
        print(f"[GDrive] 업로드 실패: {e}")

def upload_video_to_youtube(target_date, edition):
    """YouTube에 영상 업로드 (OAuth 토큰 방식)"""
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token_path = os.path.join(BASE_DIR, "config", "youtube_token.json")
    if not os.path.exists(token_path):
        print(f"[YouTube] 토큰 파일 없음 ({token_path}). 업로드 건너뜀.")
        return

    video_path, video_filename = _get_video_path(target_date, edition)
    if not os.path.exists(video_path):
        print(f"[YouTube] 영상 파일 없음: {video_path}")
        return

    from src.config import EDITION_CONFIG
    top_title = EDITION_CONFIG[edition]['top_title']
    # 날짜 포맷: YYYYMMDD -> YYYY.MM.DD
    date_formatted = f"{target_date[:4]}.{target_date[4:6]}.{target_date[6:8]}"
    yt_title = f"{date_formatted} {top_title} 뉴스브리핑"
    yt_description = (
        f"{date_formatted} {top_title}\n\n"
        "#뉴스브리핑 #쇼츠 #Shorts\n"
        f"#{edition}"
    )

    print(f"[YouTube] '{yt_title}' 업로드 중...")
    try:
        creds = Credentials.from_authorized_user_file(token_path)
        youtube = build('youtube', 'v3', credentials=creds)
        body = {
            'snippet': {
                'title': yt_title,
                'description': yt_description,
                'tags': ['뉴스브리핑', '쇼츠', 'Shorts', top_title],
                'categoryId': '25'  # 25 = News & Politics
            },
            'status': {
                'privacyStatus': 'public'
            }
        }
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response = request.execute()
        print(f"[YouTube] 업로드 완료! https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"[YouTube] 업로드 실패: {e}")

def main():
    parser = argparse.ArgumentParser(description="뉴스 브리핑 자동화 파이프라인 (클라우드/무인 실행용)")
    parser.add_argument("--edition", type=str, choices=['morning', 'lunch', 'evening', 'weekend_morning', 'weekend_evening'], required=True, help="실행할 버전을 지정하세요")
    parser.add_argument("--date", type=str, default=None, help="대상 날짜 (YYYYMMDD 형식). 지정하지 않으면 오늘 날짜를 사용합니다.")
    args = parser.parse_args()

    edition = args.edition
    # KST 기준 오늘 날짜 사용 (GitHub Actions 서버는 UTC)
    # 예: 토 KST 06:30 = 금 UTC 21:30 → UTC 날짜 쓰면 금요일로 오인
    _now_kst = datetime.now(KST)
    target_date = args.date if args.date else _now_kst.strftime("%Y%m%d")

    # --- 주말 자동 감지 (Weekend Auto-Detection) ---
    # KST 기준 요일로 판단 (UTC 기준이면 토 아침이 금요일로 오인되는 버그 발생)
    _is_weekend = _now_kst.weekday() >= 5  # 5=토, 6=일

    WEEKEND_EDITION_MAP = {
        'morning': 'weekend_morning',
        'evening': 'weekend_evening',
        'lunch': None,  # 주말에는 점심 에디션 없음
    }

    if _is_weekend and edition in WEEKEND_EDITION_MAP:
        _mapped = WEEKEND_EDITION_MAP[edition]
        if _mapped is None:
            print(f"[WEEKEND] 오늘은 주말입니다. '{edition}' 에디션은 주말에 실행되지 않습니다. 종료.")
            sys.exit(0)
        print(f"[WEEKEND] 주말 감지: '{edition}' → '{_mapped}' 으로 자동 전환됩니다.")
        edition = _mapped
    # -----------------------------------------------


    print(f"=== 뉴스 브리핑 무인 파이프라인 ===")
    print(f"[{edition.upper()}] 파이프라인 시작 (대상 날짜: {target_date})")
    
    try:
        print("\n--- 1. 기사 스크랩 ---")
        scrape_naver_ranking_news(target_date, edition=edition)
        
        print("\n--- 2. 대본 작성 ---")
        run_script_gen(target_date, edition=edition)
        
        print("\n--- 3. 음성 합성 (TTS) ---")
        run_tts_gen(target_date, edition=edition)
        
        print("\n--- 4. 썸네일 생성 ---")
        run_renderer_thumb(target_date, edition=edition)
        
        print("\n--- 5. 영상 렌더링 ---")
        run_renderer_video(target_date, edition=edition)
        
        print("\n--- 6. Google Drive 업로드 ---")
        upload_video_to_gdrive(target_date, edition=edition)

        print("\n--- 7. YouTube 업로드 ---")
        upload_video_to_youtube(target_date, edition=edition)
        
        print(f"\n[{edition.upper()}] 모든 작업이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n작업 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
