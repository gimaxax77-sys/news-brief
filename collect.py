# RSS 소스를 훑어 기사 목록을 만들고, 이미 본 것은 걸러 냅니다
import collections
import concurrent.futures as cf
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET

import requests

from sources import SOURCES, 제외어

STATE = "state.json"  # 이미 알린 기사 지문. 매 실행마다 갱신됩니다.
STATE_MAX = 4000      # 지문 보관 개수. 넘으면 오래된 것부터 버립니다.
TIMEOUT = 15
# 소스 하나가 전체를 뒤덮지 않게 막습니다. OpenAI 피드는 아카이브 1107건을 통째로
# 내주어, 상한이 없으면 한 소스가 수집분의 60%를 차지했습니다(2026-08-04 실측).
PER_SOURCE_MAX = 25
MAX_AGE_DAYS = 3  # 이보다 오래된 기사는 버립니다. 날짜가 없는 기사는 남깁니다.
ATOM = "{http://www.w3.org/2005/Atom}"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
       "Accept": "application/rss+xml,application/xml,text/xml,*/*"}


def _텍스트(el, *이름들) -> str:
    """RSS 와 Atom 이 태그 이름을 달리 쓰므로 둘 다 훑습니다."""
    for 이름 in 이름들:
        for t in (이름, ATOM + 이름):
            자식 = el.find(t)
            if 자식 is not None:
                if 자식.text and 자식.text.strip():
                    return 자식.text.strip()
                # Atom 의 link 는 값이 href 속성에 있습니다.
                if 자식.get("href"):
                    return 자식.get("href")
    return ""


def _시각(s: str) -> dt.datetime | None:
    """RFC822(RSS)와 ISO8601(Atom) 두 형식을 모두 받습니다."""
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


DESC_MAX = 400  # 요약에 넣을 본문 설명 길이. 길수록 비싸지고, 400자면 첫 문단이 다 들어옵니다.


def _설명(it, 제목: str) -> str:
    """기사 본문 설명을 뽑습니다. 요약할 재료가 없으면 빈 문자열입니다.

    ⛔ 구글뉴스 RSS 는 이 칸에 **제목을 감싼 링크 태그만** 넣습니다(2026-08-04 실측).
    태그를 벗기면 제목과 매체명이 그대로 나오는데, 그걸 본문으로 착각해 요약에 넣으면
    제목을 다시 풀어 쓴 문장이 나오고 돈만 나갑니다. 그래서 제목으로 시작하면 버립니다.
    """
    원본 = _텍스트(it, "description", "summary", f"{ATOM}summary", f"{ATOM}content", "content")
    글 = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", 원본))).strip()
    벗김 = lambda s: re.sub(r"\W", "", s)[:25]  # noqa: E731  공백·부호를 빼고 앞머리만 견줍니다
    if not 글 or 벗김(글) == 벗김(제목):
        return ""
    # Hacker News 는 본문 대신 "Article URL: … Comments URL: … Points: 12 # Comments: 3" 만 넣습니다.
    # 주소만 지우면 라벨이 50자쯤 남아 길이 검사를 통과합니다 — 라벨까지 지우고 재야 합니다.
    # (2026-08-04: 이 구멍으로 HN 36건이 쓸모없이 요약돼 실행마다 요약분의 24%를 먹었습니다.)
    남은 = re.sub(r"(Article|Comments)\s+URL:|Points:\s*\d+|#\s*Comments:\s*\d+", "", 글)
    남은 = re.sub(r"https?://\S+", "", 남은).strip()
    # ⚠ 주소가 든 것만 길이로 잽니다. 한국어는 촘촘해서 40자면 온전한 한 문장이라,
    #   길이만으로 자르면 멀쩡한 설명이 통째로 날아갑니다(실제로 한 번 날렸습니다).
    if "http" in 글 and len(남은) < 40:
        return ""
    return 글[:DESC_MAX]


def 파싱(body: bytes) -> list[dict]:
    """피드 본문에서 (제목·주소·시각)을 뽑습니다.

    일부 피드는 XML 문서 뒤에 잡음이 붙어 그대로 파싱하면 터집니다
    (`junk after document element`, 2026-08-04 Unreal 피드에서 확인).
    마지막 닫는 태그까지 잘라 내고 파싱합니다.
    """
    for 끝 in (b"</rss>", b"</feed>"):
        i = body.rfind(끝)
        if i != -1:
            body = body[: i + len(끝)]
            break
    root = ET.fromstring(body)
    항목들 = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    out = []
    for it in 항목들:
        제목 = re.sub(r"\s+", " ", _텍스트(it, "title")).strip()
        주소 = _텍스트(it, "link", "id", "guid")
        if not 제목 or not 주소.startswith("http"):
            continue
        out.append({"title": 제목, "url": 주소, "desc": _설명(it, 제목),
                    "at": _시각(_텍스트(it, "pubDate", "published", "updated"))})
    return out


