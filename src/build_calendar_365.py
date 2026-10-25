"""스타이즈본 한국 시청자 맞춤 과거 아카이브 캘린더 (build_calendar_365.py).

[운영 철칙]:
1. 10월 26일 이후의 모든 일자는 실시간 3인 후보 AI 트렌드 스카우터(star_trend_scout.py)가
   매일 당일 아침 Google Search Grounding을 통해 실시간 발굴/검증하여 data/calendar_db.json에 누적 저장합니다.
2. 본 파일은 10월 15일 ~ 10월 25일까지의 초기 11개 일자 아카이브 보존용으로만 사용되며,
   실제 런타임 런처(01_star_script.py)의 인물 선정에 개입하지 않습니다.
"""
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CALENDAR_FILE = DATA_DIR / "calendar_db.json"

# 10월 15일 ~ 10월 25일 과거 아카이브 라인업 (AM 생일 / PM 기일)
KOREAN_CALENDAR_OCT = {
    "10-15": {
        "am": {
            "person_name": "메수트 외질",
            "person_name_en": "Mesut Özil",
            "wikidata_id": "Q1792",
            "category": "Sports / Football",
            "event_date": "1988-10-15",
            "keywords": ["도움의 마법사", "레알 마드리드 10번", "호날두 영혼의 단짝", "박지성 시대 축구"],
            "brief": "박지성 해외축구 전성기 시절 호날두 발밑에 마법 같은 패스를 찔러주던 '어시스트의 신'. 한국 축구팬들이 가장 사랑한 천재 미드필더.",
            "verified": True
        },
        "pm": {
            "person_name": "폴 앨런",
            "person_name_en": "Paul Allen",
            "wikidata_id": "Q162005",
            "category": "Tech / Business",
            "event_date": "2018-10-15",
            "keywords": ["마이크로소프트 공동창업", "빌 게이츠 단짝", "시애틀 구단주", "기부왕"],
            "brief": "빌 게이츠와 함께 전 세계 PC 시대를 연 마이크로소프트 공동 창업자 (2018년 10월 15일 별세).",
            "verified": True
        }
    },
    "10-16": {
        "am": {
            "person_name": "김아중",
            "person_name_en": "Kim Ah-joong",
            "wikidata_id": "Q494723",
            "category": "K-Culture / Actor",
            "event_date": "1982-10-16",
            "keywords": ["미녀는 괴로워", "마리아 Maria 신드롬", "대종상 여우주연상", "흥행 퀸"],
            "brief": "영화 '미녀는 괴로워'로 660만 관객을 홀리고 OST 'Maria'로 전국 가요계를 씹어먹었던 대한민국 역대급 흥행 퀸.",
            "verified": True
        },
        "pm": {
            "person_name": "리암 페인",
            "person_name_en": "Liam Payne",
            "wikidata_id": "Q275637",
            "category": "Music / Boyband",
            "event_date": "2024-10-16",
            "keywords": ["원디렉션", "전설의 보이밴드", "What Makes You Beautiful", "전 세계 추모 물결"],
            "brief": "한국 1020세대에게도 절대적인 사랑을 받았던 21세기 원탑 보이밴드 '원디렉션(One Direction)'의 메인 보컬 (2024년 10월 16일 별세).",
            "verified": True
        }
    },
    "10-17": {
        "am": {
            "person_name": "에미넴",
            "person_name_en": "Eminem",
            "wikidata_id": "Q5608",
            "category": "Music / Hip-Hop",
            "event_date": "1972-10-17",
            "keywords": ["랩 갓", "한국 내한 손하트", "Lose Yourself", "현대카드 슈퍼콘서트"],
            "brief": "한국 내한 당시 관객들의 떼창에 감격해 힙합 역사상 최초로 머리 위 '손하트'를 날렸던, 한국인이 가장 사랑하는 살아있는 랩의 신.",
            "verified": True
        },
        "pm": {
            "person_name": "프레데리크 쇼팽",
            "person_name_en": "Frédéric Chopin",
            "wikidata_id": "Q1268",
            "category": "Music / Classical",
            "event_date": "1849-10-17",
            "keywords": ["조성진 우승 쇼팽 콩쿠르", "피아노의 시인", "야상곡", "심장 폴란드 안치"],
            "brief": "피아니스트 조성진의 콩쿠르 우승으로 한국인에게 더욱 각별해진 음악가. 유언에 따라 몸은 파리에, 심장은 조국 폴란드에 묻힌 감동의 레전드.",
            "verified": True
        }
    },
    "10-18": {
        "am": {
            "person_name": "장클로드 반담",
            "person_name_en": "Jean-Claude Van Damme",
            "wikidata_id": "Q308840",
            "category": "Hollywood / Action",
            "event_date": "1960-10-18",
            "keywords": ["다리 찢기의 제왕", "비디오 대여점 3대장", "어벤저", "스트리트 파이터"],
            "brief": "성룡, 아놀드와 함께 90년대 한국 비디오 대여점을 주름잡았던 '원조 액션 레전드'. 달리는 트럭 사이 180도 다리 찢기로 유명한 상남자.",
            "verified": True
        },
        "pm": {
            "person_name": "콜린 파월",
            "person_name_en": "Colin Powell",
            "wikidata_id": "Q15088",
            "category": "Modern History / Leadership",
            "event_date": "2021-10-18",
            "keywords": ["최초의 흑인 국무장관", "걸프전 사령관", "리더십의 아이콘"],
            "brief": "할렘가 출신으로 시작해 미 합참의장과 최초 흑인 국무장관까지 오른 21세기 현대사의 입지전적 거물 (2021년 10월 18일 별세).",
            "verified": True
        }
    },
    "10-19": {
        "am": {
            "person_name": "김지원",
            "person_name_en": "Kim Ji-won",
            "wikidata_id": "Q268069",
            "category": "K-Culture / Actor",
            "event_date": "1992-10-19",
            "keywords": ["눈물의 여왕 홍해인", "나의 해방일지 추앙", "태양의 후예", "시청률 24.9% 퀸"],
            "brief": "'눈물의 여왕'으로 대한민국 최고 시청률 24.9%를 찍으며 전 국민을 울리고 웃긴 흥행 퀸. 오란씨걸에서 톱배우로 우뚝 선 주인공.",
            "verified": True
        },
        "pm": {
            "person_name": "조너선 스위프트",
            "person_name_en": "Jonathan Swift",
            "wikidata_id": "Q41166",
            "category": "Literature / Author",
            "event_date": "1745-10-19",
            "keywords": ["걸리버 여행기", "소인국 거인국", "풍자 문학의 거장"],
            "brief": "'걸리버 여행기'로 인간 사회의 위선과 모순을 날카롭게 풍자한 아일랜드 문학의 불멸의 거장 (1745년 10월 19일 별세).",
            "verified": True
        }
    },
    "10-20": {
        "am": {
            "person_name": "스눕 독",
            "person_name_en": "Snoop Dogg",
            "wikidata_id": "Q6096",
            "category": "Music / Hip-Hop",
            "event_date": "1971-10-20",
            "keywords": ["싸이 행오버(Hangover)", "쇼미더머니 심사위원", "한국 소주 러브", "힙합 대부"],
            "brief": "싸이와 함께 노래방에서 소주를 마시는 뮤비로 한국을 뒤흔들고, '쇼미더머니4' 게스트 심사위원으로 깜짝 출연했던 친한파 힙합 대부.",
            "verified": True
        },
        "pm": {
            "person_name": "버트 랭커스터",
            "person_name_en": "Burt Lancaster",
            "wikidata_id": "Q160528",
            "category": "Hollywood / Cinema",
            "event_date": "1994-10-20",
            "keywords": ["지상에서 영원으로", "오스카 남우주연상", "할리우드 황금기 전설"],
            "brief": "영화 '지상에서 영원으로'와 '엘머 갠트리'로 아카데미 남우주연상을 수상한 할리우드 황금기의 전설적 대배우 (1994년 10월 20일 별세).",
            "verified": True
        }
    },
    "10-21": {
        "am": {
            "person_name": "차준환",
            "person_name_en": "Cha Jun-hwan",
            "wikidata_id": "Q18719001",
            "category": "Sports / Figure Skating",
            "event_date": "2001-10-21",
            "keywords": ["한국 피겨 간판", "세계선수권 은메달", "피겨 왕자", "빙판의 아이돌"],
            "brief": "김연아 이후 대한민국 피겨 역사상 최초로 세계선수권 은메달을 목에 걸며 한국 남자 피겨의 역사를 새로 쓴 빙판 위의 프린스.",
            "verified": True
        },
        "pm": {
            "person_name": "허레이시오 넬슨",
            "person_name_en": "Horatio Nelson",
            "wikidata_id": "Q83235",
            "category": "World / History",
            "event_date": "1805-10-21",
            "keywords": ["트라팔가르 해전", "영국의 이순신", "영국 국민 영웅"],
            "brief": "\"영국은 모든 이가 자신의 의무를 다할 것을 기대한다\"는 명언과 함께 트라팔가르 해전에서 조국을 지켜낸 불멸의 제독 (1805년 10월 21일 전사).",
            "verified": True
        }
    },
    "10-22": {
        "am": {
            "person_name": "기안84",
            "person_name_en": "Kian84",
            "wikidata_id": "Q16183492",
            "category": "K-Culture / Enter & Webtoon",
            "event_date": "1984-10-22",
            "keywords": ["MBC 연예대상 대상", "나 혼자 산다", "태어난 김에 세계일주", "패션왕 작가"],
            "brief": "네이버 웹툰 '패션왕' 작가에서 '나 혼자 산다'와 '태계일주'로 비연예인 최초 MBC 연예대상 대상까지 거머쥔 21세기 대한민국 최고의 자연인 스타.",
            "verified": True
        },
        "pm": {
            "person_name": "폴 세잔",
            "person_name_en": "Paul Cézanne",
            "wikidata_id": "Q35548",
            "category": "Art / Painter",
            "event_date": "1906-10-22",
            "keywords": ["근대 회화의 아버지", "생트빅투아르산", "사과 하나로 파리를 놀라게 하겠다"],
            "brief": "피카소와 마티스가 '우리 모두의 아버지'라 부르며 현대 미술의 문을 활짝 열어젖힌 후기 인상주의의 위대한 거장 (1906년 10월 22일 별세).",
            "verified": True
        }
    },
    "10-23": {
        "am": {
            "person_name": "라이언 레이놀즈",
            "person_name_en": "Ryan Reynolds",
            "wikidata_id": "Q192682",
            "category": "Hollywood / Cinema",
            "event_date": "1976-10-23",
            "keywords": ["복면가왕 유니콘", "런닝맨 출연", "데드풀 그 자체", "한국 사랑 1등"],
            "brief": "'복면가왕'에 가면을 쓰고 나와 전 국민을 경악시키고, '런닝맨'에서 유재석과 환상의 티키타카를 펼쳤던 한국인이 가장 사랑하는 데드풀.",
            "verified": True
        },
        "pm": {
            "person_name": "피트 번즈",
            "person_name_en": "Pete Burns",
            "wikidata_id": "Q312061",
            "category": "Global Pop / Synth-Pop",
            "event_date": "2016-10-23",
            "keywords": ["Dead or Alive", "You Spin Me Round", "80년대 신스팝 제왕", "불멸의 댄스 명곡"],
            "brief": "전 세계를 뒤흔든 불멸의 댄스 팝 명곡 'You Spin Me Round'로 80년대 신스팝의 황금기를 이끈 독보적인 카리스마의 레전드 보컬 (2016년 10월 23일 별세).",
            "verified": True
        }
    },
    "10-24": {
        "am": {
            "person_name": "웨인 루니",
            "person_name_en": "Wayne Rooney",
            "wikidata_id": "Q266613",
            "category": "Sports / Football",
            "event_date": "1985-10-24",
            "keywords": ["맨유 레전드", "박지성", "축구 영웅", "악동"],
            "brief": "한국 축구 팬들의 가슴 속에 영원히 기억될 맨유의 심장, 웨인 루니! 박지성과의 환상적인 호흡으로 감동을 선사한 레전드.",
            "verified": True
        },
        "pm": {
            "person_name": "로자 파크스",
            "person_name_en": "Rosa Parks",
            "wikidata_id": "Q41921",
            "category": "Human Rights / Leader",
            "event_date": "2005-10-24",
            "keywords": ["시민권 운동", "몽고메리 버스 보이콧", "인종차별 저항"],
            "brief": "2005년 10월 24일 별세한 로자 파크스는 작은 용기가 세상을 바꿀 수 있음을 보여준 위대한 인권 운동가입니다.",
            "verified": True
        }
    },
    "10-25": {
        "am": {
            "person_name": "케이티 페리",
            "person_name_en": "Katy Perry",
            "wikidata_id": "Q42449",
            "category": "Music / Pop",
            "event_date": "1984-10-25",
            "keywords": ["내한공연 태극기", "Firework", "슈퍼볼 하프타임 쇼", "팝의 여왕"],
            "brief": "한국 내한 공연 당시 무대에서 대형 태극기를 두르고 'Firework'를 열창해 한국 팬들을 열광시켰던 글로벌 팝 디바.",
            "verified": True
        },
        "pm": {
            "person_name": "이건희",
            "person_name_en": "Lee Kun-hee",
            "wikidata_id": "Q319985",
            "category": "Tech / Business",
            "event_date": "2020-10-25",
            "keywords": ["삼성전자 회장", "마누라와 자식 빼고 다 바꿔라", "애니콜 화형식", "반도체 1위 신화"],
            "brief": "\"마누라와 자식 빼고 다 바꿔라\"는 프랑크푸르트 선언과 500억 불량 애니콜 화형식으로 삼성을 세계 1위 반도체 제국으로 만든 신화적 경영자 (2020년 10월 25일 별세).",
            "verified": True
        }
    }
}

