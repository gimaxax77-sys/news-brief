# 기사에 한국어 한 줄 요약을 붙입니다 (Claude Haiku · 결과는 파일에 쌓아 두고 재사용)
import concurrent.futures as cf
import datetime as dt
import json
import os
import re

MODEL = "claude-haiku-4-5"
CACHE = "summaries.json"   # {지문: 요약}. 같은 기사를 매시간 다시 요약하지 않으려고 둡니다.
호출상한 = 200             # 한 번 실행에 부를 수 있는 최대 건수. 폭주로 돈이 새는 것을 막습니다.
동시 = 8                   # 한꺼번에 부르는 수. 155건이 순차면 3분, 8줄이면 20초입니다.
MAX_TOKENS = 120
# 1M 토큰당 달러. 실제 청구액을 눈으로 보려고 적어 둡니다(2026-08-04 기준 Haiku 4.5).
단가 = {"in": 1.0, "out": 5.0}

제외표시 = "제외"  # 모델이 이 한 마디만 돌려주면 그 기사는 화면에서 뺍니다.

# ⛔ 길이 규칙을 아래 요약 지시문에 세게 넣으면 **판정까지 조여집니다.**
#    2026-08-08 실측(같은 기사 30건) — 「50자를 넘기지 않는다」를 넣자 분야 밖 판정이
#    8건 → 15건으로 늘었고, 그중 5건은 우리 분야인데 잘못 뺀 것이었습니다
#    (Claude 플러그인·AI 챗봇 기사 등). 방화벽 문구를 넣어도 3건이 샜습니다.
#    그래서 **판정 호출은 그대로 두고, 길어진 것만 따로 한 번 더 불러 줄입니다.**
#    실측 효과 — 평균 51.3→46.8자 · 최대 73→58자 · 60자 초과 5건→0건 · 과잉 배제 0건.
줄임한계 = 60      # 요약이 이보다 길면 한 번 더 불러 줄입니다
줄임지시 = (
    "받은 한국어 문장을 **50자 이내 한 문장**으로 줄인다.\n"
    "- 배경 설명·수식어·부연을 지운다. 수치와 고유명사는 반드시 남긴다.\n"
    "- 새 사실을 보태지 않는다. 있는 말만 줄인다.\n"
    "- 줄인 문장만 출력한다. 다른 말을 붙이지 않는다."
)

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
    "   AI 활용 팁·코딩 도구 가운데 하나를 다루면 싣는다.\n"
    "   기사의 **형식은 보지 않는다** — 실적·투자·인수·인사·정책·판매량 기사도 그 대상이\n"
    "   위 영역이면 그대로 싣는다.\n"
    f"   대상 자체가 영역 밖일 때만 다른 말 없이 「{제외표시}」 한 마디만 출력하고 끝낸다.\n"
    "\n"
    "   싣는 보기: 새 스마트폰 사전판매 기록 / 반도체 기업 매출 전망 / 정부의 AI 조직 신설 /\n"
    "             AI 코딩 도구 사용 팁 / 보안 스타트업 투자 유치 / 플랫폼 기업 경영 현안\n"
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
판정면제 = {"Claude Code 릴리스", "OpenAI", "Google AI", "The Decoder",
            "Simon Willison", "Latent Space"}

지시_요약만 = "너는 IT 뉴스 브리핑의 편집자다. 기사를 읽고 " + 요약규칙


def 버릴까(g: dict) -> bool:
    """모델이 분야가 다르다고 본 기사인지."""
    if g.get("source") in 판정면제:
        return False
    return g.get("summary", "").strip().rstrip(".。") == 제외표시


후보배수 = 3   # 알릴 건수의 몇 배를 후보로 올릴지. 넓게 주고 모델이 고르게 합니다.
후보상한 = 18  # 그래도 이보다 많이는 안 넣습니다. 입력이 커지면 값이 올라갑니다.