def 매체분리(제목: str) -> tuple[str, str]:
    """구글뉴스 제목 `기사 제목 - 매체명` 을 (제목, 매체명) 으로 나눕니다.

    떼어 내지 않으면 같은 기사가 매체 수만큼 중복으로 올라옵니다(2026-08-04 실측:
    로이터·재팬타임스가 같은 백악관 회동 기사를 각각 실어 화면에 두 번 나왔음).
    덤으로 출처가 "구글뉴스(한)" 대신 실제 매체명("네이트")이 됩니다.
    """
    if " - " not in 제목:
        return 제목, ""
    앞, _, 뒤 = 제목.rpartition(" - ")
    # 뒤쪽이 지나치게 길면 매체명이 아니라 제목의 일부로 봅니다.
    if not 앞 or len(뒤) > 30:
        return 제목, ""
    return 앞.strip(), 뒤.strip()


def 지문(기사: dict) -> str:
    """같은 기사를 다른 소스에서 또 받아도 한 번만 세도록 하는 열쇠.

    주소는 매체마다 추적 파라미터가 붙어 달라지므로 제목을 씁니다.
    """
    t = re.sub(r"[^0-9a-z가-힣]+", "", 기사["title"].lower())
    return hashlib.sha1(t.encode()).hexdigest()[:16]


def 최신만(기사: list[dict], 상한: int = PER_SOURCE_MAX,
          일수: int = MAX_AGE_DAYS) -> list[dict]:
    """한 소스에서 최근 것만 상한만큼 남깁니다.

    날짜가 없는 기사는 버리지 않습니다 — 검색 기반 피드에는 날짜가 빠진 항목이 섞이는데,
    그건 오래됐다는 뜻이 아닙니다. 대신 정렬에서 뒤로 밀려 상한에 먼저 걸립니다.
    """
    기준 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=일수)
    산것 = [g for g in 기사 if g["at"] is None or g["at"] >= 기준]
    산것.sort(key=lambda g: (g["at"] is not None, g["at"] or dt.datetime.min.replace(
        tzinfo=dt.timezone.utc)), reverse=True)
    return 산것[:상한]


def 한소스(항목) -> tuple[str, str, list[dict], str]:
    분야, 이름, url = 항목
    try:
        r = requests.get(url, headers=HDR, timeout=TIMEOUT)
        if r.status_code != 200:
            return 분야, 이름, [], f"HTTP {r.status_code}"
        기사들 = 최신만(파싱(r.content))
        구글 = "news.google.com" in url
        for g in 기사들:
            매체 = ""
            if 구글:  # 구글뉴스만 `제목 - 매체명` 형태입니다.
                g["title"], 매체 = 매체분리(g["title"])
            g["source"] = 매체 or 이름
            g["topic"] = 분야
        return 분야, 이름, 기사들, ""
    except Exception as e:
        # 소스 하나가 죽어도 나머지는 계속 모읍니다.
        return 분야, 이름, [], f"{type(e).__name__}"


CLUSTER_MIN = 0.30   # 제목 두 글자 조각이 이만큼 겹치면 같은 사건으로 봅니다.
_버릴말 = re.compile(r"\[[^\]]*\]|\([^)]*\)|[\"'“”‘’·…\-—,.!?~/|]|&#?\w+;")
# ⛔ 이 틀로 시작하는 글은 묶지 않습니다. Show/Ask HN 은 제목 생김새가 똑같지만
#    안은 전부 **다른 프로젝트**입니다(cctap·Cckeep·AxiomCore 가 하나로 뭉쳤습니다).
_묶지않음 = re.compile(r"^\s*(show|ask|tell)\s+hn[:\s]", re.I)


