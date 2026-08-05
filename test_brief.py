# 수집·중복제거·신규판정·화면·알림이 망 없이도 맞게 도는지 확인
import datetime as dt
import os
import tempfile

import re

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
# 탭이 다섯이라 긴 이름은 탭에서만 줄여 쓴다. data-val 은 원래 이름이어야 필터가 걸린다.
assert 'data-val="AI·클로드" aria-pressed="false">AI<span class="nn">+2</span></button>' \
    in 문서, "탭에 신규 건수가 없거나 이름을 안 줄였습니다"
assert 'data-val="게임개발" aria-pressed="false">게임개발</button>' in 문서, \
    "신규가 없는 분야에는 +0 을 붙이지 않습니다"
assert render._탭이름("유튜브·쇼츠") == "유튜브" and render._탭이름("IT이슈") == "IT이슈"
assert set(render.탭줄임) <= set(분야순서), "탭줄임에 없는 분야 이름이 있습니다"
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

# --- 한 사건씩: 같은 보도자료가 매체만 바꿔 도배되는 것을 하나로 줄인다 ---
def 제목만(*제목들, 설명=None):
    return [{"title": t, "url": f"https://a.com/{i}", "at": None,
             "desc": (설명 or {}).get(t, "")} for i, t in enumerate(제목들)]


묶임 = collect.한사건씩(제목만(
    "카카오게임즈, 더그림엔터테인먼트와 웹툰 IP 활용 게임 개발 및 서비스 업무협약",
    "카카오게임즈, ‘김부장’ 더그림엔터와 IP 활용 게임 개발·서비스 MOU",
    "카카오게임즈-더그림엔터 맞손…웹툰 IP 활용 게임 개발 나선다",
    "SK하이닉스, 샌디스크와 HBF 첫 표준규격 공개"))
assert len(묶임) == 2, f"같은 보도자료 3건이 하나로 안 줄었습니다: {[g['title'][:20] for g in 묶임]}"
assert 묶임[1]["title"].startswith("SK하이닉스"), "다른 사건까지 묶였습니다"

# ⛔ Show HN 은 제목 틀이 같지만 안은 전부 다른 프로젝트다 — 묶으면 글이 사라진다
쇼 = collect.한사건씩(제목만(
    "Show HN: cctap – see and reach the Claude Code session that needs you",
    "Show HN: Cckeep – Claude Code's remote session gives up recovery",
    "Show HN: AxiomCore – a Claude plugin that keeps your project in sync"))
assert len(쇼) == 3, "Show HN 글은 서로 다른 프로젝트라 묶으면 안 됩니다"

# 흔한 말만 겹치는 다른 사건은 묶이지 않는다(귀한 낱말을 함께 봐야 하는 이유)
다름 = collect.한사건씩(제목만(
    "오픈AI, 서울서 게임 개발 해커톤 개최",
    "오픈AI, 서울서 게임 개발 세미나 취소"))
assert len(다름) == 2 or 다름[0]["title"].startswith("오픈AI"), "판단이 뒤집혔습니다"

# 대표에 본문이 없고 뒤엣것에 있으면 바꿔 단다 — 요약할 수 있는 쪽이 남아야 한다
바뀜 = collect.한사건씩(제목만(
    "갤럭시 Z8 시리즈 사전판매 144만 대…역대 최고 기록",
    "삼성전자, 갤럭시 Z8 사전예약 144만대... 역대 신기록",
    설명={"삼성전자, 갤럭시 Z8 사전예약 144만대... 역대 신기록": "본문이 여기 있습니다. 이만큼 충분히 깁니다."}))
assert len(바뀜) == 1 and 바뀜[0]["desc"], "본문 있는 쪽을 대표로 세우지 않았습니다"

# --- 제외어: 국내 IT 일간지가 함께 내보내는 증시·정치·사건사고를 버린다 ---
from sources import SOURCES, 제외어  # noqa: E402

