# 수집할 뉴스 소스 목록 (전부 2026-08-04 접속 확인함)
import urllib.parse as up


def 구글뉴스(q: str, 기간: str = "1d", 한국: bool = True) -> str:
    """구글 뉴스 RSS 검색 주소를 만듭니다.

    개별 매체 RSS 는 자주 죽습니다(2026-08-04 실측: 디스이즈게임·인벤·블로터 전멸,
    Anthropic 은 아예 공식 RSS 가 없음). 키워드 검색은 그 영향을 받지 않습니다.
    """
    지역 = "hl=ko&gl=KR&ceid=KR:ko" if 한국 else "hl=en-US&gl=US&ceid=US:en"
    return f"https://news.google.com/rss/search?q={up.quote(f'{q} when:{기간}')}&{지역}"


# (분야, 이름, 주소). 분야는 화면에서 묶는 단위입니다.
SOURCES = [
    # --- AI · 클로드 ---
    ("AI·클로드", "구글뉴스(한)", 구글뉴스("앤스로픽 OR 클로드 OR \"AI 코딩\"")),
    ("AI·클로드", "구글뉴스(영)", 구글뉴스("Anthropic OR \"Claude AI\"", 한국=False)),
    ("AI·클로드", "Claude Code 릴리스",
     "https://github.com/anthropics/claude-code/releases.atom"),
    ("AI·클로드", "Hacker News", "https://hnrss.org/newest?q=Claude+OR+Anthropic"),
    ("AI·클로드", "OpenAI", "https://openai.com/news/rss.xml"),
    ("AI·클로드", "Google AI", "https://blog.google/technology/ai/rss/"),

    # --- 게임 개발 ---
    ("게임개발", "구글뉴스", 구글뉴스("게임개발 OR 유니티 OR 언리얼엔진")),
    ("게임개발", "Game Developer", "https://www.gamedeveloper.com/rss.xml"),
    ("게임개발", "Godot", "https://godotengine.org/rss.xml"),
    ("게임개발", "Unity", "https://blog.unity.com/feed"),

    # --- 유튜브 · 쇼츠 운영 ---
    # ⛔ 이 분야에는 구글뉴스 검색을 쓰지 않습니다. 2026-08-04 에 한글·영문 쿼리 4종을
    # 실측했는데 전부 노이즈가 압도적이었습니다("심현섭 하루 3억2천", "당진 온열질환 사망").
    # 구글 뉴스는 매체명까지 느슨하게 매칭해서, 국내 보도가 드문 좁은 실무 주제에는
    # 관련 없는 기사를 억지로 끌어옵니다. 아래 전용 매체 셋이 훨씬 정확합니다.
    ("유튜브·쇼츠", "YouTube 공식", "https://blog.youtube/rss/"),
    ("유튜브·쇼츠", "YouTube Creators",
     "https://www.youtube.com/feeds/videos.xml?channel_id=UCkRfArvrzheW2E7b6SVT7vQ"),
    ("유튜브·쇼츠", "TubeFilter", "https://www.tubefilter.com/feed/"),

    # --- 최신 IT · IT 이슈 ---
    ("IT이슈", "구글뉴스", 구글뉴스("IT 업계 OR 인공지능 OR 반도체")),
    # IT 신제품. ⛔ "신제품" 이라는 말 자체를 넣으면 안 됩니다 — 국내 뉴스에서 이 단어는
    # 식품·생활용품이 압도적입니다(2026-08-04 실측: 우유식빵·주방후드·오메가3·레고·담배).
    # ⛔ 괄호로 AND 를 걸어도 소용없습니다 — 구글뉴스 RSS 가 괄호를 안 지킵니다(잡음 23%).
    # **품목 이름만** 나열하는 것이 가장 정확했습니다 — 100건 중 잡음 0건.
    ("IT이슈", "구글뉴스(IT신제품)",
     구글뉴스("갤럭시 OR 아이폰 OR 맥북 OR 그래픽카드 OR \"AI PC\" OR 태블릿")),
    ("IT이슈", "ZDNet Korea", "https://feeds.feedburner.com/zdkorea"),
    ("IT이슈", "전자신문", "https://rss.etnews.com/Section901.xml"),
    ("IT이슈", "IT동아", "https://it.donga.com/feeds/rss/"),
    ("IT이슈", "네이버 D2", "https://d2.naver.com/d2.atom"),
    ("IT이슈", "The Verge", "https://www.theverge.com/rss/index.xml"),
    ("IT이슈", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("IT이슈", "TechCrunch", "https://techcrunch.com/feed/"),
    ("IT이슈", "Hacker News", "https://hnrss.org/frontpage?points=100"),
]

# 화면에 이 순서로 나옵니다.
분야순서 = ["AI·클로드", "게임개발", "유튜브·쇼츠", "IT이슈"]

# 제목에 이 말이 들어가면 버립니다. 국내 IT 일간지(전자신문·ZDNet)가 종합 섹션을 함께
# 내보내서 증시·정치·사건사고가 섞여 들어옵니다(2026-08-04 실측: 전자신문 25건 중 13건).
#
# ⚠ 늘릴 때는 반드시 실측하고 넣으십시오. 아래 명령이 무엇이 빠지는지 전부 보여 줍니다.
#     python -X utf8 -c "import collect;print('\n'.join(g['title'] for g in collect.버릴것()))"
# ⛔ IT 기사가 함께 걸리는 말은 넣지 않습니다 — 예를 들어 '실적' 은 반도체 실적 기사를,
#    '정부' 는 AI 정책 기사를 통째로 지웁니다. 좁은 말만 씁니다.
제외어 = [
    # 증시·금융 (기업 실적 숫자 기사. IT 기업이어도 제품 소식이 아닙니다)
    "증시", "코스피", "코스닥", "주가", "목표가", "공모주", "주식선물", "주식옵션",
    "배당", "환율", "채권", "어닝서프라이즈", "영업익", "순이익", "투자의견",
    # 정치·행정
    "대통령", "국회", "본회의", "여야", "의원", "선거", "개각", "탄핵", "국정감사",
    # 사건사고
    "사망", "숨진", "추락", "화재", "참사", "감염", "확진", "구속", "피의자",
    "음주운전", "성추행",
    # 부동산·생활
    "부동산", "아파트", "분양", "전세", "우유", "배추", "급식", "등하교",
]