def _조각(제목: str) -> set:
    """제목을 두 글자 조각으로 쪼갭니다. 한국어는 어순·조사가 흔들려 낱말보다 이게 낫습니다."""
    s = re.sub(r"\s+", "", _버릴말.sub(" ", 제목)).lower()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _낱말(제목: str) -> set:
    return {w.lower() for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", _버릴말.sub(" ", 제목))}


def 한사건씩(기사: list[dict], 문턱: float = CLUSTER_MIN) -> list[dict]:
    """같은 보도자료가 매체만 바꿔 여러 번 실린 것을 하나로 줄입니다.

    2026-08-04 실측: 한 사건이 최대 11번까지 실렸습니다(갤럭시 Z8 사전판매,
    카카오게임즈 MOU, 오픈AI 해커톤). 제목이 조금씩 달라 지문 대조로는 안 잡힙니다.

    닮은 것만으로는 부족합니다 — 제목 틀이 같은 다른 사건이 뭉칩니다. 그래서
    **드물게 나오는 낱말을 하나 이상 공유**할 때만 묶습니다(고유명사·숫자가 여기 걸립니다).
    """
    조각들 = [_조각(g["title"]) for g in 기사]
    낱말들 = [_낱말(g["title"]) for g in 기사]
    셈 = collections.Counter(w for s in 낱말들 for w in s)
    흔함 = max(3, len(기사) // 20)          # 전체의 5% 넘게 나오면 흔한 말입니다
    귀함 = [{w for w in s if 셈[w] <= 흔함} for s in 낱말들]

    남길, 대표 = [], []
    for i, g in enumerate(기사):
        짝 = None
        if not _묶지않음.match(g["title"]):
            짝 = next((j for j in 대표
                       if 조각들[i] & 조각들[j] and 귀함[i] & 귀함[j]
                       and len(조각들[i] & 조각들[j]) / len(조각들[i] | 조각들[j]) >= 문턱), None)
        if 짝 is None:
            대표.append(i)
            g["dup"] = 1
            남길.append(g)
            continue
        자리 = 대표.index(짝)
        묶인수 = 남길[자리]["dup"] + 1
        if not 남길[자리].get("desc") and g.get("desc"):
            # 대표에 본문이 없고 뒤엣것에 있으면 바꿔 답니다 — 요약할 수 있는 쪽이 낫습니다.
            남길[자리] = g
        # 몇 매체가 다뤘는지는 그대로 화제성 지표입니다. 핫뉴스를 고를 때 씁니다.
        남길[자리]["dup"] = 묶인수
    return 남길


def 걸린제외어(제목: str) -> str:
    """제목에 든 제외어를 돌려줍니다. 없으면 빈 문자열입니다."""
    return next((w for w in 제외어 if w in 제목), "")


def 버릴것(sources=None) -> list[dict]:
    """제외어에 걸려 빠지는 기사를 봅니다. 제외어를 늘리기 전에 이걸로 확인하십시오."""
    기사, _ = 모으기(sources, 거르기=False)
    return [g for g in 기사 if 걸린제외어(g["title"])]


def 모으기(sources=None, 거르기: bool = True) -> tuple[list[dict], list[str]]:
    """모든 소스를 동시에 훑어 (기사 목록, 실패한 소스 이름) 을 돌려줍니다."""
    sources = SOURCES if sources is None else sources
    기사, 실패 = [], []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for 분야, 이름, 목록, 에러 in ex.map(한소스, sources):
            if 에러:
                실패.append(f"{이름}({에러})")
            기사 += 목록
    # 이번 수집 안에서의 중복부터 제거합니다(같은 기사를 여러 소스가 물어 옵니다).
    본것, 결과 = set(), []
    for g in sorted(기사, key=lambda x: x["at"] or dt.datetime.min.replace(
            tzinfo=dt.timezone.utc), reverse=True):
        f = 지문(g)
        if f in 본것:
            continue
        if 거르기 and 걸린제외어(g["title"]):
            continue
        본것.add(f)
        결과.append(g)
    if 거르기:
        결과 = 한사건씩(결과)
    return 결과, 실패


def 이전기록(path: str = STATE) -> list[str]:
    if not os.path.exists(path):
        return []
    try:
        return json.load(open(path, encoding="utf-8")).get("seen", [])
    except (ValueError, OSError):
        return []  # 기록이 깨졌으면 전부 새 기사로 봅니다(중복 알림 1회, 유실 0)


def 신규만(기사: list[dict], 본것: list[str]) -> list[dict]:
    본것 = set(본것)
    return [g for g in 기사 if 지문(g) not in 본것]


def 기록저장(기사: list[dict], 본것: list[str], path: str = STATE) -> None:
    """새 지문을 앞에 쌓고 STATE_MAX 개까지만 남깁니다."""
    합친것 = [지문(g) for g in 기사] + list(본것)
    남길것, 중복 = [], set()
    for f in 합친것:
        if f not in 중복:
            중복.add(f)
            남길것.append(f)
    tmp = path + ".tmp"  # 쓰다 죽어도 원본이 남도록 임시파일에 쓰고 교체합니다.
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"seen": 남길것[:STATE_MAX]}, f)
    os.replace(tmp, path)