핫지시 = (
    "너는 IT 뉴스 브리핑의 편집장이다. 아래 후보 가운데 **못 보면 아쉬울 것**만 고른다.\n"
    "\n"
    "⛔ 요청한 수를 채우려 하지 마라. 기준에 맞는 것이 2건이면 2건만, 없으면 하나도 고르지 않는다.\n"
    "\n"
    "고르는 기준 — 다음 중 하나에 **분명히** 해당해야 고른다.\n"
    "- 판이 바뀌는 소식: 새 기술 공개, 실제 출시, 정책 확정, 대형 인수, 중대한 보안 사고.\n"
    "- 규모 자체가 뉴스인 것: 조 단위 투자, 기록적인 판매량.\n"
    "\n"
    "⛔ 다룬 매체가 아무리 많아도 고르지 않는 것\n"
    "- 기업 보도자료 — 업무협약(MOU)·행사 개최·수상·후원·전시 참가·지원사업 선정.\n"
    "- 인사·조직 개편, 지역 협력, 사내 행사.\n"
    "- 아직 일어나지 않은 것 — 예고·전망·기대·루머·「검토 중」.\n"
    "- 의견·칼럼·리뷰·할인 정보.\n"
    "- 같은 사건이 여럿이면 가장 구체적인 하나만.\n"
    "\n"
    "출력 형식 — 고른 것마다 한 줄씩, 다른 말은 붙이지 않는다.\n"
    "번호|왜 지금 중요한지 25자 이내\n"
    "보기)\n"
    "3|국내 폴더블 사전판매 최다 기록\n"
    "7|정부가 AI 전담 조직을 처음 만든다"
)


def 핫뉴스(기사: list[dict], 몇건: int) -> list[dict]:
    """알릴 기사를 골라 돌려줍니다. 고른 이유는 `g["왜"]` 에 담깁니다.

    ① 다룬 매체 수(`dup`)로 후보를 좁히고 ② 모델이 그중에서 고릅니다.
    ①만 쓰면 **보도자료 도배가 1위를 차지합니다**(2026-08-04: 카카오게임즈 MOU 12건).
    """
    후보 = sorted(기사, key=lambda g: (-g.get("dup", 1), g["title"]))[
        :min(후보상한, 몇건 * 후보배수)]
    if len(후보) <= 몇건 or not os.environ.get("ANTHROPIC_API_KEY"):
        return 후보[:몇건]

    줄 = [f"{i+1}. [{g.get('dup', 1)}개 매체] {g['title']}"
          + (f" — {g['summary']}" if g.get("summary") else "")
          for i, g in enumerate(후보)]
    try:
        import anthropic
        m = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=400, system=핫지시,
            messages=[{"role": "user",
                       "content": f"후보 {len(후보)}건 중 최대 {몇건}건을 골라라.\n\n"
                                  + "\n".join(줄)}])
        답 = "".join(b.text for b in m.content if b.type == "text")
        # 이 호출은 로그에 값이 안 찍혀 **월 비용 집계에서 통째로 빠져 있었습니다**(2026-08-08).
        비용 = (m.usage.input_tokens / 1e6 * 단가["in"]
              + m.usage.output_tokens / 1e6 * 단가["out"])
    except Exception as e:
        print(f"  (핫뉴스 선별 실패, 보도 수 순으로 대신합니다: {e})")
        return 후보[:몇건]

    고른것 = []
    for 줄하나 in 답.splitlines():
        번호, _, 왜 = 줄하나.partition("|")
        숫자 = re.match(r"\s*(\d+)", 번호)
        if not 숫자:
            continue
        i = int(숫자.group(1)) - 1
        if 0 <= i < len(후보) and 후보[i] not in 고른것:
            후보[i]["왜"] = 왜.strip()
            고른것.append(후보[i])
    # ⛔ 0건을 순위대로 채우면 안 됩니다 — 지시문이 「없으면 하나도 고르지 않는다」를
    #    허용하므로 0건은 정상입니다. 채워 넣으면 조인 것이 도로아미타불이 됩니다.
    #    다만 답에 번호가 있는데 하나도 못 읽었다면 형식이 어긋난 것이라 순위로 갑니다.
    if not 고른것 and re.search(r"\d", 답):
        print(f"  핫뉴스: 후보 {len(후보)}건 → 형식이 어긋나 순위대로 {몇건}건 · ${비용:.4f}")
        return 후보[:몇건]
    print(f"  핫뉴스: 후보 {len(후보)}건 → {len(고른것[:몇건])}건 골랐습니다 · ${비용:.4f}")
    return 고른것[:몇건]