assert collect.걸린제외어("카카오페이, 2분기 영업익 528%↑…역대 최대 실적") == "영업익"
assert collect.걸린제외어("SK하이닉스, 샌디스크와 HBF 첫 표준규격 공개") == "", \
    "반도체 기사를 버리면 안 됩니다"
assert collect.걸린제외어("정부 직속 'AI 개발 조직 신설' 초읽기…국무총리훈령 제정") == "", \
    "AI 정책 기사를 버리면 안 됩니다 — '정부'·'실적' 같은 넓은 말을 넣지 마십시오"
assert not (set(제외어) & {"정부", "실적", "투자", "매출", "기업", "산업"}), \
    "IT 기사까지 통째로 지우는 넓은 말이 제외어에 들어갔습니다"
# 거르기를 끄면 그대로 나온다 — 무엇이 빠지는지 눈으로 확인하는 통로입니다
막힘 = [{"title": "李대통령, 기업 투자 걸림돌 제거", "url": "https://a.com/1", "at": None}]
assert collect.걸린제외어(막힘[0]["title"]) == "대통령"

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
assert 항목("Article URL: https://a.com/x Comments URL: https://b.com/y "
          "Points: 120 # Comments: 45") == "", \
    "Hacker News 의 라벨+주소만 있는 설명을 걸러 내지 못했습니다"
# 같은 HN 이라도 글 본문이 실려 있으면 요약할 값어치가 있다
assert 항목("Article URL: https://a.com/x Comments URL: https://b.com/y "
          "I spent three months rewriting our build system and here is what actually "
          "broke along the way.") != "", "본문이 실린 HN 글까지 버렸습니다"
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

# --- 분야 판정: 요약과 같은 호출에서 "분야가 다르다"를 받아 낸다 ---
# 지시문에 판정을 시키는 말이 살아 있어야 한다. 이게 빠지면 조용히 요약만 하고 끝난다.
assert summarize.제외표시 in summarize.지시 and "브리핑에 실을 기사인지" in summarize.지시, \
    "요약 지시문에서 분야 판정이 빠졌습니다"
assert "애매하면 반드시 싣는다" in summarize.지시, "애매할 때 빼 버리면 멀쩡한 기사가 사라집니다"
# ⛔ 판정은 「대상 영역」으로만 한다. 형식(실적·투자·판매량)으로 빼기 시작하면
#    갤럭시 사전판매·정부 AI 조직 신설까지 사라진다 — 실측 정확도가 95%에서 65%로 떨어졌다.
assert "형식은 보지 않는다" in summarize.지시, "기사 형식으로 빼면 멀쩡한 IT 기사가 날아갑니다"
assert "싣는 보기:" in summarize.지시 and "빼는 보기:" in summarize.지시,     "경계에 있는 보기를 빼면 판정이 흔들립니다"
assert summarize.버릴까({"summary": "제외"}), "분야 판정을 못 읽습니다"
assert summarize.버릴까({"summary": " 제외. "}), "앞뒤 공백·마침표가 붙으면 못 읽습니다"
assert not summarize.버릴까({"summary": "제외 대상이 된 반도체 장비의 수출 규제가 풀렸다."}), \
    "요약문이 '제외' 로 시작한다고 기사를 버리면 안 됩니다"
assert not summarize.버릴까({"summary": ""}), "요약이 없는 기사(구글뉴스)를 버리면 안 됩니다"
assert not summarize.버릴까({}), "요약 칸이 아예 없어도 죽지 않아야 합니다"
# 주제가 고정된 전용 피드는 판정 자체를 안 한다. 제목이 "v2.1.221" 뿐인 릴리스 글이
# "분야 밖" 으로 빠진 실제 사고에서 나온 규칙이다.
assert summarize.판정면제 <= {이름 for _, 이름, _ in SOURCES},     "판정면제에 없는 소스 이름이 있습니다 — 소스 이름을 바꾸면 면제가 조용히 풀립니다"
assert not summarize.버릴까({"source": "Claude Code 릴리스", "summary": "제외"}),     "전용 피드까지 분야 판정으로 빼면 안 됩니다"
assert summarize.요약규칙 in summarize.지시 and summarize.요약규칙 in summarize.지시_요약만,     "두 지시문이 같은 요약 규칙을 써야 결과가 어긋나지 않습니다"
assert summarize.제외표시 not in summarize.지시_요약만, "면제용 지시문에 판정이 남아 있습니다"

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

