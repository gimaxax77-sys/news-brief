# 기사에 한국어 한 줄 요약을 붙입니다 (Claude Haiku · 결과는 파일에 쌓아 두고 재사용)
import concurrent.futures as cf
import json
import os

MODEL = "claude-haiku-4-5"
CACHE = "summaries.json"   # {지문: 요약}. 같은 기사를 매시간 다시 요약하지 않으려고 둡니다.
호출상한 = 200             # 한 번 실행에 부를 수 있는 최대 건수. 폭주로 돈이 새는 것을 막습니다.
동시 = 8                   # 한꺼번에 부르는 수. 155건이 순차면 3분, 8줄이면 20초입니다.
MAX_TOKENS = 120
# 1M 토큰당 달러. 실제 청구액을 눈으로 보려고 적어 둡니다(2026-08-04 기준 Haiku 4.5).
단가 = {"in": 1.0, "out": 5.0}

제외표시 = "제외"  # 모델이 이 한 마디만 돌려주면 그 기사는 화면에서 뺍니다.

요약규칙 = (
    "한국어 한 문장으로 핵심만 뽑는다.\n"
    "   - 60자 이내. 한 문장. 마침표로 끝낸다.\n"
    "   - 제목에 이미 있는 말을 되풀이하지 않는다. 제목이 빠뜨린 것을 채운다.\n"
    "   - 본문에 없는 사실을 지어내지 않는다. 재료가 부족하면 있는 것만 짧게 적는다.\n"
    "   - 영어 기사는 한국어로 옮겨 요약한다.\n"
    "   - 요약문만 출력한다. 머리말·따옴표·설명을 붙이지 않는다."
)

# 읽는 김에 분야 판정까지 시킵니다. 어차피 본문을 넣어 부르는 호출이라
# 판정에 드는 값은 출력 두 글자뿐입니다 — 키워드 목록보다 정확하고 거의 공짜입니다.
지시 = (
    "너는 IT 뉴스 브리핑의 편집자다. 기사를 읽고 두 가지를 한다.\n"
    "\n"
    "1) 이 브리핑에 실을 기사인지 고른다.\n"
    "   기준은 **기사가 다루는 대상**뿐이다. IT·소프트웨어·하드웨어·반도체·인공지능·\n"
    "   게임·유튜브 가운데 하나를 다루면 싣는다.\n"
    "   기사의 **형식은 보지 않는다** — 실적·투자·인수·인사·정책·판매량 기사도 그 대상이\n"
    "   위 영역이면 그대로 싣는다.\n"
    f"   대상 자체가 영역 밖일 때만 다른 말 없이 「{제외표시}」 한 마디만 출력하고 끝낸다.\n"
    "\n"
    "   싣는 보기: 새 스마트폰 사전판매 기록 / 반도체 기업 매출 전망 / 정부의 AI 조직 신설 /\n"
    "             게임기 누적 판매량 / 보안 스타트업 투자 유치 / 플랫폼 기업 경영 현안\n"
    "   빼는 보기: 주식 시황과 거래소 공시 / 정당 정치와 선거 / 사건사고와 재해 /\n"
    "             부동산 / 식품·생활용품 / 완구 / 자동차 시승기 / 영화·드라마·스포츠\n"
    "\n"
    "   애매하면 반드시 싣는다. 잘못 빼는 것이 잘못 싣는 것보다 훨씬 나쁘다.\n"
    "\n"
    "2) 실을 기사면 " + 요약규칙
)

# 주제가 이미 고정된 전용 피드입니다. 여기 실린 것은 무조건 우리 분야이므로 판정하지 않습니다.
# ⛔ 넣지 않으면 사고가 납니다 — 제목이 "v2.1.221" 뿐인 Claude Code 릴리스와
#    OpenAI 공식 글이 "분야 밖" 으로 빠졌습니다(2026-08-04 실측).
판정면제 = {"Claude Code 릴리스", "OpenAI", "Google AI", "Godot", "Unity",
            "YouTube 공식", "YouTube Creators", "TubeFilter", "Game Developer"}

지시_요약만 = "너는 IT 뉴스 브리핑의 편집자다. 기사를 읽고 " + 요약규칙


def 버릴까(g: dict) -> bool:
    """모델이 분야가 다르다고 본 기사인지."""
    if g.get("source") in 판정면제:
        return False
    return g.get("summary", "").strip().rstrip(".。") == 제외표시


def 이전요약(path: str = CACHE) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def 요약저장(캐시: dict, 살릴지문: set, path: str = CACHE) -> None:
    """이번에 본 기사 것만 남깁니다. 안 그러면 파일이 계속 커집니다."""
    남길 = {k: v for k, v in 캐시.items() if k in 살릴지문}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(남길, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path)


def _한건(client, g: dict) -> tuple[str, str, int, int]:
    본문 = f"제목: {g['title']}\n매체: {g.get('source', '')}\n본문: {g['desc']}"
    쓸지시 = 지시_요약만 if g.get("source") in 판정면제 else 지시
    m = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=쓸지시,
                               messages=[{"role": "user", "content": 본문}])
    글 = "".join(b.text for b in m.content if b.type == "text").strip()
    return g["fp"], 글, m.usage.input_tokens, m.usage.output_tokens


def 채우기(기사: list[dict], path: str = CACHE) -> dict:
    """`g["summary"]` 를 채웁니다. 요약할 수 없는 상황이면 조용히 넘어갑니다.

    요약은 **덤**입니다. 키가 없든 API 가 죽었든, 화면 생성과 알림은 그대로 돌아야 합니다.
    그래서 이 함수는 예외를 밖으로 내보내지 않습니다.
    """
    잰것 = {"새로": 0, "재사용": 0, "건너뜀": 0, "실패": 0, "in": 0, "out": 0, "비용": 0.0}
    캐시 = 이전요약(path)
    for g in 기사:
        g["summary"] = 캐시.get(g["fp"], "")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        잰것["건너뜀"] = len(기사)
        return 잰것
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"  (요약 준비 실패: {e})")
        잰것["건너뜀"] = len(기사)
        return 잰것

    # 본문 설명이 없는 기사는 부르지 않습니다. 제목만 넣으면 제목을 바꿔 쓴 문장이 나와
    # 정보가 안 늘고 돈만 나갑니다(구글뉴스 기사가 여기 해당합니다).
    할것 = [g for g in 기사 if g.get("desc") and not g["summary"]]
    잰것["재사용"] = sum(1 for g in 기사 if g["summary"])
    잰것["건너뜀"] = len(기사) - len(할것) - 잰것["재사용"]
    if len(할것) > 호출상한:
        print(f"  (요약 {len(할것)}건 중 상한 {호출상한}건만 처리합니다. 나머지는 다음 실행에서)")
        할것 = 할것[:호출상한]

    with cf.ThreadPoolExecutor(max_workers=동시) as pool:
        for fut in cf.as_completed([pool.submit(_한건, client, g) for g in 할것]):
            try:
                fp, 글, i, o = fut.result()
            except Exception as e:
                잰것["실패"] += 1
                if 잰것["실패"] == 1:      # 같은 오류가 100줄 찍히지 않게 첫 건만 남깁니다
                    print(f"  (요약 실패: {e})")
                continue
            캐시[fp] = 글
            잰것["새로"] += 1
            잰것["in"] += i
            잰것["out"] += o

    for g in 기사:
        g["summary"] = 캐시.get(g["fp"], "")
    잰것["비용"] = 잰것["in"] / 1e6 * 단가["in"] + 잰것["out"] / 1e6 * 단가["out"]
    요약저장(캐시, {g["fp"] for g in 기사}, path)
    return 잰것