# --- 같은 화제 접기 (2026-11-17 Gim «유사하거나 비슷한 것들 건수만 늘어나지 않게» → «한 칸으로 접기») ---
# 같은 보도자료 도배는 collect.한사건씩 이 제목으로 줄입니다. 하지만 «앤스로픽 상장»처럼 **서로 다른 기사가
# 같은 화제로 쌓이는 것**(11-17 실측 15건, 영어 · 한국어 섞임)은 제목 글자로 못 묶습니다.
# 그래서 실행마다 한 번, 한국어 한 줄(요약 > 번역 제목 > 원제목)을 모델에 보여 주고 화제끼리 번호를 묶게 합니다.
# 기사는 버리지 않습니다 — 화면에서 대표 1건 밑에 «관련 N건»으로 접힐 뿐입니다.
# ⛔ «같은 화제»만 말하면 모델이 **주제가 비슷한 다른 글**까지 묶습니다(11-17 첫 실행: 21묶음 중 약 절반 —
#    «클로드 기능 업데이트»에 릴리스 노트 · 새 모델 발표 · 다른 회사 MCP 출시가, «AI 에이전트 코딩»에 서로 다른
#    후기 6편이, «네이버 AI 기술»에 다른 기술 블로그 글 3편이 묶임). 그래서 «한 가지 사실» 기준과 빼는 보기를 둡니다.
화제지시 = (
    "너는 IT 뉴스 브리핑 편집자다. 아래 기사 가운데 **같은 사건 하나**를 전하는 기사끼리만 묶는다.\n"
    "- 같은 사건 = 같은 발표 · 사고 · 거래 · 결정 하나. 관점 · 매체 · 언어가 달라도 그 한 가지를 다루면 같다.\n"
    "  보기) 앤스로픽 상장 기사 여럿 / 삼성 갤럭시 XR 교실 도입 보도 여럿 / 같은 장애의 원인 기사 둘.\n"
    "- ⛔ 주제 · 분야 · 회사만 같고 **전하는 사실이 다르면 묶지 않는다.**\n"
    "  묶지 않는 보기) 같은 회사의 서로 다른 발표(새 모델 ↔ 릴리스 노트 ↔ 새 기능) / 서로 다른 사용 후기 ·\n"
    "  개발기 · 튜토리얼 · 칼럼 / 한 회사 기술 블로그의 다른 글들 / 비슷한 분야 다른 회사 제품.\n"
    "- 애매하면 묶지 않는다. 잘못 묶으면 기사가 숨어 버려, 안 묶는 것보다 훨씬 나쁘다.\n"
    "- [ ] 안 분야가 같은 것끼리만 묶는다.\n"
    "- 2건 이상인 사건만 적는다. 묶을 것이 없으면 아무것도 출력하지 않는다.\n"
    "\n"
    "출력 형식 — 화제마다 한 줄, 다른 말은 붙이지 않는다.\n"
    "화제 이름 15자 이내|번호,번호,번호\n"
    "보기)\n"
    "앤스로픽 상장|3,8,15,22\n"
    "갤럭시 XR 교육|5,9"
)
화제상한 = 400   # 이보다 많으면 앞에서부터 이만큼만 묶습니다(입력이 커지면 값이 오릅니다)
# 1M 토큰당 달러(2026-11 기준). 비용 줄이 실제 청구와 맞도록 모델마다 둡니다.
화제단가 = {"claude-haiku-4-5": 단가, "claude-haiku-5-5": {"in": 0.10, "out": 0.50},
            "claude-sonnet-5-5": {"in": 2.0, "out": 10.0}}
# 11-17 같은 수집분 대조 — Haiku 4.5 는 지시를 조여도 «앤스로픽 상장»에 새 모델 발표 · 이직 소식을,
#   «교육용 AI»에 서로 다른 행사 9건을 묶었다($0.015/회). Haiku 5.5(생각 low)는 11묶음 모두 같은 소식 ·
#   애매한 2건은 안 묶음 · $0.004/회(하루 8회 약 월 $1).
화제모델 = "claude-haiku-5-5"
화제노력 = "low"   # output_config.effort — 생각을 하는 모델에만 넣습니다


