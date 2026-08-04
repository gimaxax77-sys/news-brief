# 수집·중복제거·신규판정·화면·알림이 망 없이도 맞게 도는지 확인
import datetime as dt
import os
import tempfile

import collect
import render
import brief

UTC = dt.timezone.utc
지금 = dt.datetime.now(UTC)


def 기사(제목, 분야="IT이슈", 출처="테스트", 시각=None):
    return {"title": 제목, "url": "https://example.com/" + 제목, "at": 시각 or 지금,
            "topic": 분야, "source": 출처}


# --- 지문: 같은 기사는 주소가 달라도 한 번만 센다 ---
a = {"title": "클로드가 해킹을 인정했다", "url": "https://a.com/1?utm=x"}
b = {"title": "클로드가  해킹을 인정했다!", "url": "https://b.com/9"}
assert collect.지문(a) == collect.지문(b), "공백·문장부호·주소가 달라도 같은 기사로 봐야 합니다"
assert collect.지문(a) != collect.지문({"title": "전혀 다른 제목"}), "다른 기사가 같게 나옵니다"

# --- 매체분리: 같은 기사가 매체 수만큼 중복되던 것을 막는다 ---
assert collect.매체분리("백악관 AI 회동 - Reuters") == ("백악관 AI 회동", "Reuters")
assert collect.매체분리("백악관 AI 회동 - The Japan Times")[0] == "백악관 AI 회동", "매체명이 안 떨어집니다"
assert collect.매체분리("매체명 없는 제목") == ("매체명 없는 제목", ""), "구분자가 없으면 그대로 둬야 합니다"
긴꼬리 = "제목 - " + "가" * 40
assert collect.매체분리(긴꼬리) == (긴꼬리, ""), "뒤가 길면 매체명이 아니라 제목의 일부입니다"

# --- 최신만: 오래된 것은 버리고, 날짜 없는 것은 남기고, 상한을 지킨다 ---
목록 = ([기사(f"새것{i}") for i in range(40)]
        + [기사("오래된것", 시각=지금 - dt.timedelta(days=10))]
        + [{**기사("날짜없음"), "at": None}])
남은것 = collect.최신만(목록, 상한=25, 일수=3)
제목들 = {g["title"] for g in 남은것}
assert len(남은것) == 25, f"상한 25를 안 지킵니다: {len(남은것)}"
assert "오래된것" not in 제목들, "10일 지난 기사가 남았습니다"
남은것2 = collect.최신만([{**기사("날짜없음"), "at": None}], 상한=25, 일수=3)
assert len(남은것2) == 1, "날짜 없는 기사를 버리면 안 됩니다(검색 피드에 흔합니다)"

# --- 파싱: 문서 뒤에 잡음이 붙어도 읽어 낸다 ---
피드 = (b'<?xml version="1.0"?><rss><channel><item><title>A</title>'
        b'<link>https://x.com/a</link><pubDate>Mon, 04 Aug 2026 01:00:00 +0000</pubDate>'
        b'</item></channel></rss>' + b'<!-- junk -->trailing')
얻은것 = collect.파싱(피드)
assert len(얻은것) == 1 and 얻은것[0]["title"] == "A", f"잡음 붙은 피드 파싱 실패: {얻은것}"
assert 얻은것[0]["at"] is not None, "pubDate 를 못 읽었습니다"

# --- 신규 판정 + 상태 저장 ---
with tempfile.TemporaryDirectory() as work:
    p = os.path.join(work, "state.json")
    전체 = [기사("첫째"), 기사("둘째")]
    assert collect.이전기록(p) == [], "기록이 없으면 빈 목록이어야 합니다"
    assert len(collect.신규만(전체, [])) == 2, "첫 실행은 전부 새 기사입니다"
    collect.기록저장(전체, [], p)
    assert collect.신규만(전체, collect.이전기록(p)) == [], "이미 알린 기사가 또 새 것으로 나옵니다"
    더 = 전체 + [기사("셋째")]
    새것 = collect.신규만(더, collect.이전기록(p))
    assert [g["title"] for g in 새것] == ["셋째"], f"새 기사만 골라야 합니다: {새것}"
    # 상한을 넘겨도 파일이 무한정 커지지 않는다
    collect.기록저장([기사(f"n{i}") for i in range(collect.STATE_MAX + 500)], [], p)
    assert len(collect.이전기록(p)) == collect.STATE_MAX, "지문 보관 상한이 안 걸립니다"

