import os
import sys
import time
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


# ---------------------------------------------------------------------------
# 재시도 유틸리티
# ---------------------------------------------------------------------------
def run_with_retry(func, step_name, max_attempts=3, wait_seconds=30, *args, **kwargs):
    """
    주어진 함수를 최대 max_attempts 회까지 재시도합니다.
    성공 시 True, 모든 시도 실패 시 마지막 예외를 raise 합니다.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[{step_name}] 시도 {attempt}/{max_attempts} ...")
            result = func(*args, **kwargs)
            print(f"[{step_name}] ✅ 성공 (시도 {attempt}회)")
            return result
        except Exception as e:
            last_exc = e
            print(f"[{step_name}] ❌ 실패 (시도 {attempt}회): {e}")
            if attempt < max_attempts:
                print(f"[{step_name}] {wait_seconds}초 후 재시도합니다...")
                time.sleep(wait_seconds)
    raise last_exc


# ---------------------------------------------------------------------------
# 각 단계 완료 여부 체크 헬퍼
# ---------------------------------------------------------------------------
def _is_step_done(daily_dir, marker_filename):
    """
    중간 결과 파일이 존재하고 크기가 0 이상이면 해당 단계가 완료된 것으로 간주합니다.
    재시도(retry) 시 이미 완료된 단계를 건너뛸 수 있습니다.
    """
    path = os.path.join(daily_dir, marker_filename)
    return os.path.exists(path) and os.path.getsize(path) > 0


# ---------------------------------------------------------------------------
# 단계별 완료 마커 파일 정의
# (각 단계 함수가 생성하는 대표 출력 파일)
# ---------------------------------------------------------------------------
STEP_MARKERS = {
    "scrape":    "1_all_titles.json",   # scraper.py 출력
    "script":    "3_script.json",       # script_gen.py 출력
    "tts":       "4_audio_hook.mp3",    # tts_gen.py 출력 (hook이 첫 번째)
    "thumb":     "5_thumbnail.png",     # renderer_1_thumb.py 출력 (추정)
    # video: video_path 자체로 체크하므로 여기선 제외
}


# ---------------------------------------------------------------------------
# GDrive / YouTube 업로드
# ---------------------------------------------------------------------------
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
    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
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

    print(f"[GDrive] '{video_filename}' 업로드 중... (folder_id: {folder_id})")
    try:
        creds = Credentials.from_authorized_user_file(token_path)
        service = build('drive', 'v3', credentials=creds)

        # 폴더 존재 여부 사전 확인
        try:
            service.files().get(fileId=folder_id, fields='id,name').execute()
            file_metadata = {'name': video_filename, 'parents': [folder_id]}
            print(f"[GDrive] 폴더 확인 완료. 폴더에 업로드합니다.")
        except Exception:
            # 폴더를 찾을 수 없으면 루트에 업로드 (fallback)
            print(f"[GDrive] 폴더(ID: {folder_id}) 접근 실패. 루트에 업로드합니다.")
            file_metadata = {'name': video_filename}

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
                'privacyStatus': 'private'  # 비공개. YouTube Studio에서 직접 확인 후 공개로 전환하세요.
            }
        }
        media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response = request.execute()
        print(f"[YouTube] 업로드 완료! https://youtu.be/{response['id']}")
    except Exception as e:
        print(f"[YouTube] 업로드 실패: {e}")


# ---------------------------------------------------------------------------
# 메인 파이프라인
# ---------------------------------------------------------------------------
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

    # daily_dir 참조 (마커 파일 체크에 사용)
    from src.config import get_daily_dir
    daily_dir = get_daily_dir(target_date, edition)

    print(f"=== 뉴스 브리핑 무인 파이프라인 ===")
    print(f"[{edition.upper()}] 파이프라인 시작 (대상 날짜: {target_date})")
    print(f"[작업 디렉토리] {daily_dir}")

    try:
        # ------------------------------------------------------------------
        # 1단계: 기사 스크랩
        # 출력: 1_all_titles.json
        # 네트워크 의존 → 재시도 3회
        # ------------------------------------------------------------------
        print("\n--- 1. 기사 스크랩 ---")
        if _is_step_done(daily_dir, STEP_MARKERS["scrape"]):
            print(f"[스크랩] ⏩ 이미 완료된 단계입니다. 건너뜁니다.")
        else:
            run_with_retry(
                scrape_naver_ranking_news,
                "스크랩",
                3, 30,          # max_attempts=3, wait=30초
                target_date, edition=edition
            )

        # ------------------------------------------------------------------
        # 2단계: 대본 작성
        # 출력: 3_script.json
        # AI API 의존 → 재시도 3회
        # ------------------------------------------------------------------
        print("\n--- 2. 대본 작성 ---")
        if _is_step_done(daily_dir, STEP_MARKERS["script"]):
            print(f"[대본] ⏩ 이미 완료된 단계입니다. 건너뜁니다.")
        else:
            run_with_retry(
                run_script_gen,
                "대본",
                3, 30,
                target_date, edition=edition
            )

        # ------------------------------------------------------------------
        # 3단계: 음성 합성(TTS)
        # 출력: 4_audio_hook.mp3 외
        # Google Cloud TTS API 의존 → 재시도 3회
        # ------------------------------------------------------------------
        print("\n--- 3. 음성 합성 (TTS) ---")
        if _is_step_done(daily_dir, STEP_MARKERS["tts"]):
            print(f"[TTS] ⏩ 이미 완료된 단계입니다. 건너뜁니다.")
        else:
            run_with_retry(
                run_tts_gen,
                "TTS",
                3, 30,
                target_date, edition=edition
            )

        # ------------------------------------------------------------------
        # 4단계: 썸네일 생성
        # 출력: 5_thumbnail.png (추정)
        # CPU 연산 → 재시도 2회
        # ------------------------------------------------------------------
        print("\n--- 4. 썸네일 생성 ---")
        if _is_step_done(daily_dir, STEP_MARKERS["thumb"]):
            print(f"[썸네일] ⏩ 이미 완료된 단계입니다. 건너뜁니다.")
        else:
            run_with_retry(
                run_renderer_thumb,
                "썸네일",
                2, 15,
                target_date, edition=edition
            )

        # ------------------------------------------------------------------
        # 5단계: 영상 렌더링
        # 출력: {target_date}{video_suffix}.mp4
        # CPU 연산 → 재시도 2회
        # ------------------------------------------------------------------
        print("\n--- 5. 영상 렌더링 ---")
        video_path, _ = _get_video_path(target_date, edition)
        if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
            print(f"[렌더링] ⏩ 이미 완료된 단계입니다. 건너뜁니다.")
        else:
            run_with_retry(
                run_renderer_video,
                "렌더링",
                2, 15,
                target_date, edition=edition
            )

        # ------------------------------------------------------------------
        # 6단계: Google Drive 업로드
        # 업로드 실패는 파이프라인 전체 실패로 처리하지 않음
        # 네트워크 의존 → 재시도 3회 (단, 실패해도 계속 진행)
        # ------------------------------------------------------------------
        print("\n--- 6. Google Drive 업로드 ---")
        try:
            run_with_retry(
                upload_video_to_gdrive,
                "GDrive",
                3, 20,
                target_date, edition=edition
            )
        except Exception as e:
            print(f"[GDrive] ⚠️ 최종 업로드 실패 (파이프라인은 계속): {e}")

        # ------------------------------------------------------------------
        # 7단계: YouTube 업로드
        # 업로드 실패는 파이프라인 전체 실패로 처리하지 않음
        # 네트워크 의존 → 재시도 3회 (단, 실패해도 계속 진행)
        # ------------------------------------------------------------------
        print("\n--- 7. YouTube 업로드 ---")
        try:
            run_with_retry(
                upload_video_to_youtube,
                "YouTube",
                3, 20,
                target_date, edition=edition
            )
        except Exception as e:
            print(f"[YouTube] ⚠️ 최종 업로드 실패 (파이프라인은 계속): {e}")

        print(f"\n[{edition.upper()}] 모든 작업이 성공적으로 완료되었습니다!")

    except Exception as e:
        print(f"\n[PIPELINE ERROR] 파이프라인 중단: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
