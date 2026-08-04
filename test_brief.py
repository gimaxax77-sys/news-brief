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

print("통과: 지문3 · 최신만4 · 파싱2 · 신규판정5 · 화면4 · 알림3")