# --- 화면: 제목이 그대로 들어가고 태그가 새지 않는다 ---
g = 기사("<script>alert(1)</script> 위험한 제목")
g["fp"] = collect.지문(g)
문서 = render.만들기([g], {g["fp"]}, [], 지금)
assert "<script>alert(1)</script> 위험한" not in 문서, "제목의 태그가 그대로 새어 나갑니다"
assert "&lt;script&gt;" in 문서, "이스케이프가 안 됐습니다"
assert 'class="new"' in 문서, "새 기사 뱃지가 없습니다"
assert "새 소식이 없습니다" in 문서, "기사 없는 분야에 안내가 없어야 할 자리에 없습니다"

# --- 검색·색인 ---
목록 = []
for i, (제, 분, 출) in enumerate([("클로드 신기능", "AI·클로드", "네이트"),
                                 ("유니티 6 출시", "게임개발", "네이트"),
                                 ("쇼츠 알고리즘", "유튜브·쇼츠", "TubeFilter")]):
    x = 기사(제, 분, 출)
    x["fp"] = collect.지문(x)
    목록.append(x)
문서 = render.만들기(목록, {목록[0]["fp"]}, [], 지금)
assert 'id="q"' in 문서, "검색창이 없습니다"
assert 문서.count('data-k="') == 3, "기사마다 검색 열쇠가 있어야 합니다"
assert 'data-k="클로드 신기능 네이트 "' in 문서, "검색 열쇠에 제목·출처가 함께 담겨야 합니다"
assert 'data-t="AI·클로드"' in 문서, "분야 필터용 속성이 없습니다"
assert 'data-kind="topic"' in 문서, "분야 칩이 없습니다"
# 출처 색인은 걷어냈다. 출처로 걸러 보고 싶으면 검색창에 치면 된다(열쇠에 담겨 있음).
assert 'data-kind="src"' not in 문서, "출처 칩이 남아 있습니다"
assert "출처 2곳" not in 문서, "출처 색인이 남아 있습니다"
# 검색칸은 헤더 안에 제목과 나란히 있어야 한다
머리 = 문서[문서.index("<header>"):문서.index("</header>")]
assert 'id="q"' in 머리 and "<h1>" in 머리, "검색칸이 헤더 밖에 있습니다"
assert "display:flex" in 문서[문서.index("header{"):문서.index("header{") + 200], \
    "헤더가 한 줄로 배치되지 않았습니다"
# 검색 열쇠는 소문자로 미리 만들어 둔다(대소문자 구분 없이 걸리게)
대문자 = 기사("YouTube Shorts UPDATE", "유튜브·쇼츠", "TubeFilter")
대문자["fp"] = collect.지문(대문자)
assert 'data-k="youtube shorts update tubefilter' in render.만들기(
    [대문자], set(), [], 지금), "검색 열쇠가 소문자로 정규화되지 않았습니다"

# --- 분야 색 카드 ---
from sources import 분야순서  # noqa: E402
색들 = [render.분야색[t] for t in 분야순서]
assert len(set(색들)) == len(색들), f"분야마다 다른 색이어야 합니다: {색들}"
assert set(분야순서) == set(render.분야색), "분야 목록과 색 목록이 어긋납니다"
규칙 = render._색규칙()
for 분야 in 분야순서:
    assert f'li[data-t="{분야}"]' in 규칙, f"{분야} 카드 색 규칙이 없습니다"
    assert f'.chip[data-kind="topic"][data-val="{분야}"]' in 규칙, f"{분야} 칩 색 규칙이 없습니다"
assert f"--tint:{render.기본색}" in 규칙, "색을 못 찾은 분야용 기본값이 없습니다"
문서 = render.만들기(목록, set(), [], 지금)
for 분야 in ("AI·클로드", "게임개발"):
    assert f'<section data-t="{분야}"' in 문서, f"{분야} 구역에 색 표시가 없습니다"
