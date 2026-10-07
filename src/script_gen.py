import os
import json
from google import genai
from google.genai import types
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def generate_script(news_data: list, daily_dir: str = None):
    if daily_dir is None:
        daily_dir = config.DATA_DIR
        
    client = genai.Client(vertexai=True, project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
    
    import datetime
    from zoneinfo import ZoneInfo
    today_kst = datetime.datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m월 %d일")
    
    news_json = json.dumps(news_data or [], ensure_ascii=False, indent=2)
    prompt = f"""
당신은 대한민국 최고의 메인 뉴스 객원 AI 앵커이자, 날카로운 분석력을 가진 논설위원입니다.
오늘 발생한 분야별(정치, 경제, 사회, 세계, IT, 연예, 스포츠, 날씨) 원문 요약 데이터는 다음과 같습니다:

{news_json}

위 데이터를 바탕으로 다음 조건에 맞춰 **최대 3분을 절대 넘지 않는 분량**의 유튜브 영상 뉴스 브리핑 대본을 작성하세요.

[중요 조건]
1. 출력은 오직 **JSON 형식**이어야 합니다. 백틱(```json) 없이 바로 JSON 객체만 출력해 주세요.
2. `cover_title`: 영상 첫 화면에 노출될 짧고 명확한 제목 (예: "{today_kst} 종합 뉴스". 반드시 '{today_kst}' 라는 오늘 날짜를 사용하세요.)
3. **팩트체크 엄수**: 기사 본문에 '예정', '추진 중', '논의' 등 아직 확정되거나 완료되지 않은 미래의 사건(예: 누리호 5차 발사 예정)을 절대 "성공했다", "완료했다" 등 과거형으로 지어내지(Hallucination) 마세요. 원문 본문의 시제와 사실관계를 100% 엄격하게 지켜야 합니다.
4. `script_sections`: 대본을 여러 개의 객체로 배열로 구성해 주세요.
    - **주의사항**: `caption`이나 `narration`에 漢字(한자)나 특수기호(예: 與, 野, 中, ☒)는 절대 사용하지 마세요. 모두 순수 한글로만 작성해야 합니다.
    - 첫 번째 객체(오프닝): `narration`에 "시청자 여러분 안녕하십니까, 오늘 하루 반드시 알아야 할 핵심 뉴스 브리핑입니다." 등 신뢰감 있는 오프닝. `image_url`은 "".
    - 본문 객체들: 정치, 경제, 사회, 세계, IT, 과학 등 가장 중요한 뉴스를 **반드시 정확히 5개 또는 6개 선별**하여 다룹니다 (본문 뉴스의 개수가 4개 이하여도 절대 안 되며, 6개를 초과해도 절대 안 됩니다). 각 뉴스당 반드시 **정확히 3개의 문장(팩트 -> 배경 -> 평가)**으로 작성하세요. 첫 문장은 핵심 팩트, 두 번째 문장은 그 사안이 발생한 배경이나 파급효과, 세 번째 문장은 사안에 대한 평가입니다. 단, 평가는 어느 한쪽으로 치우치지 않는 **완벽하게 중립적이고 냉철한 평론가**의 시각을 유지해야 합니다. `image_url`, `source_publisher`, `source_url`은 제공된 기사의 데이터를 찾아 그대로 넣으세요.
    - 마지막 객체(클로징): 단순 사실 나열이나 요약, "오늘의 뉴스, 한 줄 요약입니다" 같은 식상한 도입부는 절대 쓰지 마세요. 오늘 다룬 전체 뉴스들을 하나로 꿰뚫는 **'촌철살인의 날카롭고 뼈 있는 비평 한마디(한 문장)'**를 작성하세요. 이 문장이 전체 콘텐츠의 핵심입니다. (예: "기득권의 밥그릇 챙기기와 소모적인 정쟁 속에서도, 우주를 향한 누리호 발사처럼 묵묵히 내일을 준비해야 하는 하루였습니다.") 날씨 멘트는 이곳에 포함하지 마세요. `image_url`, `source_publisher`, `source_url`은 "".
    - `caption`: 화면에 표시할 핵심 자막 (마지막 클로징 객체의 자막은 무조건 "오늘의 주요뉴스"로 고정하세요)
    - `source_publisher`: 이 기사를 쓴 원문 언론사명 (제공된 데이터의 publisher)
    - `source_url`: 이 기사의 원문 링크 (제공된 데이터의 url)
    - `bg_keyword`: Pexels 검색용 영어 장면 키워드 (예: news studio, stock 일자, clear sky 등. 사진이 없는 경우 대비)
    - 전체 `narration` 분량은 공백 포함 500자 이내로 맞추세요.
6. `news_summary_list`: 영상 마지막에 띄울 분야별 뉴스 요약 리스트. 본문에서 다룬 기사들을 `["[정치] 여당 영화제 개막작 취소 요구", "[사회] 유해진 신변보호 결정", ...]` 와 같이 각 분야별로 요약하여 문자열 배열로 만들어 주세요. (항목 수는 다룬 뉴스 개수와 동일하게 4~5개)
7. `weather_list`: 제공된 날씨 데이터 텍스트를 파싱하여, **반드시 다음 10개 도시(서울, 인천, 춘천, 강릉, 대전, 전주, 광주, 대구, 부산, 제주)**의 날씨 정보를 정확히 순서대로 객체 배열로 만들어 주세요. 누락되는 도시가 없어야 합니다. 각 객체는 `{{"city": "서울", "temp": "18.8°", "status": "맑음"}}` 형태입니다.

JSON 포맷 예시:
{{
    "cover_title": "{today_kst} 종합 뉴스",
    "script_sections": [
        {{"narration": "안녕하십니까, 종합 뉴스입니다.", "caption": "오늘의 종합 뉴스", "image_url": "", "source_publisher": "", "source_url": "", "bg_keyword": "news studio"}},
        {{"narration": "여당이 영화제 개막작 취소를 요구했습니다. 해당 작품이 특정 정치적 시각을 담고 있다는 이유에서 비롯된 갈등입니다. 예술의 자유 보장과 공공지원금의 중립성이라는 가치가 팽팽하게 맞서고 있습니다.", "caption": "[정치] 여당, 영화제 개막작 취소 요구", "image_url": "https://...", "source_publisher": "KBS", "source_url": "https://news.naver.com/...", "bg_keyword": "parliament"}},
        {{"narration": "기득권의 밥그릇 챙기기와 소모적인 정쟁 속에서도, 우주를 향한 누리호 발사처럼 묵묵히 내일을 준비해야 하는 하루였습니다.", "caption": "오늘의 주요뉴스", "image_url": "", "source_publisher": "", "source_url": "", "bg_keyword": "clear sky"}}
    ],
    "news_summary_list": [
        "[정치] 여당 영화제 개막작 취소 요구",
        "[사회] 금융권 해킹 비상 체제 돌입"
    ],
    "weather_list": [
        {{"city": "서울", "temp": "18.8°", "status": "맑음"}},
        {{"city": "부산", "temp": "20.7°", "status": "맑음"}}
    ],
    "useful_source_title": "출처: 네이버 뉴스 헤드라인",
    "useful_source_url": "https://news.naver.com"
}}
"""
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        result = json.loads(response.text.strip())
        result["topic"] = "퇴근길 종합 뉴스"
        sections = result.get("script_sections", [])
        
        for section in sections:
            if not all(k in section for k in ("narration", "caption", "image_url")):
                raise ValueError("각 대본 구간에 narration, caption, image_url이 필요합니다.")
            section["text"] = section["narration"]
        
        script_path = os.path.join(daily_dir, "3_script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        return result
    except Exception as e:
        print(f"스크립트 생성 오류: {e}")
        return None

if __name__ == "__main__":
    test_news = [{"category": "정치", "title": "정치 뉴스 테스트"}]
    print("대본 생성 테스트:")
    res = generate_script(test_news)
    print(json.dumps(res, ensure_ascii=False, indent=2))
