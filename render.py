# 기사 목록을 폰에서 읽기 좋은 정적 HTML 한 장으로 만듭니다 (검색·색인·필터 포함)
import datetime as dt
import html
import json

from sources import 분야순서
from summarize import 핫표시

REFRESH = 600  # 페이지 자동 새로고침(초). 수집 주기보다 짧게 둘 이유가 없습니다.
KST = dt.timezone(dt.timedelta(hours=9))
본문상한 = 3   # 첫 화면에서 분야마다 보여 줄 기사 수. 나머지는 분야 탭에서 봅니다.

# 분야별 색. 카드 배경·칩 점·분야 제목에 같은 색을 물려 색만으로 구분되게 합니다.
# 배경에는 아주 옅게(밝을 때 6%, 어두울 때 13%)만 깔아 글자 대비를 해치지 않습니다.
# 색상환에서 멀리 떨어진 넷을 골라 옅어져도 서로 구분됩니다.
분야색 = {
    "AI·클로드": "#3b6fd4",    # 파랑
    "게임개발": "#8b5cf6",      # 보라
    "유튜브·쇼츠": "#e11d48",   # 빨강
    "IT이슈": "#0d9488",       # 청록
}
기본색 = "#78716c"  # 목록에 없는 분야가 생겨도 무채색으로 나옵니다.
핫색 = "#ea580c"    # 핫이슈 — 네 분야 어느 색과도 겹치지 않는 주황입니다.

# Pretendard 는 맑은 고딕보다 한글 획이 굵고 자간이 고릅니다. 못 받아 오면
# 시스템 폰트로 자연스럽게 내려앉으므로 페이지가 깨지지 않습니다.
_FONT = ("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/"
         "variable/pretendardvariable-dynamic-subset.min.css")

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,
 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 font-size:17px;line-height:1.5;letter-spacing:-.01em;
 background:#faf9f7;color:#191714;padding:0 0 28px;-webkit-text-size-adjust:100%}
