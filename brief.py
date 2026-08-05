# 수집 → 신규 판정 → 화면 생성 → 텔레그램 알림. 스케줄러가 2시간마다 이 파일을 부릅니다.
import datetime as dt
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

from collect import 기록저장, 모으기, 신규만, 이전기록, 지문  # noqa: E402
from render import 만들기  # noqa: E402
from summarize import 버릴까, 핫기록, 핫뉴스, 채우기 as 요약채우기  # noqa: E402

OUT = os.path.join("docs", "index.html")  # GitHub Pages 가 docs/ 를 그대로 서빙합니다.
KST = dt.timezone(dt.timedelta(hours=9))

# Gim 이 자는 시간(한국시간 01~08시)에는 아무것도 하지 않습니다 — 알림도, 요약 호출도.
# 그동안 쌓인 것은 09시에 한 번에 처리해 「밤새 있었던 일」로 묶어 알립니다.
잠든시간 = range(1, 9)
아침시각 = 9
주간상한 = 5   # 2시간마다 보내는 알림에 담을 기사 수
아침상한 = 8   # 09시 알림은 8시간치라 조금 더 담습니다


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


def 알림문(핫: list[dict], 새것: list[dict], 전체: int, 주소: str | None,
         아침: bool = False) -> str:
    머리 = "밤새 있었던 일" if 아침 else "핫뉴스"
    줄 = [f"[뉴스 브리핑] {머리} {len(핫)}건 · 새 소식 {len(새것)}건 (전체 {전체}건)", ""]
    for g in 핫:
        줄.append(f"■ {g['title'][:70]}")
        속 = g.get("왜") or g.get("summary") or ""
        if 속:
            줄.append(f"   {속[:70]}")
        꼬리 = [g["topic"]]
        if g.get("dup", 1) > 1:
            꼬리.append(f"{g['dup']}개 매체")
        줄.append(f"   ({' · '.join(꼬리)})")
        줄.append("")
    남음 = len(새것) - len(핫)
    if 남음 > 0:
        줄.append(f"나머지 {남음}건은 페이지에서 보실 수 있습니다.")
    if 주소:
        줄 += ["", 주소]
    return "\n".join(줄)


def main() -> int:
    지금 = dt.datetime.now(dt.timezone.utc)
    한국시 = 지금.astimezone(KST)
    # ⛔ 수집보다 먼저 막습니다. 수집한 뒤에 막으면 기사가 「이미 본 것」으로 기록돼
    #    아침 알림에서 통째로 빠집니다. 여기서 나가면 상태 파일을 건드리지 않습니다.
    if 한국시.hour in 잠든시간:
        print(f"[{한국시:%Y-%m-%d %H:%M} KST] 잠든 시간({잠든시간.start}~{잠든시간.stop - 1}시)"
              f"이라 건너뜁니다. {아침시각}시에 한 번에 처리합니다.")
        return 0
    아침 = 한국시.hour == 아침시각

    기사, 실패 = 모으기()
    if not 기사:
        # 전부 실패했으면 화면을 빈 것으로 덮어쓰지 않습니다(있던 화면이 더 낫습니다).
        print(f"[{지금:%Y-%m-%d %H:%M}] 수집 0건. 화면을 건드리지 않습니다. 실패: {실패}")
        알림("[뉴스 브리핑] 수집에 실패했습니다. 소스가 전부 응답하지 않습니다.")
        return 1

    for g in 기사:
        g["fp"] = 지문(g)

    잰것 = 요약채우기(기사)
    # 요약하면서 "분야가 다르다"고 판정한 기사는 여기서 뺍니다. 본문을 읽고 내린 판단이라
    # 제목의 낱말만 보는 제외어보다 정확합니다(제외어는 본문이 없는 기사를 맡습니다).
    # ⚠ 신규 판정보다 **먼저** 빼야 합니다. 뒤로 미루면 뺀 기사가 알림에 그대로 나갑니다.
    버린것 = [g for g in 기사 if 버릴까(g)]
    기사 = [g for g in 기사 if not 버릴까(g)]
    print(f"  요약: 새로 {잰것['새로']}건 · 재사용 {잰것['재사용']}건 · 건너뜀 {잰것['건너뜀']}건"
          + (f" · 실패 {잰것['실패']}건" if 잰것["실패"] else "")
          + (f" · 분야밖 {len(버린것)}건 뺌" if 버린것 else "")
          + (f" · ${잰것['비용']:.4f}" if 잰것["새로"] else ""))

    본것 = 이전기록()
    새것 = 신규만(기사, 본것)

    # 알림에 나갈 핫뉴스를 먼저 고릅니다 — 같은 목록이 화면 맨 위 「핫이슈」 칸이 됩니다.
    # 화면용으로 따로 부르지 않으므로 추가 비용이 없습니다.
    핫 = 핫뉴스(새것, 아침상한 if 아침 else 주간상한) if 새것 else []
    쌓인핫 = 핫기록(핫, 지금)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"  # 쓰다 죽어도 이전 화면이 남도록 임시파일에 쓰고 교체합니다.
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(만들기(기사, {지문(g) for g in 새것}, 실패, 지금, 쌓인핫))
    os.replace(tmp, OUT)

    print(f"[{한국시:%Y-%m-%d %H:%M} KST] 전체 {len(기사)}건 · 새 소식 {len(새것)}건 · "
          f"실패 {len(실패)}개 → {OUT}")
    if 새것:
        print(f"  알림: {'밤새 있었던 일' if 아침 else '핫뉴스'} {len(핫)}건 "
              f"· 화면 핫이슈 칸 {len(쌓인핫)}건")
        알림(알림문(핫, 새것, len(기사), os.environ.get("BRIEF_URL"), 아침))
    기록저장(기사, 본것)
    return 0


if __name__ == "__main__":
    sys.exit(main())
