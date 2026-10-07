import os
import sys
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload'
]

def get_youtube_service():
    creds = None
    token_path = os.path.join(config.CONFIG_DIR, 'youtube_token.json')
    client_secrets_path = os.path.join(config.CONFIG_DIR, 'client_secret_1.json')
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_path):
                print(f"Error: {client_secrets_path} 파일이 없습니다.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return build('youtube', 'v3', credentials=creds)

def upload_video(video_path: str, title: str, description: str):
    if not os.path.exists(video_path):
        print(f"Error: 업로드할 영상이 없습니다. ({video_path})")
        return None
        
    youtube = get_youtube_service()
    if not youtube:
        return None
        
    safe_title = title.encode('cp949', 'ignore').decode('cp949')
    print(f"[YouTube] '{safe_title}' 업로드 중...")
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['1분상식', '상식', '쇼츠', '이슈', '지식'],
            'categoryId': '27' # Education
        },
        'status': {
            'privacyStatus': 'private',
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
    
    try:
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        response = request.execute()
        url = f"https://youtu.be/{response['id']}"
        print(f"[YouTube] 업로드 완료! {url}")
        return url
    except Exception as e:
        print(f"[YouTube] 업로드 실패: {e}")
        return None

if __name__ == "__main__":
    print("유튜브 API 인증을 시작합니다...")
    service = get_youtube_service()
    if service:
        print("✅ 인증 성공! youtube_token.json 파일이 갱신되었습니다.")
    else:
        print("❌ 인증 실패.")
