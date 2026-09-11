import os
import sys
import argparse
from datetime import datetime

# Add src to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import scrape_naver_ranking_news
from src.script_gen import run_script_gen
from src.tts_gen import run_tts_gen
from src.renderer_1_thumb import run_renderer_thumb
from src.renderer_2_video import run_renderer_video
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google.auth

def upload_video_to_gdrive(target_date, edition):
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not folder_id:
        print("GDRIVE_FOLDER_ID environment variable is not set. Skipping Google Drive upload.")
        return

    from src.config import EDITION_CONFIG, get_daily_dir
    video_suffix = EDITION_CONFIG[edition]['video_suffix']
    daily_dir = get_daily_dir(target_date, edition)
    video_filename = f"{target_date}{video_suffix}"
    video_path = os.path.join(daily_dir, video_filename)

    if not os.path.exists(video_path):
        print(f"Video file not found at {video_path}. Cannot upload.")
        return

    print(f"Uploading {video_filename} to Google Drive folder '{folder_id}'...")
    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=credentials)
        
        file_metadata = {
            'name': video_filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Successfully uploaded to Google Drive! File ID: {file.get('id')}")
    except Exception as e:
        print(f"Failed to upload to Google Drive: {e}")

def main():
    parser = argparse.ArgumentParser(description="뉴스 브리핑 자동화 파이프라인 (클라우드/무인 실행용)")
    parser.add_argument("--edition", type=str, choices=['morning', 'lunch', 'evening', 'weekend_morning', 'weekend_evening'], required=True, help="실행할 버전을 지정하세요")
    parser.add_argument("--date", type=str, default=None, help="대상 날짜 (YYYYMMDD 형식). 지정하지 않으면 오늘 날짜를 사용합니다.")
    args = parser.parse_args()

    edition = args.edition
    target_date = args.date if args.date else datetime.now().strftime("%Y%m%d")

    # --- 주말 자동 감지 (Weekend Auto-Detection) ---
    # YAML이 morning/evening을 인자로 넘겨도, 주말이면 자동 전환
    # 주말 에디션을 직접 지정하려면: --edition weekend_morning 으로 override 가능
    _today = datetime.now()
    _is_weekend = _today.weekday() >= 5  # 5=토, 6=일

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
        
        print(f"\n[{edition.upper()}] 모든 작업이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n작업 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