# 과거 아카이브 캘린더 (10월 15일 ~ 10월 25일 총 11개 일자 보존용)
KOREAN_CALENDAR_ALL = KOREAN_CALENDAR_OCT


def build_database():
    output = {
        "version": "4.2",
        "description": "스타이즈본 한국 시청자 맞춤 100% 현대 스타 마스터 캘린더 (10-15 ~ 10-25 아카이브)",
        "policy": {
            "target_audience": "Korean YouTube Shorts Viewers (1030세대 & 대중)",
            "korean_familiarity_priority": True,
            "min_year": 1960,
            "period": "10-15 ~ 10-25 (Historical Archive)",
            "total_dates": len(KOREAN_CALENDAR_ALL),
            "total_stars": len(KOREAN_CALENDAR_ALL) * 2,
            "categories": [
                "K-Culture (드라마/예능/아이돌/가요 레전드)",
                "Global Pop (내한 떼창/손하트)",
                "Hollywood (복면가왕/런닝맨/주말의명화)",
                "Sports (해외축구/올림픽)",
                "Tech & History (대한민국 경제/글로벌 혁신)"
            ]
        },
        "calendar": KOREAN_CALENDAR_ALL
    }

    CALENDAR_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Archive Calendar] 10월 15일 ~ 10월 25일 과거 아카이브 동기화 완료!")
    print(f"                   저장 경로: {CALENDAR_FILE}")
    print(f"                   등록 일자: {len(KOREAN_CALENDAR_ALL)}개 일자")


if __name__ == "__main__":
    build_database()