assert "color-mix(in srgb,var(--tint) 6%,transparent)" in 문서, "카드 배경이 아주 옅어야 합니다"
assert "li.empty{background:none" in 문서, "빈 안내에는 카드를 씌우지 않습니다"

# --- 본문 상한: 분야마다 앞의 몇 건만 보이고 나머지는 감춘 채 실려 있다 ---
많음 = []
for i in range(7):
    x = 기사(f"AI뉴스{i}", "AI·클로드")
    x["fp"] = collect.지문(x)
    많음.append(x)
문서 = render.만들기(많음, {많음[0]["fp"], 많음[5]["fp"]}, [], 지금)
assert 문서.count('data-k="') == 7, "감춘 기사도 문서에는 실려 있어야 검색에 걸립니다"
assert 문서.count("<li hidden ") == 7 - render.본문상한, \
    f"첫 화면에는 {render.본문상한}건만 보여야 합니다"
assert 문서.index("AI뉴스2") < 문서.index("<li hidden "), "앞의 것부터 보여야 합니다"
assert f'class="rest" data-val="AI·클로드">나머지 {7 - render.본문상한}건 보기' in 문서, \
    "나머지를 탭에서 보라는 안내가 없습니다"
# 상한 이하인 분야에는 안내를 띄우지 않는다
assert '<button class="rest" data-val="게임개발" hidden>' in 문서, "빈 분야에 안내가 떠 있습니다"

# --- 분야 탭: 신규 건수만. 전체 건수를 넣으면 360px 폰에서 한 줄에 안 들어간다 ---
assert 'data-val="AI·클로드" aria-pressed="false">AI·클로드<span class="nn">+2</span></button>' \
    in 문서, "탭에 신규 건수가 없습니다"
assert 'data-val="게임개발" aria-pressed="false">게임개발</button>' in 문서, \
    "신규가 없는 분야에는 +0 을 붙이지 않습니다"
assert '<button class="chip"' in 문서 and 'class="n"' not in 문서, \
    "탭에 전체 건수가 남아 있으면 한 줄에 안 들어갑니다"
# 전체 건수는 섹션 제목에 남아 있어야 한다
assert ">AI·클로드 <span style='opacity:.65'>7</span>" in 문서, "섹션 제목의 전체 건수가 없습니다"

# --- 축소·펼치기 ---
assert 문서.count("<details open>") == len(분야순서), "분야마다 접을 수 있어야 합니다"
assert 문서.count("<summary><h2>") == len(분야순서), "제목이 접기 손잡이여야 합니다"
assert "localStorage" in 문서, "접은 상태를 기억하지 않으면 새로고침마다 풀립니다"
assert 문서.count("catch(e){}") == 2, "사생활 모드에서 localStorage 예외를 막지 않았습니다"
assert f"const 상한={render.본문상한};" in 문서, "화면 스크립트에 상한이 안 박혔습니다"

# --- 본문 설명 뽑기: 요약할 재료가 있는 것만 남긴다 ---
import xml.etree.ElementTree as ET  # noqa: E402

import summarize  # noqa: E402


def 항목(설명, 제목="테스트 제목입니다"):
    x = ET.fromstring(f"<item><title>{제목}</title><description>{설명}</description></item>")
    return collect._설명(x, 제목)


# 실제 피드는 태그를 &lt; 로 감싸 넣는다(그래서 XML 로는 글자다). 벗겨 낸 뒤 남아야 한다.
assert 항목("&lt;p&gt;정부가 1600조원 규모 투자를 앞당기고 제조 AI 전환을 가속한다.&lt;/p&gt;") \
    == "정부가 1600조원 규모 투자를 앞당기고 제조 AI 전환을 가속한다.", "정상 설명이 안 뽑힙니다"
# 구글뉴스는 제목을 감싼 링크만 넣는다 — 그걸 본문으로 착각하면 제목을 다시 풀어 쓴 요약이 나온다
assert 항목('&lt;a href="https://news.google.com/x"&gt;테스트 제목입니다&lt;/a&gt;') == "", \
    "구글뉴스의 제목 링크를 본문으로 오인했습니다"
