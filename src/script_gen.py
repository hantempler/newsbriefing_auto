import json
import os
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from datetime import datetime
import inquirer
import sys

# Add src to Python path if run standalone
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GCP_PROJECT_ID, GCP_LOCATION, get_daily_dir, EDITION_CONFIG, BASE_DIR

def scrape_naver_news_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        article_body = soup.find("article", id="dic_area")
        if not article_body:
            return None
            
        # 첫 번째 이미지 추출
        img_tag = article_body.find("img")
        img_url = None
        if img_tag:
            img_url = img_tag.get("data-src") or img_tag.get("src")
            
        full_text = article_body.get_text(separator="\n").strip()
        
        if len(full_text) > 30:
            return {
                "text": full_text,
                "img_url": img_url
            }
        return None
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return None

def run_script_gen(target_date=None, edition='morning'):
    client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)
    
    daily_dir = get_daily_dir(target_date, edition)
    titles_path = os.path.join(daily_dir, "1_all_titles.json")
    if not os.path.exists(titles_path):
        print(f"File not found: {titles_path}. Run scraper first.")
        return None
        
    with open(titles_path, "r", encoding="utf-8") as f:
        all_news = json.load(f)
        
    if not all_news:
        print("No news available to generate script.")
        return None
        
    print(f"Loaded {len(all_news)} news titles.")
    
    # 1. 1차 큐레이션: 제목 기반으로 상위 3개 이슈 링크 추출
    print("Asking Gemini to select the top 3 issues...")
    
    # 히스토리 파일 로드 및 중복 배제 로직
    if not target_date:
        from datetime import timezone, timedelta
        target_date = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")

    # KST 기준 날짜/요일 계산 (Gemini 프롬프트에 주입용)
    _WEEKDAYS_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    _dt = datetime(int(target_date[:4]), int(target_date[4:6]), int(target_date[6:8]))
    
    import holidays
    kr_holidays = holidays.KR(years=_dt.year)
    holiday_name = kr_holidays.get(_dt.date())
    
    if holiday_name:
        kst_date_str = f"{target_date[:4]}년 {int(target_date[4:6])}월 {int(target_date[6:8])}일 ({_WEEKDAYS_KO[_dt.weekday()]}, {holiday_name})"
        holiday_context_prompt = f"\n[중요 지침] 오늘은 법정공휴일인 '{holiday_name}'입니다. 대본 인사말(hook 또는 closing)에 반드시 '{holiday_name}'(예: 연휴 잘 보내고 계신가요 등)와 관련된 시즈널한 언급을 자연스럽게 포함하여 시청자와 친밀감을 형성해주세요."
    else:
        kst_date_str = f"{target_date[:4]}년 {int(target_date[4:6])}월 {int(target_date[6:8])}일 ({_WEEKDAYS_KO[_dt.weekday()]})"
        holiday_context_prompt = ""

    history_path = os.path.join(BASE_DIR, "data", f"history_{target_date}.json")
    history_data = {}
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            pass
            
    excluded_titles = []
    for ed, titles in history_data.items():
        if ed != edition:  # 다른 에디션(예: 오전)에서 사용된 기사 배제
            excluded_titles.extend(titles)
            
    exclusion_text = ""
    if excluded_titles:
        exclusion_text = "\n\n[중요] 아래 기사들은 오늘 이전 브리핑에서 이미 다루었으므로, 이와 관련된 주제나 이슈는 철저히 제외하고 완전히 새로운 이슈들로만 선정해주세요:\n"
        for t in excluded_titles:
            exclusion_text += f"- {t}\n"
    
    titles_list_str = ""
    for i, news in enumerate(all_news):
        titles_list_str += f"[{i}] {news['title']}\n"
        
    if edition == 'lunch':
        prompt_topic_condition = "이 중에서 점심시간에 가볍고 재미있게 읽을 수 있는 라이프스타일, 연예, 문화, IT/트렌드, 유머 등 무겁지 않은 주제의 흥미로운 이슈 6가지를 우선순위대로 골라주세요. 정치/사건사고/무거운 경제 뉴스는 피해주세요."
    elif edition in ('weekend_morning', 'weekend_evening'):
        prompt_topic_condition = "이 중에서 주말에 즐길 수 있는 라이프스타일, 레저, 여행, 문화, 맛집, 연예/엔터테인먼트, IT 트렌드 등 풍요롭고 가벼운 주제의 이슈 5가지와, 이번 주 놓치면 안 될 핵심 시사 이슈 1가지를 합쳐 총 6가지를 우선순위대로 골라주세요. 무거운 정치 분쟁이나 사건사고 위주의 뉴스는 피해주세요."
    else:
        prompt_topic_condition = "이 중에서 2040 직장인들이 가장 관심 가질 만한 핵심 이슈 6가지를 우선순위대로 골라주세요."

    selection_prompt = f"""
    아래는 오늘 네이버 뉴스의 전체 언론사 랭킹 기사 제목들입니다.
    {prompt_topic_condition}
    (이미지가 없는 기사를 대비해 예비로 넉넉히 6개를 선정합니다.)
    반드시 서로 다른 주제(예: 하나는 부동산, 하나는 경제, 하나는 사회현상 등)로 선정해야 합니다.{exclusion_text}
    선정한 기사의 인덱스 번호를 JSON 배열 형태로만 출력해주세요. (예: [12, 45, 102, 5, 8, 90])
    
    기사 목록:
    {titles_list_str}
    """
    
    selection_response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=selection_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    
    try:
        selected_indices = json.loads(selection_response.text)
    except Exception as e:
        print("Failed to parse JSON response from Gemini. Fallback to top 6.")
        selected_indices = [0, 1, 2, 3, 4, 5]
        
    print(f"Selected indices: {selected_indices}")
    
    selected_news = []
    # 이슈 번호 매기기를 위한 변수
    issue_counter = 1
    
    for idx in selected_indices:
        if len(selected_news) >= 3:
            break
            
        if 0 <= idx < len(all_news):
            news_item = all_news[idx]
            print(f"Checking: {news_item['title']}")
            
            scraped_data = scrape_naver_news_content(news_item['link'])
            
            # 이미지가 없는 기사는 다른 기사로 대체 (건너뜀)
            if not scraped_data or not scraped_data.get('img_url'):
                print("  -> No image found. Skipping to next article.")
                continue
                
            img_path = None
            # 이미지 다운로드 및 저장
            try:
                img_res = requests.get(scraped_data['img_url'], headers={"User-Agent": "Mozilla/5.0"})
                if img_res.status_code == 200:
                    img_filename = f"2_img_issue{issue_counter}.jpg"
                    img_path = os.path.join(daily_dir, img_filename)
                    with open(img_path, "wb") as img_f:
                        img_f.write(img_res.content)
                    print(f"  -> Downloaded image: {img_filename}")
            except Exception as e:
                print(f"  -> Failed to download image: {e}")
            
            selected_news.append({
                "source": news_item.get('source', 'Unknown'),
                "title": news_item['title'],
                "link": news_item['link'],
                "description": scraped_data['text'],
                "image_path": img_path
            })
            print(f"  -> Successfully selected as Issue {issue_counter}")
            issue_counter += 1
                
    if not selected_news:
        print("Failed to scrape selected news bodies.")
        return None
        
    selected_path = os.path.join(daily_dir, "2_selected_articles.json")
    with open(selected_path, "w", encoding="utf-8") as f:
        json.dump(selected_news, f, ensure_ascii=False, indent=2)
        
    # 2. 대본 작성 (5단 분리 JSON 구조)
    print("Generating 5-part summary script...")
    
    context = ""
    for i, news in enumerate(selected_news):
        context += f"이슈 {i+1}:\n제목: {news['title']}\n내용: {news['description']}\n\n"
        
    system_instruction = (
        "당신은 2040 직장인 타겟의 정보 전달형 쇼츠(1분 이내) 스크립트 작가입니다.\n"
        f"[필수 준수] 오늘 날짜는 정확히 '{kst_date_str}'입니다. "
        "대본 어디에도 이 날짜/요일과 다른 표현을 절대 사용하지 마세요. "
        "날짜나 요일을 언급해야 할 경우 반드시 위 날짜 정보만 사용하세요."
        f"{holiday_context_prompt}"
    )
    
    script_prompt = f"""
    [오늘 날짜: {kst_date_str}] — 이 날짜/요일을 대본에서 언급할 때 반드시 그대로 사용할 것.
    아래는 오늘 가장 핵심적인 3가지 이슈(기사 본문 전체)입니다.
    이 3가지 이슈를 속도감 있게 전달하고 브리핑하는 1분 분량의 쇼츠 대본을 작성해주세요.
    
    조건:
    1. 대본은 반드시 아래의 JSON 객체 형식으로만 출력해야 합니다.
    2. 각 파트는 영상과 음성이 동기화될 단위입니다.
    3. 나레이션 텍스트만 출력할 것 (장면 설명, 지시문 등은 절대 제외)
    4. 자막은 렌더러가 자동으로 2줄 처리하므로, 인위적인 줄바꿈(\n) 없이 자연스러운 문장으로 작성할 것.
    
    출력 형식 (JSON):
    {{
        "hook_title": "오늘 브리핑할 3가지 핵심 뉴스의 내용을 관통하면서도 2040 직장인의 뼈를 때리거나 공감을 이끌어내는 15자 내외의 강렬한 훅 문구 (단순하고 정형화된 인사가 아니라, 반드시 '오늘 선정된 기사 데이터'의 내용과 맥락이 이어지는 센스 있는 문장으로 작성할 것. 화면 중앙 노출용)",
        f'"hook": "{EDITION_CONFIG[edition]["hook_prompt"]}",'
        "issue1": "첫 번째 이슈에 대한 짧고 명확한 요약",
        "issue2": "두 번째 이슈에 대한 짧고 명확한 요약",
        "issue3": "세 번째 이슈에 대한 짧고 명확한 요약",
        f'"closing": "{EDITION_CONFIG[edition]["closing_prompt"]}",'
        f'"closing_quote": "{EDITION_CONFIG[edition]["closing_quote_prompt"]}"'
    }}
    
    이슈 데이터:
    {context}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=script_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
        )
    )
    
    script_text = response.text.strip()
    
    output_path = os.path.join(daily_dir, "3_script.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script_text)
        
    print(f"Generated script saved to {output_path}")
    print("--- Script ---")
    print(script_text)
    print("--------------")
    
    # 생성 완료 후 현재 에디션의 기사 제목을 히스토리에 저장
    current_edition_titles = [news['title'] for news in selected_news]
    history_data[edition] = current_edition_titles
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
        
    print(f"History updated for edition '{edition}'.")
    
    return script_text

if __name__ == "__main__":
    from config import DATA_DIR
    
    available_folders = []
    if os.path.exists(DATA_DIR):
        available_folders = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    
    if not available_folders:
        print("생성된 데이터 폴더가 없습니다. scraper.py를 먼저 실행하세요.")
        sys.exit(1)
        
    available_folders.sort(reverse=True)
    
    questions = [
        inquirer.List('target_folder',
                      message="[script_gen.py 독립 실행] 작업할 대상 날짜(폴더)를 선택하세요:",
                      choices=available_folders,
                  ),
    ]
    answers = inquirer.prompt(questions)
    
    if answers:
        selected_folder = answers['target_folder']
        target_date = selected_folder.replace("-", "")
        print(f"Target Date: {target_date}")
        run_script_gen(target_date)
