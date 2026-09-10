import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import inquirer
import sys

# Add src to Python path if run standalone
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import get_daily_dir

def scrape_naver_ranking_news(target_date, edition='morning'):
    print(f"Target Date: {target_date}")
    url = f"https://news.naver.com/main/ranking/popularDay.naver?date={target_date}"
    print(f"Opening Naver Ranking News: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return
        
    soup = BeautifulSoup(res.text, "html.parser")
    
    print("All publishers loaded. Scraping titles, links, and sources...")
    
    news_list = []
    
    # 랭킹 뉴스 박스 추출
    ranking_boxes = soup.find_all("div", class_="rankingnews_box")
    for box in ranking_boxes:
        source_name = box.find("strong", class_="rankingnews_name")
        source = source_name.text.strip() if source_name else "Unknown"
        
        list_items = box.find_all("li")
        for li in list_items:
            a_tag = li.find("a", class_="list_title")
            if a_tag:
                title = a_tag.text.strip()
                link = a_tag["href"]
                news_list.append({
                    "source": source,
                    "title": title,
                    "link": link
                })
                
    if not news_list:
        print("No news found. Check selector or date.")
        return
        
    print(f"Scraped {len(news_list)} news titles.")
    
    daily_dir = get_daily_dir(target_date, edition)
    output_path = os.path.join(daily_dir, "1_all_titles.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)
        
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    questions = [
        inquirer.List('date_option',
                      message="[scraper.py 독립 실행] 어느 날짜의 기사를 수집하시겠습니까?:",
                      choices=['오늘 (기본값)', '직접 입력 (YYYYMMDD)'],
                  ),
    ]
    answers = inquirer.prompt(questions)
    
    target_date = datetime.now().strftime("%Y%m%d")
    if answers['date_option'] == '직접 입력 (YYYYMMDD)':
        date_q = [
            inquirer.Text('custom_date', message="날짜를 입력하세요 (예: 20260908)")
        ]
        date_a = inquirer.prompt(date_q)
        target_date = date_a['custom_date']
        
    scrape_naver_ranking_news(target_date, edition='morning')
