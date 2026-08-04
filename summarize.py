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

지시 = (
    "너는 뉴스 한 줄 요약가다. 주어진 기사에서 한국어 한 문장으로 핵심만 뽑는다.\n"
    "규칙:\n"
    "- 60자 이내. 한 문장. 마침표로 끝낸다.\n"
    "- 제목에 이미 있는 말을 되풀이하지 않는다. 제목이 빠뜨린 것을 채운다.\n"
    "- 본문에 없는 사실을 지어내지 않는다. 재료가 부족하면 있는 것만 짧게 적는다.\n"
    "- 영어 기사는 한국어로 옮겨 요약한다.\n"
    "- 요약문만 출력한다. 머리말·따옴표·설명을 붙이지 않는다."
)


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
    m = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=지시,
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
