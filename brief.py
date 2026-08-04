# 수집 → 신규 판정 → 화면 생성 → 텔레그램 알림. 스케줄러가 1시간마다 이 파일을 부릅니다.
import datetime as dt
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

from collect import 기록저장, 모으기, 신규만, 이전기록, 지문  # noqa: E402
from render import 만들기  # noqa: E402

OUT = os.path.join("docs", "index.html")  # GitHub Pages 가 docs/ 를 그대로 서빙합니다.
알림상한 = 8  # 텔레그램 한 통에 담을 기사 수. 나머지는 건수만 알립니다.


def 알림(text: str) -> None:
    """텔레그램으로 한 통 보냅니다. 키가 없으면 아무 일도 하지 않습니다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15,
                          data={"chat_id": chat, "text": text,
                                "disable_web_page_preview": "true"})
        if not r.json().get("ok"):
            # 제목에 < > 가 있으면 거부당합니다. 원인을 눈에 보이게 남깁니다.
            print(f"  (알림 거부: {r.json().get('description')})")
    except Exception as e:
        # 알림이 실패해도 수집·화면 생성은 이미 끝나 있어야 합니다.
        print(f"  (알림 전송 실패: {e})")


def 알림문(새것: list[dict], 전체: int, 주소: str | None) -> str:
    줄 = [f"[뉴스 브리핑] 새 소식 {len(새것)}건 (전체 {전체}건)", ""]
    분야별 = {}
    for g in 새것:
        분야별.setdefault(g["topic"], []).append(g)
    for 분야, 목록 in 분야별.items():
        줄.append(f"■ {분야} {len(목록)}건")
    줄.append("")
    for g in 새것[:알림상한]:
        줄.append(f"· {g['title'][:60]}")
    if len(새것) > 알림상한:
        줄.append(f"… 외 {len(새것) - 알림상한}건")
    if 주소:
        줄 += ["", 주소]
    return "\n".join(줄)


def main() -> int:
    지금 = dt.datetime.now(dt.timezone.utc)
    기사, 실패 = 모으기()
    if not 기사:
        # 전부 실패했으면 화면을 빈 것으로 덮어쓰지 않습니다(있던 화면이 더 낫습니다).
        print(f"[{지금:%Y-%m-%d %H:%M}] 수집 0건. 화면을 건드리지 않습니다. 실패: {실패}")
        알림("[뉴스 브리핑] 수집에 실패했습니다. 소스가 전부 응답하지 않습니다.")
        return 1

    본것 = 이전기록()
    새것 = 신규만(기사, 본것)
    for g in 기사:
        g["fp"] = 지문(g)
        g.setdefault("summary", "")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"  # 쓰다 죽어도 이전 화면이 남도록 임시파일에 쓰고 교체합니다.
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(만들기(기사, {지문(g) for g in 새것}, 실패, 지금))
    os.replace(tmp, OUT)

    print(f"[{지금:%Y-%m-%d %H:%M}] 전체 {len(기사)}건 · 새 소식 {len(새것)}건 · "
          f"실패 {len(실패)}개 → {OUT}")
    if 새것:
        알림(알림문(새것, len(기사), os.environ.get("BRIEF_URL")))
    기록저장(기사, 본것)
    return 0


if __name__ == "__main__":
    sys.exit(main())
