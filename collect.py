# RSS 소스를 훑어 기사 목록을 만들고, 이미 본 것은 걸러 냅니다
import concurrent.futures as cf
import datetime as dt
import email.utils
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET

import requests

from sources import SOURCES

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
        out.append({"title": 제목, "url": 주소,
                    "at": _시각(_텍스트(it, "pubDate", "published", "updated"))})
    return out


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
        for g in 기사들:
            g["source"] = 이름
            g["topic"] = 분야
        return 분야, 이름, 기사들, ""
    except Exception as e:
        # 소스 하나가 죽어도 나머지는 계속 모읍니다.
        return 분야, 이름, [], f"{type(e).__name__}"


def 모으기(sources=None) -> tuple[list[dict], list[str]]:
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
        본것.add(f)
        결과.append(g)
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