# --- 잠든 시간·핫뉴스 알림 ---
assert list(brief.잠든시간) == [1, 2, 3, 4, 5, 6, 7, 8], "한국시간 01~08시가 잠든 시간입니다"
assert brief.아침시각 == 9 and brief.아침시각 not in brief.잠든시간,     "아침 시각이 잠든 시간 안에 있으면 하루 종일 아무것도 안 돕니다"
assert brief.아침상한 > brief.주간상한, "8시간치 아침 알림이 2시간치보다 적으면 안 됩니다"

# 무리 크기(몇 개 매체가 다뤘나)가 남아야 핫뉴스를 고를 수 있다
묶임 = collect.한사건씩(제목만(
    "카카오게임즈, 더그림엔터테인먼트와 웹툰 IP 활용 게임 개발 및 서비스 업무협약",
    "카카오게임즈, ‘김부장’ 더그림엔터와 IP 활용 게임 개발·서비스 MOU",
    "카카오게임즈-더그림엔터 맞손…웹툰 IP 활용 게임 개발 나선다",
    "SK하이닉스, 샌디스크와 HBF 첫 표준규격 공개"))
assert [g["dup"] for g in 묶임] == [3, 1], f"묶인 매체 수가 안 남았습니다: {묶임}"

# 후보가 상한 이하면 모델을 부르지 않는다(망 접속 없이 도는 이유)
os.environ.pop("ANTHROPIC_API_KEY", None)
후보 = 제목만("가장 많이 다룬 것", "두 번째", "세 번째")
후보[1]["dup"] = 9
후보[0]["dup"] = 2
for x in 후보:
    x.setdefault("dup", 1)
    x["topic"] = "IT이슈"
골라짐 = summarize.핫뉴스(후보, 2)
assert [g["title"] for g in 골라짐] == ["두 번째", "가장 많이 다룬 것"],     f"매체가 많이 다룬 순서가 아닙니다: {[g['title'] for g in 골라짐]}"

# 알림문: 고른 이유와 매체 수가 들어가고, 나머지 건수를 안내한다
글 = brief.알림문(골라짐, 후보, 200, "https://example.com")
assert "핫뉴스 2건" in 글 and "새 소식 3건" in 글 and "전체 200건" in 글, 글
assert "9개 매체" in 글, "몇 개 매체가 다뤘는지 안 보입니다"
assert "나머지 1건" in 글, "못 담은 건수를 안내하지 않습니다"
assert "밤새 있었던 일" in brief.알림문(골라짐, 후보, 200, None, 아침=True),     "아침 알림은 8시간치라는 것이 드러나야 합니다"

# --- 핫이슈 칸: 맨 위에 오고, 첫 탭이고, 원래 분야에도 그대로 남는다 ---
핫들 = []
for i in range(3):
    x = 기사(f"핫뉴스{i}", "AI·클로드")
    x["fp"] = collect.지문(x)
    핫들.append(x)
보통 = 기사("보통 기사", "게임개발")
보통["fp"] = collect.지문(보통)
쌓인핫 = {핫들[0]["fp"]: {"왜": "판이 바뀌는 소식", "at": "2026-08-05T03:00:00+00:00"},
        핫들[1]["fp"]: {"왜": "", "at": "2026-08-05T01:00:00+00:00"}}
문서 = render.만들기(핫들 + [보통], set(), [], 지금, 쌓인핫)

# ⚠ 문서 전체에서 찾으면 안 된다 — 같은 문자열이 위쪽 CSS(색 규칙)에도 있어 순서가 뒤집힌다
칩 = '<button class="chip" data-kind="topic" data-val='
assert 문서.index('<section data-t="핫이슈"') < 문서.index('<section data-t="AI·클로드"'), \
    "핫이슈 칸이 맨 위에 있어야 진입하자마자 보입니다"
