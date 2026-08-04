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
