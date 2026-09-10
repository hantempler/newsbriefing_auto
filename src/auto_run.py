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
from google.cloud import storage

def upload_video_to_gcs(target_date, edition):
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if not bucket_name:
        print("GCS_BUCKET_NAME environment variable is not set. Skipping GCS upload.")
        return

    from src.config import EDITION_CONFIG, get_daily_dir
    video_suffix = EDITION_CONFIG[edition]['video_suffix']
    daily_dir = get_daily_dir(target_date, edition)
    video_filename = f"{target_date}{video_suffix}"
    video_path = os.path.join(daily_dir, video_filename)

    if not os.path.exists(video_path):
        print(f"Video file not found at {video_path}. Cannot upload.")
        return

    print(f"Uploading {video_filename} to GCS bucket '{bucket_name}'...")
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"newsbriefing/{edition}/{target_date}/{video_filename}")
        
        blob.upload_from_filename(video_path)
        print(f"Successfully uploaded to gs://{bucket_name}/newsbriefing/{edition}/{target_date}/{video_filename}")
    except Exception as e:
        print(f"Failed to upload to GCS: {e}")

def main():
    parser = argparse.ArgumentParser(description="뉴스 브리핑 자동화 파이프라인 (클라우드/무인 실행용)")
    parser.add_argument("--edition", type=str, choices=['morning', 'lunch', 'evening'], required=True, help="실행할 버전을 지정하세요")
    parser.add_argument("--date", type=str, default=None, help="대상 날짜 (YYYYMMDD 형식). 지정하지 않으면 오늘 날짜를 사용합니다.")
    args = parser.parse_args()

    edition = args.edition
    target_date = args.date if args.date else datetime.now().strftime("%Y%m%d")
    
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
        
        print("\n--- 6. GCS 버킷 업로드 ---")
        upload_video_to_gcs(target_date, edition=edition)
        
        print(f"\n[{edition.upper()}] 모든 작업이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"\n작업 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