def _화제글(g: dict) -> str:
    return (g.get("summary") or g.get("ko") or g["title"]).strip()


def 화제읽기(답: str, 후보: list[dict]) -> int:
    """모델 답을 읽어 `g["화제"] = (이름, 번호)` 를 답니다. 묶인 화제 수를 돌려줍니다.

    한 기사가 두 화제에 나오면 먼저 나온 화제에 둡니다. 분야가 다른 것이 섞이면 첫 기사의 분야만 남깁니다.
    """
    쓴것, 화제수 = set(), 0
    for 줄 in 답.splitlines():
        이름, 칸, 번호들 = 줄.rpartition("|")
        if not 칸:
            continue
        이름 = re.sub(r"^\s*[-*\d.)\s]+(?=\D)", "", 이름).strip()[:20] or "같은 화제"
        식구 = []
        for n in re.findall(r"\d+", 번호들):
            i = int(n) - 1
            if 0 <= i < len(후보) and i not in 쓴것:
                식구.append(i)
        if 식구:
            분야 = 후보[식구[0]]["topic"]
            식구 = [i for i in 식구 if 후보[i]["topic"] == 분야]
        if len(식구) < 2:
            continue
        화제수 += 1
        for i in 식구:
            쓴것.add(i)
            후보[i]["화제"] = (이름, 화제수)
    return 화제수


def 화제묶기(기사: list[dict]) -> dict:
    """같은 화제 기사에 `g["화제"]` 를 답니다. 실패하면 아무것도 안 달고 화면은 그대로 돕니다."""
    잰것 = {"화제": 0, "접힘": 0, "비용": 0.0}
    for g in 기사:
        g.pop("화제", None)
    후보 = 기사[:화제상한]
    if len(후보) < 2 or not os.environ.get("ANTHROPIC_API_KEY"):
        return 잰것
    본문 = "\n".join(f"{i+1}. [{g['topic']}] {_화제글(g)}" for i, g in enumerate(후보))
    try:
        import anthropic
        덧: dict = {"output_config": {"effort": 화제노력}} if 화제노력 else {}
        m = anthropic.Anthropic().messages.create(
            model=화제모델, max_tokens=8000, system=화제지시,
            messages=[{"role": "user", "content": 본문}], **덧)
        답 = "".join(b.text for b in m.content if b.type == "text")
        값 = 화제단가.get(화제모델, 단가)
        잰것["비용"] = (m.usage.input_tokens / 1e6 * 값["in"]
                     + m.usage.output_tokens / 1e6 * 값["out"])
    except Exception as e:
        print(f"  (화제 묶기 실패, 접지 않고 그대로 둡니다: {e})")
        return 잰것
    잰것["화제"] = 화제읽기(답, 후보)
    잰것["접힘"] = sum(1 for g in 후보 if g.get("화제")) - 잰것["화제"]
    return 잰것


제목캐시 = "titles.json"   # {지문: 한글 제목}
제목묶음 = 25              # 한 호출에 몇 개씩 넣을지. 제목은 짧아 묶어 보내는 편이 훨씬 쌉니다.
_한글 = re.compile(r"[가-힣]")

제목지시 = (
    "너는 IT 뉴스 제목을 한국어로 옮긴다.\n"
    "- 제목 그대로 옮긴다. 요약하거나 설명을 보태지 않는다.\n"
    "- 회사·제품·서비스 이름은 널리 쓰이는 한국어 표기가 있으면 그것을 쓰고,\n"
    "  없으면 원문 그대로 둔다(예: Anthropic→앤스로픽, Hacker News→Hacker News).\n"
    "- 40자 이내로 자연스럽게. 직역투를 피한다.\n"
    "\n"
    "출력 형식 — 받은 번호마다 한 줄씩, 다른 말은 붙이지 않는다.\n"
    "번호|한국어 제목"
)


