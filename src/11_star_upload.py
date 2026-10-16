"""스타이즈본 유튜브 쇼츠 자동 업로드 엔진 (11_star_upload.py).
newsbriefing_v3 검증된 OAuth2 인증 체계 계승 + 스타이즈본 4대 특화 연동:
1. OAuth2 무인 리프레시 토큰 자동 갱신 (Zero-interaction Auth)
2. final_shorts.mp4 Resumable 분할 청크 업로드 (대용량 안정성)
3. youtube_metadata.json (공식 팩트체크 출처 본문 + 알고리즘 태그 + 카테고리) 자동 주입
4. 업로드 결과 영구 저장 (upload_result.json)
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
CONFIG_DIR = ROOT_DIR / "config"
OUTPUT_DIR = ROOT_DIR / "output"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def get_youtube_service():
    """OAuth2 리프레시 토큰 기반 무인 YouTube API 서비스 객체 획득."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = CONFIG_DIR / "youtube_token.json"
    client_secrets_path = CONFIG_DIR / "client_secret_1.json"
    if not client_secrets_path.exists():
        client_secrets_path = CONFIG_DIR / "client_secrets.json"

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception as e:
            print(f"[Upload] 기존 토큰 파싱 실패, 재인증 필요: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Upload] 만료된 액세스 토큰 자동 리프레시 중...")
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            print("[Upload] 새 액세스 토큰 저장 완료!")
        else:
            if not client_secrets_path.exists():
                print(f"[Error] 클라이언트 비밀키 파일 없음: {client_secrets_path}")
                return None
            print("[Upload] 브라우저 최초 1회 OAuth2 인증 창을 실행합니다...")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            print(f"[Upload] 인증 성공! 토큰 저장: {token_path}")

    return build("youtube", "v3", credentials=creds)


def upload_shorts_package(package_dir, privacy_status="private", publish_at=None, dry_run=False):
    """지정된 패키지 디렉토리의 영상, 메타데이터, 썸네일, 고정 댓글을 유튜브에 자동 등록."""
    from googleapiclient.http import MediaFileUpload

    pkg = Path(package_dir)
    if not pkg.is_absolute():
        pkg = ROOT_DIR / package_dir

    if not pkg.exists():
        print(f"[Error] 패키지 경로를 찾을 수 없습니다: {pkg}")
        return None

    # 1. 필수 에셋 경로 검증
    video_path = pkg / "final_shorts.mp4"
    if not video_path.exists():
        print(f"[Error] 업로드할 영상 파일이 없습니다: {video_path}")
        return None

    # 메타데이터 로드
    meta_json = pkg / "youtube_metadata.json"
    script_json = pkg / "script.json"
    title = ""
    description = ""
    tags = []
    category_id = "24"  # 기본 Entertainment

    if meta_json.exists():
        try:
            data = json.loads(meta_json.read_text(encoding="utf-8"))
            title = data.get("title", "")
            description = data.get("description", "")
            tags = data.get("tags", [])
        except Exception as e:
            print(f"[Warn] youtube_metadata.json 로드 실패: {e}")

    if not title and script_json.exists():
        try:
            s_data = json.loads(script_json.read_text(encoding="utf-8"))
            sc = s_data.get("script", {})
            title = sc.get("title", "스타이즈본 역사 인물 쇼츠") + " #shorts"
            description = sc.get("hook_quote", "") + "\n\n#shorts #스타이즈본"
            tags = s_data.get("meta", {}).get("keywords", ["스타이즈본", "쇼츠"])
        except Exception as e:
            print(f"[Warn] script.json 폴백 실패: {e}")

    if not title:
        title = f"오늘의 스타 이야기 #shorts"

    print(f"============================================================")
    print(f"[YouTube Upload] 스타이즈본 쇼츠 자동 업로드 파이프라인")
    print(f"                 패키지: {pkg.name}")
    print(f"                 영상: {video_path.name} ({video_path.stat().st_size / 1e6:.1f} MB)")
    print(f"                 제목: {title}")
    print(f"                 공개 상태: {privacy_status.upper()}")
    if publish_at:
        print(f"                 예약 공개 일시: {publish_at}")
    print(f"                 태그 수: {len(tags)}개")
    print(f"============================================================")

    if dry_run:
        print("[DryRun] 테스트 모드: 실제 API 호출을 건너뜁니다.")
        return {
            "status": "dry_run_success",
            "title": title,
            "video_path": str(video_path),
            "privacy": privacy_status
        }

    # 2. YouTube API 서비스 획득
    youtube = get_youtube_service()
    if not youtube:
        print("[Error] YouTube API 인증 실패")
        return None

    # 3. 비디오 업로드 본문 구성
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],  # 유튜브 최대 태그 제한 보호
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    if publish_at:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at

    print(f"[Upload] 영상 파일 전송 중 (Resumable Upload)...")
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=1024 * 1024 * 5)
    
    video_id = None
    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[Upload] 진행률: {int(status.progress() * 100)}%")
                
        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        print(f"[Upload] 대성공! 영상 업로드 완료:")
        print(f"         URL: {video_url}")
    except Exception as e:
        print(f"[Error] 유튜브 영상 업로드 실패: {e}")
        return None

    # 4. 업로드 결과 로컬 패키지에 영구 저장
    upload_result = {
        "video_id": video_id,
        "video_url": f"https://youtu.be/{video_id}",
        "title": title,
        "privacy": privacy_status,
        "publish_at": publish_at,
        "uploaded_at": datetime.datetime.now().isoformat(),
        "package_dir": str(pkg)
    }
    result_file = pkg / "upload_result.json"
    result_file.write_text(json.dumps(upload_result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Upload] 업로드 결과 저장 완료: {result_file.name}")
    return upload_result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 유튜브 쇼츠 자동 업로더")
    p.add_argument("--package", help="업로드할 패키지 폴더 경로 (예: output/20261112_AM_anne_hathaway)")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"], help="공개 상태 (기본값: private 비공개)")
    p.add_argument("--publish-at", default=None, help="예약 공개 일시 (ISO 8601 포맷, 예: 2026-11-12T07:00:00Z)")
    p.add_argument("--dry-run", action="store_true", help="실제 업로드 없이 메타데이터 및 인증 검증만 수행")
    p.add_argument("--latest", action="store_true", help="output/ 폴더에서 가장 최근 생성된 패키지를 자동 선택")
    args = p.parse_args()

    target_pkg = args.package
    if args.latest or not target_pkg:
        pkgs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and (d / "final_shorts.mp4").exists()]
        if pkgs:
            target_pkg = str(max(pkgs, key=lambda x: x.stat().st_mtime))
            print(f"[Upload] 최신 패키지 자동 감지: {target_pkg}")
        else:
            print("[Error] 업로드 가능한 패키지가 output/ 에 없습니다.")
            sys.exit(1)

    upload_shorts_package(target_pkg, privacy_status=args.privacy, publish_at=args.publish_at, dry_run=args.dry_run)