assert 문서.index(칩 + '"핫이슈"') < 문서.index(칩 + '"AI·클로드"'), "핫이슈가 첫 탭이어야 합니다"
assert '<div class="sum">판이 바뀌는 소식</div>' in 문서,     "핫이슈 카드에는 「왜 중요한지」가 요약 대신 들어갑니다"
# 최근에 뽑힌 것이 위로 온다
assert 문서.index("핫뉴스0") < 문서.index("핫뉴스1"), "핫이슈는 최근에 뽑힌 순서여야 합니다"
# 원래 분야 칸에서 빼면 분야 탭을 눌렀을 때 큰 뉴스가 사라진다
assert 문서.count("핫뉴스0") >= 2, "핫이슈 기사가 원래 분야 칸에서 빠졌습니다"
assert 문서.count('<section data-t=') == len(분야순서) + 1, "핫이슈 칸이 하나 더 있어야 합니다"
# 핫이슈가 없으면 칸도 탭도 안 만든다
빈것 = render.만들기(핫들, set(), [], 지금, {})
assert '<section data-t="핫이슈"' not in 빈것 and 칩 + '"핫이슈"' not in 빈것, \
    "핫이슈가 없는데 빈 칸을 만들었습니다"
# 색이 네 분야 어느 것과도 겹치지 않아야 구분이 된다
assert render.핫색 not in render.분야색.values(), "핫이슈 색이 분야 색과 겹칩니다"
assert f'.chip[data-val="핫이슈"]' in render._색규칙(), "핫이슈 탭이 눌리기 전에도 눈에 띄어야 합니다"

# 쌓기: 오래된 핫이슈는 버린다
import datetime as _dt  # noqa: E402
with tempfile.TemporaryDirectory() as work:
    hp = os.path.join(work, "hot.json")
    이른때 = 지금 - _dt.timedelta(hours=summarize.핫유지 + 1)
    summarize.핫기록([{**핫들[2], "왜": "옛것"}], 이른때, hp)
    남은 = summarize.핫기록([{**핫들[0], "왜": "새것"}], 지금, hp)
    assert 핫들[0]["fp"] in 남은 and 핫들[2]["fp"] not in 남은,         f"{summarize.핫유지}시간 지난 핫이슈가 안 빠졌습니다: {남은}"
    assert 남은[핫들[0]["fp"]]["왜"] == "새것"

# --- 뒤로가기 플로팅 단추: 분야를 고르면 뜨고, 첫 화면에서는 숨는다 ---
문서 = render.만들기(목록, set(), [], 지금)
assert '<button id="back" hidden' in 문서, "첫 화면에서는 단추가 숨어 있어야 합니다"
assert 'aria-label="전체 목록으로 돌아가기"' in 문서, "읽어 주는 이름이 없습니다"
assert "back.hidden=제한" in 문서, "조건이 있을 때만 뜨게 하는 코드가 없습니다"
assert "const 전체로=" in 문서 and "back.onclick=전체로" in 문서, "누를 때 할 일이 안 붙었습니다"
# 분야와 검색어를 **함께** 풀어야 한다. 하나만 풀면 화면이 그대로 걸러진 채 남는다
전체로 = 문서[문서.index("const 전체로="):문서.index("back.onclick")]
assert "분야=null" in 전체로 and "q.value=''" in 전체로, "분야와 검색어를 함께 풀지 않습니다"
assert "aria-pressed','false'" in 전체로, "탭 눌림 표시를 안 풀면 탭이 켜진 채 남습니다"
assert "scrollTo" in 전체로, "맨 위로 올려 주지 않으면 돌아온 티가 안 납니다"
# 오른쪽 아래 고정 + 아이폰 홈바 회피
규칙 = 문서[문서.index("#back{"):문서.index("#back{") + 220]
assert "position:fixed" in 규칙 and "right:14px" in 규칙, "오른쪽 아래에 고정되지 않았습니다"
assert "env(safe-area-inset-bottom)" in 규칙, "아이폰 홈바에 가릴 수 있습니다"

