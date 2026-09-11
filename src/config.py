import os
from dotenv import load_dotenv

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
ENV_PATH = os.path.join(CONFIG_DIR, '.env')
FONT_PATH = os.path.join(CONFIG_DIR, "GmarketSansTTFBold.ttf")

# Load environment variables
load_dotenv(ENV_PATH)

# Naver API
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# GCP / Vertex AI
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(CONFIG_DIR, "application_default_credentials.json")
GCP_PROJECT_ID = "project-beba2bf6-d235-4031-ba5"
GCP_LOCATION = "us-central1"

from datetime import datetime

ASSETS_DIR = os.path.join(BASE_DIR, "assets")

EDITION_CONFIG = {
    "morning": {
        "data_dir": os.path.join(BASE_DIR, "data", "morning"),
        "voice_name": "ko-KR-Wavenet-D",
        "top_title": "1분 출근길 뉴스",
        "video_suffix": "_출근길_뉴스브리핑.mp4",
        "hook_prompt": "출근길 직장인들의 잠을 깨워주는 상쾌하고 활기찬 이슈 브리핑 시작 알림",
        "closing_prompt": "오늘 하루를 시작하는 2040 직장인 시청자들에게 건네는 응원과 에너지를 주는 인사말과 명언이 모두 포함된 전체 나레이션 대본",
        "closing_quote_prompt": "도전, 시작, 열정 등 긍정적인 에너지를 주는 '출처가 명확한 위인들의 명언이나 책 구절(발언자 포함)' 텍스트 (화면 중앙 노출용)"
    },
    "evening": {
        "data_dir": os.path.join(BASE_DIR, "data", "evening"),
        "voice_name": "ko-KR-Wavenet-A",
        "top_title": "1분 퇴근길 뉴스",
        "video_suffix": "_퇴근길_뉴스브리핑.mp4",
        "hook_prompt": "오늘 하루의 피로를 날려줄 이슈 브리핑 시작 알림",
        "closing_prompt": "오늘 하루도 치열하게 살아낸 2040 직장인 시청자들에게 건네는 인사말과 명언이 모두 포함된 전체 나레이션 대본",
        "closing_quote_prompt": "대충 지어낸 말이 아닌 '출처가 명확한 위인들의 명언이나 책 구절(발언자 포함)' 텍스트 (화면 중앙 노출용)"
    },
    "lunch": {
        "data_dir": os.path.join(BASE_DIR, "data", "lunch"),
        "voice_name": "ko-KR-Wavenet-B",
        "top_title": "1분 점심시간 뉴스",
        "video_suffix": "_점심시간_뉴스브리핑.mp4",
        "hook_prompt": "오전 업무의 피로를 풀어줄 편안하고 재밌는 점심시간 이슈 브리핑 시작 알림",
        "closing_prompt": "오후 업무를 준비하는 2040 직장인 시청자들에게 건네는 응원과 편안함을 주는 인사말과 명언이 포함된 전체 나레이션 대본",
        "closing_quote_prompt": "휴식과 재충전, 여유와 관련된 '출처가 명확한 위인들의 명언이나 책 구절(발언자 포함)' 텍스트 (화면 중앙 노출용)"
    },
    # --- 주말 에디션 (Weekend Editions) ---
    "weekend_morning": {
        "data_dir": os.path.join(BASE_DIR, "data", "weekend_morning"),
        "voice_name": "ko-KR-Wavenet-C",
        "top_title": "1분 주말 라이프",
        "video_suffix": "_주말아침_라이프브리핑.mp4",
        "hook_prompt": "주말 아침을 상쾌하게 시작하는 라이프스타일 브리핑 시작 알림",
        "closing_prompt": "여유로운 주말을 즐기는 시청자들에게 건네는 따뜻한 인사말과 명언이 모두 포함된 전체 나레이션 대본",
        "closing_quote_prompt": "여유, 휴식, 삶의 질, 행복과 관련된 '출처가 명확한 위인들의 명언이나 책 구절(발언자 포함)' 텍스트 (화면 중앙 노출용)"
    },
    "weekend_evening": {
        "data_dir": os.path.join(BASE_DIR, "data", "weekend_evening"),
        "voice_name": "ko-KR-Wavenet-A",
        "top_title": "1분 주말 라이프",
        "video_suffix": "_주말저녁_라이프브리핑.mp4",
        "hook_prompt": "주말 저녁, 한 주를 여유롭게 마무리하는 라이프스타일 브리핑 시작 알림",
        "closing_prompt": "주말을 마무리하고 새로운 한 주를 준비하는 시청자들에게 건네는 따뜻한 응원과 명언이 모두 포함된 전체 나레이션 대본",
        "closing_quote_prompt": "새로운 시작, 삶의 균형, 자기계발과 관련된 '출처가 명확한 위인들의 명언이나 책 구절(발언자 포함)' 텍스트 (화면 중앙 노출용)"
    }
}

os.makedirs(EDITION_CONFIG["morning"]["data_dir"], exist_ok=True)
os.makedirs(EDITION_CONFIG["evening"]["data_dir"], exist_ok=True)
os.makedirs(EDITION_CONFIG["lunch"]["data_dir"], exist_ok=True)
os.makedirs(EDITION_CONFIG["weekend_morning"]["data_dir"], exist_ok=True)
os.makedirs(EDITION_CONFIG["weekend_evening"]["data_dir"], exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DATA_DIR = EDITION_CONFIG["morning"]["data_dir"]

def get_daily_dir(target_date_str=None, edition="morning"):
    if target_date_str is None:
        target_date_str = datetime.now().strftime("%Y%m%d")
        
    formatted_date = f"{target_date_str[:4]}-{target_date_str[4:6]}-{target_date_str[6:8]}"
    daily_dir = os.path.join(EDITION_CONFIG[edition]["data_dir"], formatted_date)
    os.makedirs(daily_dir, exist_ok=True)
    return daily_dir
