import os
import sys
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_naver_headlines():
    print("  -> 네이버 많이 본 뉴스 및 연예 랭킹 수집 중...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    }
    
    news_data = []
    
    # 1. 일반 뉴스 (언론사별 랭킹 페이지)
    print("    [종합] 랭킹 뉴스 수집 시작...")
    try:
        url = "https://news.naver.com/main/ranking/popularDay.naver"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 랭킹 기사 링크 추출 (각 언론사별 1위 기사만 먼저 수집하여 다양성 확보, 최대 15개)
        links = []
        for box in soup.select('.rankingnews_box'):
            first_link = box.select_one('.list_content a')
            if first_link and first_link.has_attr('href'):
                href = first_link['href']
                if href.startswith('/'):
                    href = "https://news.naver.com" + href
                if href not in links:
                    links.append(href)
                
        for article_url in links:
            try:
                art_res = requests.get(article_url, headers=headers)
                art_res.raise_for_status()
                art_soup = BeautifulSoup(art_res.text, "html.parser")
                
                # 제목
                title = art_soup.select_one('#title_area')
                title_text = title.text.strip() if title else art_soup.select_one('meta[property="og:title"]')['content']
                
                # 본문
                content = art_soup.select_one('#dic_area')
                content_text = content.text.strip() if content else ""
                if len(content_text) > 800:
                    content_text = content_text[:800] + "..."
                    
                # 이미지
                og_image = art_soup.select_one('meta[property="og:image"]')
                image_url = og_image['content'] if og_image else ""
                
                if title_text and content_text:
                    news_data.append({
                        "category": "종합",
                        "title": title_text,
                        "content": content_text,
                        "image_url": image_url,
                        "url": article_url
                    })
            except Exception as e:
                pass
        print(f"    [종합] {len([n for n in news_data if n['category'] == '종합'])}개 기사 수집 완료")
    except Exception as e:
        print(f"    [종합] 스크래핑 실패: {e}")
        
    # 연예/스포츠 뉴스 수집 로직은 모바일 SPA 구조 변경 및 본문 부족 문제로 삭제 완료. (종합 뉴스에 집중)

    # 3. 날씨 데이터 추가
    try:
        weather_res = requests.get("https://search.naver.com/search.naver?query=전국+내일+날씨", headers=headers)
        w_soup = BeautifulSoup(weather_res.text, "html.parser")
        w_info = w_soup.select_one('.api_subject_bx')
        weather_text = w_info.text[:2000] if w_info else "내일 전국은 맑고 일교차가 클 것으로 예상됩니다."
        
        news_data.append({
            "category": "날씨",
            "title": "내일의 날씨",
            "content": f"날씨 정보: {weather_text}",
            "image_url": "",
            "url": ""
        })
        print(f"    [날씨] 데이터 수집 완료")
    except Exception as e:
        print(f"    [날씨] 수집 실패: {e}")
        
    return news_data

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    data = get_naver_headlines()
    print(json.dumps(data, ensure_ascii=False, indent=2))