# Hacker News 는 주소만 넣는다 — 빼고 나면 남는 게 없다
assert 항목("Article URL: https://a.com/x Comments URL: https://b.com/y") == "", \
    "주소만 있는 설명을 걸러 내지 못했습니다"
assert len(항목("가" * 900)) == collect.DESC_MAX, "설명 길이 상한이 안 걸립니다"

# --- 요약: 키가 없으면 조용히 넘어가고, 캐시가 있으면 부르지 않는다 (망 접속 없음) ---
os.environ.pop("ANTHROPIC_API_KEY", None)
with tempfile.TemporaryDirectory() as work:
    캐시 = os.path.join(work, "summaries.json")
    목록 = [기사("설명 있는 것"), 기사("설명 없는 것")]
    목록[0]["desc"] = "본문이 이만큼 들어 있습니다."
    목록[1]["desc"] = ""
    for x in 목록:
        x["fp"] = collect.지문(x)

    잰것 = summarize.채우기(목록, 캐시)
    assert all(g["summary"] == "" for g in 목록), "키가 없는데 요약이 붙었습니다"
    assert 잰것["새로"] == 0 and 잰것["건너뜀"] == 2, f"키가 없으면 아무것도 안 불러야 합니다: {잰것}"

    # 캐시에 있으면 키가 없어도 붙는다 (매시간 다시 부르지 않게 하는 장치)
    import json as _json
    with open(캐시, "w", encoding="utf-8") as f:
        _json.dump({목록[0]["fp"]: "이미 만들어 둔 요약."}, f, ensure_ascii=False)
    summarize.채우기(목록, 캐시)
    assert 목록[0]["summary"] == "이미 만들어 둔 요약.", "쌓아 둔 요약을 다시 쓰지 않습니다"

    # 이번에 안 본 기사의 요약은 버린다 — 안 그러면 파일이 계속 커진다
    summarize.요약저장({"살릴것": "a", "버릴것": "b"}, {"살릴것"}, 캐시)
    with open(캐시, encoding="utf-8") as f:
        assert _json.load(f) == {"살릴것": "a"}, "오래된 요약이 안 지워집니다"

# 화면은 요약이 있으면 그리고, 없으면 빈 칸을 만들지 않는다
요약본 = 기사("요약 붙은 기사")
요약본["fp"] = collect.지문(요약본)
요약본["summary"] = "핵심을 한 줄로 적은 문장."
문서 = render.만들기([요약본], set(), [], 지금)
assert '<div class="sum">핵심을 한 줄로 적은 문장.</div>' in 문서, "요약이 화면에 안 그려집니다"
민것 = 기사("요약 없는 기사")
민것["fp"] = collect.지문(민것)
assert 'class="sum"' not in render.만들기([민것], set(), [], 지금), \
    "요약이 없는데 빈 칸을 만들었습니다"

# --- 알림: 키가 없으면 아무 일도 하지 않는다 (망 접속 없음) ---
보낸것 = []
원래 = brief.requests.post
brief.requests.post = lambda *a, **k: 보낸것.append(k) or (_ for _ in ()).throw(
    AssertionError("키가 없는데 전송을 시도했습니다"))
for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
    os.environ.pop(k, None)
brief.알림("보내면 안 됨")
assert 보낸것 == [], "키가 없는데 전송했습니다"
brief.requests.post = 원래

# --- 알림문: 건수와 상한이 맞다 ---
새것 = [기사(f"기사{i}") for i in range(20)]
글 = brief.알림문(새것, 100, "https://example.com")
assert "새 소식 20건" in 글 and "전체 100건" in 글, 글
assert 글.count("\n· ") == brief.알림상한, f"본문에 {brief.알림상한}건만 담아야 합니다"
assert f"외 {20 - brief.알림상한}건" in 글, "나머지 건수 안내가 없습니다"

print("통과: 지문3 · 최신만4 · 파싱2 · 신규판정5 · 화면4 · 상한5 · 탭2 · 접기5 · "
      "설명4 · 요약6 · 알림3")
