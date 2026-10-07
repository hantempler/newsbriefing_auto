import os
import json
import sys

# 상위 폴더(루트)를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# src 내부 모듈 임포트
import config
from scraper import get_naver_headlines
from script_gen import generate_script
from fact_check import fact_check_script
from bgm import download_bgm
from video_generator import YouTubeShortsGenerator
from upload_youtube import upload_video

def main():
    print("=== AI 종합 뉴스 파이프라인 시작 (newsbriefing_v3) ===")
    
    # 0. 작업 폴더 생성
    daily_dir = config.get_daily_dir()
    print(f"\n[0/5] 오늘자 작업 폴더 준비: {daily_dir}")
    
    # 1. 네이버 분야별 헤드라인 수집
    print("\n[1/5] 네이버 뉴스 분야별 헤드라인 수집 중...")
    news_data = get_naver_headlines()
    
    if not news_data:
        print("뉴스 수집 실패. 파이프라인을 종료합니다.")
        return
        
    print(f"-> 수집된 기사: 총 {len(news_data)}건")
    
    # 2. 뉴스 데이터 기반 대본 작성
    print("\n[2/5] AI 앵커 대본 작성 중...")
    script_data = generate_script(news_data, daily_dir)
    if not script_data:
        print("대본 작성 실패. 파이프라인을 종료합니다.")
        return
    # 팩트체크 수행 (대본 검증)
    print("-> 생성된 대본 팩트체크 수행 중...")
    topic_str = "저녁 뉴스 브리핑"
    fact_check_result = fact_check_script(topic_str, news_data, script_data, daily_dir)
    if fact_check_result and not fact_check_result.get("approved"):
        print("경고: 대본에 팩트체크 이슈가 발견되었습니다. (진행은 계속합니다)")
        
    # 3. 주제 분위기에 맞는 BGM 다운로드
    print("\n[3/5] 진중한 분위기의 뉴스 BGM 다운로드 중...")
    topic_str = "저녁 뉴스 브리핑"
    bgm_path = download_bgm(topic_str, daily_dir)
        
    # 4. 음성 합성 및 초고속 영상 렌더링
    print("\n[4/5] 완벽한 동기화를 위한 컷별 음성(TTS) 생성 및 영상 렌더링 중...")
    generator = YouTubeShortsGenerator(script_data, topic_str, daily_dir, bgm_path)
    video_path = generator.generate_video()
    if not video_path:
        print("영상 렌더링 실패. 파이프라인을 종료합니다.")
        return
        
    # 5. 유튜브 업로드 (OAuth 연동) - 현재 테스트를 위해 주석 처리됨
    # print("\n[5/5] 유튜브 쇼츠 자동 업로드 중 (비공개 상태로 업로드)...")
    # cover_title = script_data.get("cover_title", topic_str)
    # title = f"📺 {cover_title} #쇼츠 #뉴스브리핑"
    
    # useful_title = script_data.get("useful_source_title", "네이버 뉴스")
    # useful_url = script_data.get("useful_source_url", "https://news.naver.com")
    
    # description = f"오늘 하루 반드시 알아야 할 핵심 뉴스 브리핑입니다!\n\n"
    # description += f"💡 출처:\n👉 {useful_title}\n🔗 {useful_url}\n\n"
    
    # license_path = os.path.join(daily_dir, "bgm_license.json")
    # if bgm_path and os.path.exists(license_path):
    #     with open(license_path, encoding="utf-8") as file:
    #         bgm_license = json.load(file)
    #     description += (
    #         "🎵 BGM: {title} - {artist}\n"
    #         "🔗 {url}\n"
    #         "📄 License: {license}\n\n"
    #     ).format(**bgm_license)
    # description += "#쇼츠 #뉴스 #정치 #경제 #사회 #세계 #IT #1분요약"
    
    # upload_url = upload_video(video_path, title, description)
    
    print("\n=== 파이프라인 완료 ===")
    print(f"생성된 영상 경로: {video_path}")
    # if upload_url:
    #     print(f"업로드 주소: {upload_url}")
    # else:
    #     print("업로드 실패 또는 주소를 받아오지 못했습니다.")

if __name__ == "__main__":
    main()
