# 기사 목록을 폰에서 읽기 좋은 정적 HTML 한 장으로 만듭니다 (검색·색인·필터 포함)
import datetime as dt
import html
import json

from sources import 분야순서

REFRESH = 600  # 페이지 자동 새로고침(초). 수집 주기보다 짧게 둘 이유가 없습니다.
KST = dt.timezone(dt.timedelta(hours=9))
색인상한 = 14  # 색인에 칩으로 보여 줄 출처 수. 나머지는 "더 보기"로 폅니다.
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

# Pretendard 는 맑은 고딕보다 한글 획이 굵고 자간이 고릅니다. 못 받아 오면
# 시스템 폰트로 자연스럽게 내려앉으므로 페이지가 깨지지 않습니다.
_FONT = ("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/"
         "variable/pretendardvariable-dynamic-subset.min.css")

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,
 "Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 font-size:17px;line-height:1.62;letter-spacing:-.01em;
 background:#faf9f7;color:#191714;padding:0 0 60px;-webkit-text-size-adjust:100%}
@media(prefers-color-scheme:dark){body{background:#131210;color:#ece8e0}}

header{position:sticky;top:0;z-index:3;padding:13px 16px 10px;border-bottom:1px solid #0002;
 background:#faf9f7f2;backdrop-filter:blur(10px)}
@media(prefers-color-scheme:dark){header{background:#131210f2;border-color:#fff2}}
.top{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
h1{font-size:20px;font-weight:800;letter-spacing:-.03em}
.meta{font-size:13px;opacity:.62;white-space:nowrap}

.search{position:relative;margin-top:10px}
#q{width:100%;font:inherit;font-size:16.5px;padding:10px 38px 10px 14px;border-radius:11px;
 border:1.5px solid #0002;background:#fff;color:inherit;outline:none}
#q:focus{border-color:#c2410c}
#q::placeholder{opacity:.45}
@media(prefers-color-scheme:dark){#q{background:#1e1c18;border-color:#fff3}}
#clear{position:absolute;right:6px;top:50%;transform:translateY(-50%);border:0;
 background:none;color:inherit;opacity:.4;font-size:20px;cursor:pointer;padding:4px 8px;
 display:none;line-height:1}

.chips{display:flex;gap:6px;overflow-x:auto;padding:9px 16px 0;-webkit-overflow-scrolling:touch;
 scrollbar-width:none}
.chips::-webkit-scrollbar{display:none}
.chips.wrap{flex-wrap:wrap;overflow:visible}
.chip{flex:0 0 auto;font-size:13.5px;font-weight:600;padding:5px 12px;border-radius:99px;
 border:1.5px solid #0002;background:none;color:inherit;cursor:pointer;white-space:nowrap}
.chip[aria-pressed="true"]{background:#c2410c;border-color:#c2410c;color:#fff}
.chip .n{opacity:.55;font-weight:500;margin-left:4px}
.chip[aria-pressed="true"] .n{opacity:.8}
.chip .nn{color:#c2410c;font-weight:800;margin-left:4px}
.chip[aria-pressed="true"] .nn{color:#fff}
@media(prefers-color-scheme:dark){.chip{border-color:#fff3}.chip .nn{color:#fb7c45}}

.idx{padding:10px 16px 0}
.idx h3{font-size:12.5px;letter-spacing:.06em;opacity:.42;text-transform:uppercase;
 margin-bottom:7px;font-weight:700}
#more{font-size:13px;opacity:.55;background:none;border:0;color:inherit;cursor:pointer;
 padding:6px 2px;text-decoration:underline}

section{padding:24px 16px 0}
section h2{font-size:15px;font-weight:800;letter-spacing:-.01em;color:var(--tint)}
/* 분야 접기. details 를 쓰면 키보드·스크린리더 동작이 브라우저에서 그냥 따라옵니다. */
summary{list-style:none;cursor:pointer;display:flex;align-items:center;padding:2px 0 9px}
summary::-webkit-details-marker{display:none}
summary::after{content:"";margin-left:auto;width:7px;height:7px;
 border-right:2px solid var(--tint);border-bottom:2px solid var(--tint);opacity:.5;
 transform:rotate(45deg) translate(-3px,-3px);transition:transform .15s}
details:not([open]) summary::after{transform:rotate(-45deg)}
.rest{margin-top:9px;width:100%;font:inherit;font-size:13.5px;font-weight:700;
 color:var(--tint);background:none;border-radius:10px;padding:8px 12px;cursor:pointer;
 border:1.5px solid color-mix(in srgb,var(--tint) 32%,transparent)}
ul{list-style:none;display:flex;flex-direction:column;gap:7px}
/* 분야 색 카드. color-mix 를 못 쓰는 낡은 브라우저에서는 배경만 빠지고 글은 그대로 읽힙니다. */
li{padding:13px 14px;border-radius:13px;background:transparent;
 background:color-mix(in srgb,var(--tint) 6%,transparent);
 border:1px solid color-mix(in srgb,var(--tint) 15%,transparent)}
@media(prefers-color-scheme:dark){
 li{background:color-mix(in srgb,var(--tint) 13%,transparent);
    border-color:color-mix(in srgb,var(--tint) 26%,transparent)}}
li.empty{background:none;border:0;padding-left:0}
.chip[data-kind="topic"]::before{content:"";display:inline-block;width:8px;height:8px;
 border-radius:50%;background:var(--tint);margin-right:6px;vertical-align:.5px}
.chip[data-kind="topic"][aria-pressed="true"]{background:var(--tint);border-color:var(--tint)}
.chip[data-kind="topic"][aria-pressed="true"]::before{background:#fff}
a.t{color:inherit;text-decoration:none;font-size:18px;font-weight:700;line-height:1.45;
 letter-spacing:-.02em;display:block}
a.t:hover{text-decoration:underline}
.sub{font-size:13px;opacity:.55;margin-top:5px;font-weight:500}
.new{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.03em;
 background:#c2410c;color:#fff;border-radius:4px;padding:1.5px 5px;margin-right:6px;
 vertical-align:2px}
.sum{font-size:15px;opacity:.75;margin-top:6px;line-height:1.6}
mark{background:#fde68a;color:#000;border-radius:2px;padding:0 1px}
@media(prefers-color-scheme:dark){mark{background:#a16207;color:#fff}}
.empty{opacity:.42;font-size:14.5px;padding:8px 0}
#none{display:none;padding:40px 16px;text-align:center;opacity:.5;font-size:15px}
footer{padding:34px 16px 0;font-size:12.5px;opacity:.42;line-height:1.75}
"""

# 검색·색인 동작. 240건 정도는 단순 순회로 즉시 걸러집니다.
_JS = """
const q=document.getElementById('q'),clear=document.getElementById('clear'),
 none=document.getElementById('none'),cnt=document.getElementById('cnt'),
 chips=[...document.querySelectorAll('.chip')];
let 분야=null, 출처=null;
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
  const 제한=!말&&!분야&&!출처;
  let 보임=0;
  for(const s of document.querySelectorAll('section[data-t]')){
    let 통과=0, 남음=0;
    for(const li of s.querySelectorAll('li[data-k]')){
      const ok=(!말||li.dataset.k.includes(말))
        &&(!분야||li.dataset.t===분야)&&(!출처||li.dataset.s===출처);
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
}
q.addEventListener('input',표시);
// 한글은 조합이 끝나는 시점에 한 번 더 훑어야 마지막 글자가 반영됩니다.
q.addEventListener('compositionend',표시);
clear.onclick=()=>{q.value='';표시();q.focus()};

for(const c of chips){
  c.onclick=()=>{
    const 종류=c.dataset.kind, 값=c.dataset.val, 켜짐=c.getAttribute('aria-pressed')==='true';
    for(const o of chips) if(o.dataset.kind===종류) o.setAttribute('aria-pressed','false');
    c.setAttribute('aria-pressed', 켜짐?'false':'true');
    if(종류==='topic') 분야=켜짐?null:값; else 출처=켜짐?null:값;
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
  chips.find(c=>c.dataset.kind==='topic'&&c.dataset.val===b.dataset.val).click();

const more=document.getElementById('more'), box=document.getElementById('srcbox');
if(more) more.onclick=()=>{box.classList.toggle('wrap');
  box.querySelectorAll('.chip').forEach(c=>c.hidden=false);
  more.hidden=true;};
"""


def _색규칙() -> str:
    """분야마다 `--tint` 를 물려 주는 CSS. 분야를 추가해도 여기서 자동으로 따라옵니다."""
    줄 = [f":root,section,li{{--tint:{기본색}}}"]
    for 분야, 색 in 분야색.items():
        s = html.escape(분야, quote=True)
        줄.append(f'li[data-t="{s}"],section[data-t="{s}"],'
                  f'.chip[data-kind="topic"][data-val="{s}"]{{--tint:{색}}}')
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


def _기사(g: dict, 새것: set, 숨김: bool = False) -> str:
    e = html.escape
    뱃지 = '<span class="new">NEW</span>' if g["fp"] in 새것 else ""
    부가 = " · ".join(x for x in (e(g["source"]), _시각표기(g["at"])) if x)
    요약 = f'<div class="sum">{e(g["summary"])}</div>' if g.get("summary") else ""
    # data-k = 검색 대상(제목+출처+요약). 미리 소문자로 만들어 두면 걸러낼 때 빠릅니다.
    열쇠 = e(f"{g['title']} {g['source']} {g.get('summary', '')}".lower())
    # 상한을 넘는 기사는 서버에서 미리 감춥니다. 첫 화면이 240건 그렸다가 줄어들면 눈에 띕니다.
    return (f'<li{" hidden" if 숨김 else ""} '
            f'data-k="{열쇠}" data-t="{e(g["topic"])}" data-s="{e(g["source"])}">'
            f'<a class="t" href="{e(g["url"])}" target="_blank" rel="noopener">'
            f'{뱃지}{e(g["title"])}</a><div class="sub">{부가}</div>{요약}</li>')


def _색인(기사: list[dict]) -> str:
    """출처별 칩. 어떤 매체가 얼마나 실렸는지 한눈에 보고 눌러서 거를 수 있습니다."""
    e = html.escape
    수 = {}
    for g in 기사:
        수[g["source"]] = 수.get(g["source"], 0) + 1
    정렬 = sorted(수.items(), key=lambda kv: (-kv[1], kv[0]))
    if not 정렬:
        return ""
    칩 = []
    for i, (이름, n) in enumerate(정렬):
        숨김 = " hidden" if i >= 색인상한 else ""
        칩.append(f'<button class="chip" data-kind="src" data-val="{e(이름)}" '
                  f'aria-pressed="false"{숨김}>{e(이름)}<span class="n">{n}</span></button>')
    더 = (f'<button id="more">출처 {len(정렬) - 색인상한}개 더 보기</button>'
          if len(정렬) > 색인상한 else "")
    return (f'<div class="idx"><h3>출처 {len(정렬)}곳</h3>'
            f'<div class="chips" id="srcbox">{"".join(칩)}</div>{더}</div>')


def 만들기(기사: list[dict], 새것: set, 실패: list[str], 갱신: dt.datetime) -> str:
    e = html.escape
    묶음 = {분야: [] for 분야 in 분야순서}
    for g in 기사:
        묶음.setdefault(g["topic"], []).append(g)

    신규수 = {분야: sum(1 for g in 묶음.get(분야, []) if g["fp"] in 새것) for 분야 in 분야순서}

    본문 = []
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

    분야칩 = "".join(
        f'<button class="chip" data-kind="topic" data-val="{e(t)}" aria-pressed="false">'
        f'{e(t)}<span class="n">{len(묶음.get(t, []))}</span>'
        + (f'<span class="nn">+{신규수[t]}</span>' if 신규수[t] else "")
        + '</button>' for t in 분야순서)
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
  <div class="top"><h1>뉴스 브리핑</h1>
    <div class="meta"><span id="cnt">{len(기사)}</span>건 · 새 소식 {len(새것)}</div></div>
  <div class="search">
    <input id="q" type="search" placeholder="제목·출처로 검색" autocomplete="off"
           enterkeyhint="search" aria-label="검색">
    <button id="clear" aria-label="지우기">&times;</button>
  </div>
</header>
<div class="chips wrap">{분야칩}</div>
{_색인(기사)}
{''.join(본문)}
<div id="none">검색 결과가 없습니다.</div>
<footer>{갱신.astimezone(KST):%Y-%m-%d %H:%M} 기준 · 1시간마다 자동 갱신 ·
페이지는 {REFRESH // 60}분마다 스스로 새로고침합니다.{주의}</footer>
<script>{_JS.replace("__LIMIT__", str(본문상한))}</script>
</body></html>"""