# --- 영문 제목 한글 번역: 한글이 한 줄도 없는 카드에만 붙인다 ---
assert summarize.옮길것({"title": "Anthropic Inks $10 Billion Deal", "summary": ""}),     "영문 제목인데 요약도 없으면 옮겨야 합니다"
assert not summarize.옮길것({"title": "Anthropic Inks $10 Billion Deal",
                          "summary": "앤스로픽이 100억 달러 계약을 맺었다."}),     "요약이 있으면 이미 한글 한 줄이 있습니다 — 같은 말이 두 줄이 됩니다"
assert not summarize.옮길것({"title": "갤럭시 Z8 사전판매 144만대", "summary": ""}),     "한글 제목을 다시 옮기면 안 됩니다"
assert not summarize.옮길것({"title": "Claude Code v2.1.221 릴리스", "summary": ""}),     "한글이 섞여 있으면 이미 읽힙니다"

# 키가 없으면 조용히 넘어가고, 캐시에 있으면 부르지 않는다 (망 접속 없음)
os.environ.pop("ANTHROPIC_API_KEY", None)
with tempfile.TemporaryDirectory() as work:
    tp = os.path.join(work, "titles.json")
    영문 = 기사("Anthropic Inks $10 Billion Deal")
    영문["fp"] = collect.지문(영문)
    영문["summary"] = ""
    잰것 = summarize.제목옮기기([영문], tp)
    assert 영문["ko"] == "" and 잰것["새로"] == 0, "키가 없는데 번역을 시도했습니다"
    import json as _j
    with open(tp, "w", encoding="utf-8") as f:
        _j.dump({영문["fp"]: "앤스로픽, 100억 달러 계약"}, f, ensure_ascii=False)
    summarize.제목옮기기([영문], tp)
    assert 영문["ko"] == "앤스로픽, 100억 달러 계약", "쌓아 둔 번역을 다시 쓰지 않습니다"

    # ⛔ 모델은 입력 번호 형식을 따라 한다 — "1|글" 만 받으면 묶음이 통째로 버려진다
    묶음줄 = re.compile(r"\s*(\d+)\s*[|.):\-]\s*(.+)$")
    for 꼴 in ("3|앤스로픽, 100억 달러 계약", "3. 앤스로픽, 100억 달러 계약",
             "3) 앤스로픽, 100억 달러 계약", " 3 - 앤스로픽, 100억 달러 계약"):
        m = 묶음줄.match(꼴)
        assert m and m.group(1) == "3" and m.group(2).startswith("앤스로픽"), f"못 읽음: {꼴}"
    import inspect
    assert 묶음줄.pattern in inspect.getsource(summarize.제목옮기기),         "번호 형식을 넓게 받는 정규식이 코드에 없습니다"

    # 화면: 제목 바로 밑, 출처 줄보다 앞에 온다
    문서 = render.만들기([영문], set(), [], 지금)
    assert '<div class="ko">앤스로픽, 100억 달러 계약</div>' in 문서, "번역이 화면에 안 나옵니다"
    assert 문서.index('class="ko"') < 문서.index('class="sub"'),         "번역은 출처 줄보다 먼저 나와야 제목의 일부로 읽힙니다"
    assert ".ko{" in 문서, "번역 줄 서식이 없습니다"
    # 번역이 없으면 빈 칸을 만들지 않는다
    민것2 = 기사("한글 제목 기사")
    민것2["fp"] = collect.지문(민것2)
    assert 'class="ko"' not in render.만들기([민것2], set(), [], 지금),         "번역이 없는데 빈 줄을 만들었습니다"

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

print("통과: 지문3 · 최신만4 · 파싱2 · 신규판정5 · 화면4 · 상한5 · 탭2 · 접기5 · "
      "묶기5 · 제외5 · 설명5 · 요약6 · 판정10 · 야간8 · 핫이슈11 · 뒤로9 · 번역15 · 알림1")