def 옮길것(g: dict) -> bool:
    """제목에 한글이 하나도 없고 한글 요약도 못 붙은 기사인지.

    요약이 붙은 카드에는 이미 한국어 한 줄이 있습니다. 거기에 제목 번역까지 넣으면
    같은 말이 두 줄이 됩니다(2026-08-05 실측: 영문 제목 111건 중 80건이 여기 해당).
    """
    return not _한글.search(g["title"]) and not g.get("summary")


def 제목옮기기(기사: list[dict], path: str = 제목캐시) -> dict:
    """`g["ko"]` 에 한국어 제목을 채웁니다. 실패해도 화면은 그대로 돕니다."""
    잰것 = {"새로": 0, "재사용": 0, "비용": 0.0}
    try:
        with open(path, encoding="utf-8") as f:
            캐시 = json.load(f)
    except (OSError, ValueError):
        캐시 = {}
    for g in 기사:
        g["ko"] = 캐시.get(g["fp"], "")

    할것 = [g for g in 기사 if 옮길것(g) and not g["ko"]]
    잰것["재사용"] = sum(1 for g in 기사 if g["ko"])
    if 할것 and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            덩이 = [할것[i:i + 제목묶음] for i in range(0, len(할것), 제목묶음)]

            def 한덩이(묶음):
                본문 = "\n".join(f"{i+1}. {g['title']}" for i, g in enumerate(묶음))
                m = client.messages.create(model=MODEL, max_tokens=60 * len(묶음),
                                           system=제목지시,
                                           messages=[{"role": "user", "content": 본문}])
                답 = "".join(b.text for b in m.content if b.type == "text")
                return 묶음, 답, m.usage.input_tokens, m.usage.output_tokens

            with cf.ThreadPoolExecutor(max_workers=동시) as pool:
                for fut in cf.as_completed([pool.submit(한덩이, d) for d in 덩이]):
                    묶음, 답, i, o = fut.result()
                    잰것["in"] = 잰것.get("in", 0) + i
                    잰것["out"] = 잰것.get("out", 0) + o
                    for 줄 in 답.splitlines():
                        # ⛔ `번호|글` 만 받으면 안 됩니다 — 입력을 "1. 제목" 으로 번호 매겨
                        #    보내면 모델이 그 형식을 따라 "1. 번역" 으로 답합니다.
                        #    그러면 25건짜리 묶음이 통째로 버려집니다(2026-08-05 실측).
                        m = re.match(r"\s*(\d+)\s*[|.):\-]\s*(.+)$", 줄)
                        if not m:
                            continue
                        k = int(m.group(1)) - 1
                        if 0 <= k < len(묶음):
                            캐시[묶음[k]["fp"]] = m.group(2).strip()
                            잰것["새로"] += 1
        except Exception as e:
            print(f"  (제목 번역 실패, 원문 그대로 둡니다: {e})")

    for g in 기사:
        g["ko"] = 캐시.get(g["fp"], "")
    잰것["비용"] = (잰것.get("in", 0) / 1e6 * 단가["in"]
                 + 잰것.get("out", 0) / 1e6 * 단가["out"])
    요약저장(캐시, {g["fp"] for g in 기사}, path)   # 이번에 본 기사 것만 남깁니다
    return 잰것


핫캐시 = "hot.json"   # {지문: {"왜": ..., "at": ISO}}. 화면 맨 위 핫이슈 칸을 채웁니다.
핫유지 = 12           # 몇 시간 전에 뽑힌 것까지 핫이슈로 둘지. 밤 8시간 공백을 덮습니다.
핫표시 = 10           # 화면에 한꺼번에 보일 최대 건수


def 핫기록(고른것: list[dict], 지금: dt.datetime, path: str = 핫캐시) -> dict:
    """이번에 고른 핫뉴스를 쌓고, 오래된 것은 버린 뒤 전체를 돌려줍니다.

    알림에 나간 것이 곧 핫이슈입니다. 화면용으로 따로 부르지 않으므로 추가 비용이 없습니다.
    """
    try:
        with open(path, encoding="utf-8") as f:
            쌓인것 = json.load(f)
    except (OSError, ValueError):
        쌓인것 = {}

    for g in 고른것:
        쌓인것[g["fp"]] = {"왜": g.get("왜", "") or g.get("summary", ""),
                          "at": 지금.isoformat()}
    기준 = 지금 - dt.timedelta(hours=핫유지)
    남길 = {}
    for fp, v in 쌓인것.items():
        try:
            if dt.datetime.fromisoformat(v["at"]) >= 기준:
                남길[fp] = v
        except (KeyError, ValueError, TypeError):
            continue   # 모양이 깨진 항목은 조용히 버립니다
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(남길, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path)
    return 남길