@media(prefers-color-scheme:dark){body{background:#131210;color:#ece8e0}}

/* 헤더는 한 줄. 제목·건수·검색칸을 나란히 놓아 세로 공간을 쓰지 않습니다. */
header{position:sticky;top:0;z-index:3;padding:7px 10px;border-bottom:1px solid #0002;
 background:#faf9f7f2;backdrop-filter:blur(10px);display:flex;align-items:center;gap:8px}
@media(prefers-color-scheme:dark){header{background:#131210f2;border-color:#fff2}}
h1{font-size:15px;font-weight:800;letter-spacing:-.04em;white-space:nowrap}
.meta{font-size:11.5px;opacity:.55;white-space:nowrap;font-weight:600}
.meta b{color:#c2410c;font-weight:800}

.search{position:relative;flex:1;min-width:0}
#q{width:100%;font:inherit;font-size:15px;padding:6px 28px 6px 10px;border-radius:9px;
 border:1.5px solid #0002;background:#fff;color:inherit;outline:none}
#q:focus{border-color:#c2410c}
#q::placeholder{opacity:.45}
@media(prefers-color-scheme:dark){#q{background:#1e1c18;border-color:#fff3}}
#clear{position:absolute;right:2px;top:50%;transform:translateY(-50%);border:0;
 background:none;color:inherit;opacity:.4;font-size:17px;cursor:pointer;padding:3px 6px;
 display:none;line-height:1}

/* 분야 탭은 한 줄에 넷이 다 들어가야 합니다. 색 점을 빼고 글자에 분야 색을 물립니다. */
/* 360px 에 넷이 딱 맞습니다(여유 7px). 신규가 두 자리가 되면 넘칠 수 있어
   가로 스크롤을 안전장치로 둡니다 — 줄바꿈은 어차피 생기지 않습니다. */
.chips{display:flex;gap:4px;padding:6px 8px 0;overflow-x:auto;scrollbar-width:none;
 -webkit-overflow-scrolling:touch}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font-size:12px;font-weight:700;padding:4px 8px;border-radius:99px;
 border:1.5px solid #0002;background:none;color:inherit;cursor:pointer;white-space:nowrap}
.chip[aria-pressed="true"]{background:#c2410c;border-color:#c2410c;color:#fff}
.chip .nn{color:#c2410c;font-weight:800;margin-left:3px}
.chip[aria-pressed="true"] .nn{color:#fff}
@media(prefers-color-scheme:dark){.chip{border-color:#fff3}.chip .nn{color:#fb7c45}}

section{padding:11px 10px 0}
section h2{font-size:14px;font-weight:800;letter-spacing:-.02em;color:var(--tint)}
/* 분야 접기. details 를 쓰면 키보드·스크린리더 동작이 브라우저에서 그냥 따라옵니다. */
summary{list-style:none;cursor:pointer;display:flex;align-items:center;padding:0 0 5px}
summary::-webkit-details-marker{display:none}
summary::after{content:"";margin-left:auto;width:7px;height:7px;
 border-right:2px solid var(--tint);border-bottom:2px solid var(--tint);opacity:.5;
 transform:rotate(45deg) translate(-3px,-3px);transition:transform .15s}
details:not([open]) summary::after{transform:rotate(-45deg)}
.rest{margin-top:5px;width:100%;font:inherit;font-size:13px;font-weight:700;
 color:var(--tint);background:none;border-radius:9px;padding:6px 10px;cursor:pointer;
 border:1.5px solid color-mix(in srgb,var(--tint) 32%,transparent)}
ul{list-style:none;display:flex;flex-direction:column;gap:5px}
/* 분야 색 카드. color-mix 를 못 쓰는 낡은 브라우저에서는 배경만 빠지고 글은 그대로 읽힙니다. */
li{padding:8px 10px;border-radius:10px;background:transparent;
 background:color-mix(in srgb,var(--tint) 6%,transparent);
 border:1px solid color-mix(in srgb,var(--tint) 15%,transparent)}
@media(prefers-color-scheme:dark){
 li{background:color-mix(in srgb,var(--tint) 13%,transparent);
    border-color:color-mix(in srgb,var(--tint) 26%,transparent)}}
li.empty{background:none;border:0;padding-left:0}
.chip[data-kind="topic"]{color:var(--tint)}
.chip[data-kind="topic"][aria-pressed="true"]{background:var(--tint);border-color:var(--tint);
 color:#fff}
a.t{color:inherit;text-decoration:none;font-size:17px;font-weight:700;line-height:1.34;
 letter-spacing:-.025em;display:block}
a.t:hover{text-decoration:underline}
/* 영문 제목 밑에 붙는 한국어 제목. 제목의 일부처럼 보이되 원문보다는 약하게 씁니다. */
.ko{font-size:14.5px;font-weight:600;opacity:.72;margin-top:3px;line-height:1.38;
 letter-spacing:-.02em}
.sub{font-size:12px;opacity:.5;margin-top:2px;font-weight:500}
.new{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.03em;
 background:#c2410c;color:#fff;border-radius:4px;padding:1px 4px;margin-right:5px;
 vertical-align:2px}
.sum{font-size:14.5px;opacity:.75;margin-top:3px;line-height:1.5}
mark{background:#fde68a;color:#000;border-radius:2px;padding:0 1px}
@media(prefers-color-scheme:dark){mark{background:#a16207;color:#fff}}
.empty{opacity:.42;font-size:14px;padding:4px 0}
#none{display:none;padding:30px 16px;text-align:center;opacity:.5;font-size:15px}
footer{padding:20px 10px 0;font-size:12px;opacity:.4;line-height:1.7}
/* 분야를 고르거나 검색 중일 때만 뜨는 「전체로」 단추. 한 분야만 보고 있으면
   맨 위 탭까지 올라가야 빠져나올 수 있어서, 손가락이 닿는 오른쪽 아래에 둡니다.
   safe-area 를 더해 아이폰 홈바에 가리지 않게 합니다. */
#back{position:fixed;right:14px;bottom:calc(14px + env(safe-area-inset-bottom));z-index:5;
 font:inherit;font-size:14px;font-weight:700;color:#fff;background:#292524ee;
 border:0;border-radius:99px;padding:12px 16px;min-height:44px;cursor:pointer;
 box-shadow:0 3px 14px #0004;backdrop-filter:blur(6px)}
#back[hidden]{display:none}
@media (prefers-color-scheme:dark){#back{background:#e7e5e4ee;color:#1c1917}}
"""

# 검색·색인 동작. 240건 정도는 단순 순회로 즉시 걸러집니다.
_JS = """
const q=document.getElementById('q'),clear=document.getElementById('clear'),
 none=document.getElementById('none'),cnt=document.getElementById('cnt'),
 back=document.getElementById('back'),
 chips=[...document.querySelectorAll('.chip')];
let 분야=null;
const 상한=__LIMIT__;
// 접어 둔 분야는 기억합니다. 페이지가 10분마다 스스로 새로고침하므로
// 저장하지 않으면 접을 때마다 도로 펼쳐집니다.
// 사생활 모드에서는 localStorage 가 예외를 던집니다. 여기서 죽으면 검색까지 같이 죽으므로
// 저장은 실패해도 그냥 넘어갑니다 — 기억을 못 할 뿐 화면은 멀쩡히 돕니다.
let 접힘=new Set();
try{ 접힘=new Set(JSON.parse(localStorage.getItem('fold')||'[]')) }catch(e){}
const 접힘저장=()=>{ try{ localStorage.setItem('fold',JSON.stringify([...접힘])) }catch(e){} };

function 표시(){
  const 말=q.value.trim().toLowerCase();
  clear.style.display=q.value?'block':'none';
  // 조건이 하나도 없는 첫 화면에서만 분야당 몇 건으로 줄입니다.
  // 검색·필터 중에는 걸러진 결과를 통째로 보여 줘야 합니다.
  const 제한=!말&&!분야;
  let 보임=0;
  for(const s of document.querySelectorAll('section[data-t]')){
    let 통과=0, 남음=0;
    for(const li of s.querySelectorAll('li[data-k]')){
      const ok=(!말||li.dataset.k.includes(말))&&(!분야||li.dataset.t===분야);
      if(ok&&제한&&통과>=상한){ li.hidden=true; 남음++; 보임++; continue; }
      li.hidden=!ok; if(ok){ 통과++; 보임++; }
    }
    const rest=s.querySelector('.rest');
    if(rest){ rest.hidden=!남음; rest.textContent='나머지 '+남음+'건 보기'; }
    // 접힌 분야도 제목은 남겨야 다시 펼 수 있습니다. 검색 중에는 자동으로 폅니다.
    s.querySelector('details').open=!제한||!접힘.has(s.dataset.t);
    s.hidden=!통과&&!남음;
  }
  none.style.display=보임?'none':'block';
  cnt.textContent=보임;
  // 첫 화면(조건 없음)에서는 돌아갈 곳이 없으므로 숨깁니다.
  back.hidden=제한;
  back.textContent=분야?'← 전체 보기':'← 검색 지우기';
}
q.addEventListener('input',표시);
// 한글은 조합이 끝나는 시점에 한 번 더 훑어야 마지막 글자가 반영됩니다.
q.addEventListener('compositionend',표시);
clear.onclick=()=>{q.value='';표시();q.focus()};

// 「전체로」 — 분야 선택과 검색어를 한꺼번에 풀고 맨 위로 올립니다.
const 전체로=()=>{
  분야=null; q.value='';
  for(const o of chips) o.setAttribute('aria-pressed','false');
  표시(); window.scrollTo({top:0,behavior:'smooth'});
};
back.onclick=전체로;

for(const c of chips){
  c.onclick=()=>{
    const 켜짐=c.getAttribute('aria-pressed')==='true';
    for(const o of chips) o.setAttribute('aria-pressed','false');
    c.setAttribute('aria-pressed', 켜짐?'false':'true');
    분야=켜짐?null:c.dataset.val;
    표시(); window.scrollTo({top:0,behavior:'smooth'});
  };
}
// 분야 접기·펼치기. 브라우저 기본 동작을 막고 직접 여닫아야 저장 시점이 어긋나지 않습니다.
for(const s of document.querySelectorAll('section[data-t]')){
  const d=s.querySelector('details'), t=s.dataset.t;
  if(접힘.has(t)) d.open=false;
  d.querySelector('summary').addEventListener('click',e=>{
    e.preventDefault();
    d.open=!d.open;
    d.open?접힘.delete(t):접힘.add(t);
    접힘저장();
  });
}
// "나머지 N건 보기" 는 그 분야 탭을 누른 것과 같습니다.
for(const b of document.querySelectorAll('.rest')) b.onclick=()=>
  chips.find(c=>c.dataset.val===b.dataset.val).click();
"""


def _색규칙() -> str:
    """분야마다 `--tint` 를 물려 주는 CSS. 분야를 추가해도 여기서 자동으로 따라옵니다."""
    줄 = [f":root,section,li{{--tint:{기본색}}}"]
    for 분야, 색 in {**분야색, 핫이슈: 핫색}.items():
        s = html.escape(분야, quote=True)
        줄.append(f'li[data-t="{s}"],section[data-t="{s}"],'
                  f'.chip[data-kind="topic"][data-val="{s}"]{{--tint:{색}}}')
    # 핫이슈 탭은 누르기 전에도 눈에 띄어야 합니다. 첫 탭인 것만으로는 약합니다.
    줄.append(f'.chip[data-val="{html.escape(핫이슈, quote=True)}"]'
              f'{{background:color-mix(in srgb,{핫색} 12%,transparent);'
              f'border-color:color-mix(in srgb,{핫색} 38%,transparent)}}')
    return "\n".join(줄)


def _시각표기(d: dt.datetime | None) -> str:
    if d is None:
        return ""
    d = d.astimezone(KST)
    차 = dt.datetime.now(KST) - d
    if 차 < dt.timedelta(minutes=60):
        return f"{max(1, int(차.total_seconds() // 60))}분 전"
    if 차 < dt.timedelta(hours=24):
        return f"{int(차.total_seconds() // 3600)}시간 전"
    return d.strftime("%m-%d %H:%M")


핫이슈 = "핫이슈"   # 맨 위에 오는 가짜 분야. 실제 분야는 기사마다 그대로 남아 있습니다.

# 탭이 다섯이 되면 360px 폰 한 줄에 안 들어갑니다. 탭에서만 짧게 씁니다 —
# 섹션 제목과 카드의 분야 색은 원래 이름 그대로입니다.
탭줄임 = {"AI·클로드": "AI", "유튜브·쇼츠": "유튜브"}


def _탭이름(분야: str) -> str:
    return 탭줄임.get(분야, 분야)


def _기사(g: dict, 새것: set, 숨김: bool = False, 분야덮기: str = "",
        한줄: str = "") -> str:
    e = html.escape
    뱃지 = '<span class="new">NEW</span>' if g["fp"] in 새것 else ""
    부가 = " · ".join(x for x in (e(g["source"]), _시각표기(g["at"])) if x)
    # 핫이슈 칸에서는 「왜 지금 중요한지」를 요약 대신 보여 줍니다. 더 짧고 판단에 바로 닿습니다.
    본글 = 한줄 or g.get("summary", "")
    요약 = f'<div class="sum">{e(본글)}</div>' if 본글 else ""
    # 영문 제목에만 붙는 한국어 제목. 제목 바로 밑에 둡니다 — 출처보다 먼저 눈에 들어와야 합니다.
    옮김 = f'<div class="ko">{e(g["ko"])}</div>' if g.get("ko") else ""
    # data-k = 검색 대상(제목+출처+요약). 미리 소문자로 만들어 두면 걸러낼 때 빠릅니다.
    열쇠 = e(f"{g['title']} {g['source']} {g.get('summary', '')}".lower())
    # 상한을 넘는 기사는 서버에서 미리 감춥니다. 첫 화면이 240건 그렸다가 줄어들면 눈에 띕니다.
    return (f'<li{" hidden" if 숨김 else ""} '
            f'data-k="{열쇠}" data-t="{e(분야덮기 or g["topic"])}">'
            f'<a class="t" href="{e(g["url"])}" target="_blank" rel="noopener">'
            f'{뱃지}{e(g["title"])}</a>{옮김}<div class="sub">{부가}</div>{요약}</li>')


def 만들기(기사: list[dict], 새것: set, 실패: list[str], 갱신: dt.datetime,
         핫: dict | None = None) -> str:
    e = html.escape
    묶음 = {분야: [] for 분야 in 분야순서}
    for g in 기사:
        묶음.setdefault(g["topic"], []).append(g)

    신규수 = {분야: sum(1 for g in 묶음.get(분야, []) if g["fp"] in 새것) for 분야 in 분야순서}

    본문 = []

    # 핫이슈를 맨 위에 둡니다. 알림으로 이미 나간 것과 같은 목록이라 따로 부르지 않습니다.
    # 원래 분야 칸에도 그대로 남깁니다 — 여기서 빼면 분야 탭을 눌렀을 때 큰 뉴스가 사라집니다.
    핫목록 = []
    if 핫:
        핫목록 = sorted((g for g in 기사 if g["fp"] in 핫),
                      key=lambda g: 핫[g["fp"]].get("at", ""), reverse=True)[:핫표시]
    if 핫목록:
        속 = "".join(_기사(g, 새것, 숨김=i >= 본문상한, 분야덮기=핫이슈,
                          한줄=핫[g["fp"]].get("왜"))
                    for i, g in enumerate(핫목록))
        남음 = max(0, len(핫목록) - 본문상한)
        더 = (f'<button class="rest" data-val="{e(핫이슈)}"{"" if 남음 else " hidden"}>'
              f'나머지 {남음}건 보기</button>')
        본문.append(f'<section data-t="{e(핫이슈)}"><details open>'
                    f'<summary><h2>{e(핫이슈)} '
                    f"<span style='opacity:.65'>{len(핫목록)}</span></h2></summary>"
                    f'<ul>{속}</ul>{더}</details></section>')

    for 분야 in 분야순서:
        목록 = 묶음.get(분야, [])
        n = 신규수[분야]
        머리 = f"{e(분야)} <span style='opacity:.65'>{len(목록)}</span>"
        머리 += f" <span style='color:#c2410c'>+{n}</span>" if n else ""
        속 = ("".join(_기사(g, 새것, 숨김=i >= 본문상한) for i, g in enumerate(목록)) if 목록
              else '<li class="empty">새 소식이 없습니다.</li>')
        남음 = max(0, len(목록) - 본문상한)
        더 = (f'<button class="rest" data-val="{e(분야)}"{"" if 남음 else " hidden"}>'
              f'나머지 {남음}건 보기</button>')
        본문.append(f'<section data-t="{e(분야)}"><details open>'
                    f'<summary><h2>{머리}</h2></summary>'
                    f'<ul>{속}</ul>{더}</details></section>')

    # 탭에는 분야명과 신규 수만. 전체 건수까지 넣으면 폰 한 줄(360px)에 안 들어갑니다.
    # 전체 건수는 바로 아래 섹션 제목에 그대로 있습니다.
    # 핫이슈가 첫 탭입니다. 다섯이 한 줄에 들어가도록 긴 두 이름을 줄여 씁니다(_탭이름).
    칩들 = ([(핫이슈, len(핫목록))] if 핫목록 else []) + [(t, 신규수[t]) for t in 분야순서]
    분야칩 = "".join(
        f'<button class="chip" data-kind="topic" data-val="{e(t)}" aria-pressed="false">'
        f'{e(_탭이름(t))}'
        + (f'<span class="nn">+{n}</span>' if n and t != 핫이슈 else "")
        + '</button>' for t, n in 칩들)
    주의 = f"<br>수집 실패: {e(', '.join(실패))}" if 실패 else ""

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}">
<title>뉴스 브리핑</title>
<link rel="stylesheet" href="{_FONT}">
<style>{_CSS}
{_색규칙()}</style></head><body>
<header>
  <h1>뉴스 브리핑</h1>
  <div class="meta"><span id="cnt">{len(기사)}</span>{f' <b>+{len(새것)}</b>' if 새것 else ''}</div>
  <div class="search">
    <input id="q" type="search" placeholder="검색" autocomplete="off"
           enterkeyhint="search" aria-label="검색">
    <button id="clear" aria-label="지우기">&times;</button>
  </div>
</header>
<div class="chips">{분야칩}</div>
{''.join(본문)}
<div id="none">검색 결과가 없습니다.</div>
<button id="back" hidden aria-label="전체 목록으로 돌아가기">← 전체 보기</button>
<footer>{갱신.astimezone(KST):%Y-%m-%d %H:%M} 기준 · 2시간마다 자동 갱신 ·
페이지는 {REFRESH // 60}분마다 스스로 새로고침합니다.{주의}</footer>
<script>{_JS.replace("__LIMIT__", str(본문상한))}</script>
</body></html>"""