# ⛔ 모델이 판정 결과 «싣는다.»를 요약 앞에 붙여 내는 일이 있습니다(11-17 캐시 218건 중 5건 — 화면에 «싣는다.»가 그대로 나옴).
_판정새김 = re.compile(r"^\s*(싣는다|싣음|싣기)[.。]?\s*")


def 다듬기(글: str) -> str:
    return _판정새김.sub("", 글).strip() if isinstance(글, str) else 글


def 이전요약(path: str = CACHE) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return {k: 다듬기(v) for k, v in json.load(f).items()}   # 지난 캐시에 남은 것도 여기서 지움
    except (OSError, ValueError, AttributeError):
        return {}


def 요약저장(캐시: dict, 살릴지문: set, path: str = CACHE) -> None:
    """이번에 본 기사 것만 남깁니다. 안 그러면 파일이 계속 커집니다."""
    남길 = {k: v for k, v in 캐시.items() if k in 살릴지문}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(남길, f, ensure_ascii=False, indent=0, sort_keys=True)
    os.replace(tmp, path)


def _한건(client, g: dict) -> tuple[str, str, int, int, bool]:
    본문 = f"제목: {g['title']}\n매체: {g.get('source', '')}\n본문: {g['desc']}"
    쓸지시 = 지시_요약만 if g.get("source") in 판정면제 else 지시
    m = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=쓸지시,
                               messages=[{"role": "user", "content": 본문}])
    글 = 다듬기("".join(b.text for b in m.content if b.type == "text"))
    입, 출, 줄였다 = m.usage.input_tokens, m.usage.output_tokens, False

    if len(글) > 줄임한계:
        try:
            m2 = client.messages.create(model=MODEL, max_tokens=100, system=줄임지시,
                                        messages=[{"role": "user", "content": 글}])
            줄인 = "".join(b.text for b in m2.content if b.type == "text").strip()
            입 += m2.usage.input_tokens
            출 += m2.usage.output_tokens
            # 더 길어지거나 빈 답이 오면 원문을 그대로 둡니다. 줄이기는 덤입니다.
            if 줄인 and len(줄인) < len(글):
                글, 줄였다 = 줄인, True
        except Exception:
            pass   # 줄이기 실패로 요약 자체를 잃지 않습니다
    return g["fp"], 글, 입, 출, 줄였다


def 채우기(기사: list[dict], path: str = CACHE) -> dict:
    """`g["summary"]` 를 채웁니다. 요약할 수 없는 상황이면 조용히 넘어갑니다.

    요약은 **덤**입니다. 키가 없든 API 가 죽었든, 화면 생성과 알림은 그대로 돌아야 합니다.
    그래서 이 함수는 예외를 밖으로 내보내지 않습니다.
    """
    잰것 = {"새로": 0, "재사용": 0, "건너뜀": 0, "실패": 0, "줄임": 0,
           "in": 0, "out": 0, "비용": 0.0}
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
                fp, 글, i, o, 줄였다 = fut.result()
            except Exception as e:
                잰것["실패"] += 1
                if 잰것["실패"] == 1:      # 같은 오류가 100줄 찍히지 않게 첫 건만 남깁니다
                    print(f"  (요약 실패: {e})")
                continue
            캐시[fp] = 글
            잰것["새로"] += 1
            잰것["줄임"] += 줄였다
            잰것["in"] += i
            잰것["out"] += o

    for g in 기사:
        g["summary"] = 캐시.get(g["fp"], "")
    잰것["비용"] = 잰것["in"] / 1e6 * 단가["in"] + 잰것["out"] / 1e6 * 단가["out"]
    요약저장(캐시, {g["fp"] for g in 기사}, path)
    return 잰것
