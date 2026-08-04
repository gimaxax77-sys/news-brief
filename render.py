# 기사 목록을 폰에서 읽기 좋은 정적 HTML 한 장으로 만듭니다 (검색·색인·필터 포함)
import datetime as dt
import html
import json

from sources import 분야순서

REFRESH = 600  # 페이지 자동 새로고침(초). 수집 주기보다 짧게 둘 이유가 없습니다.
KST = dt.timezone(dt.timedelta(hours=9))
색인상한 = 14  # 색인에 칩으로 보여 줄 출처 수. 나머지는 "더 보기"로 폅니다.

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
@media(prefers-color-scheme:dark){.chip{border-color:#fff3}}

.idx{padding:10px 16px 0}
.idx h3{font-size:12.5px;letter-spacing:.06em;opacity:.42;text-transform:uppercase;
 margin-bottom:7px;font-weight:700}
#more{font-size:13px;opacity:.55;background:none;border:0;color:inherit;cursor:pointer;
 padding:6px 2px;text-decoration:underline}

section{padding:24px 16px 0}
section h2{font-size:15px;font-weight:800;letter-spacing:-.01em;opacity:.5;margin-bottom:8px}
ul{list-style:none}
li{padding:13px 0;border-bottom:1px solid #0001}
@media(prefers-color-scheme:dark){li{border-color:#ffffff14}}
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
 items=[...document.querySelectorAll('li[data-k]')],
 chips=[...document.querySelectorAll('.chip')];
let 분야=null, 출처=null;

function 표시(){
  const 말=q.value.trim().toLowerCase();
  clear.style.display=q.value?'block':'none';
  let 보임=0;
  for(const li of items){
    const ok=(!말||li.dataset.k.includes(말))
      &&(!분야||li.dataset.t===분야)&&(!출처||li.dataset.s===출처);
    li.hidden=!ok; if(ok)보임++;
  }
  // 항목이 하나도 안 남은 분야는 제목까지 숨겨 빈 칸이 생기지 않게 합니다.
  for(const s of document.querySelectorAll('section')){
    s.hidden=![...s.querySelectorAll('li[data-k]')].some(li=>!li.hidden);
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
const more=document.getElementById('more'), box=document.getElementById('srcbox');
if(more) more.onclick=()=>{box.classList.toggle('wrap');
  box.querySelectorAll('.chip').forEach(c=>c.hidden=false);
  more.hidden=true;};
"""


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


def _기사(g: dict, 새것: set) -> str:
    e = html.escape
    뱃지 = '<span class="new">NEW</span>' if g["fp"] in 새것 else ""
    부가 = " · ".join(x for x in (e(g["source"]), _시각표기(g["at"])) if x)
    요약 = f'<div class="sum">{e(g["summary"])}</div>' if g.get("summary") else ""
    # data-k = 검색 대상(제목+출처+요약). 미리 소문자로 만들어 두면 걸러낼 때 빠릅니다.
    열쇠 = e(f"{g['title']} {g['source']} {g.get('summary', '')}".lower())
    return (f'<li data-k="{열쇠}" data-t="{e(g["topic"])}" data-s="{e(g["source"])}">'
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

    본문 = []
    for 분야 in 분야순서:
        목록 = 묶음.get(분야, [])
        n = sum(1 for g in 목록 if g["fp"] in 새것)
        머리 = f"{e(분야)} <span style='opacity:.65'>{len(목록)}</span>"
        머리 += f" <span style='color:#c2410c'>+{n}</span>" if n else ""
        속 = ("".join(_기사(g, 새것) for g in 목록) if 목록
              else '<li class="empty">새 소식이 없습니다.</li>')
        본문.append(f'<section><h2>{머리}</h2><ul>{속}</ul></section>')

    분야칩 = "".join(
        f'<button class="chip" data-kind="topic" data-val="{e(t)}" aria-pressed="false">'
        f'{e(t)}<span class="n">{len(묶음.get(t, []))}</span></button>' for t in 분야순서)
    주의 = f"<br>수집 실패: {e(', '.join(실패))}" if 실패 else ""

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}">
<title>뉴스 브리핑</title>
<link rel="stylesheet" href="{_FONT}">
<style>{_CSS}</style></head><body>
<header>
  <div class="top"><h1>뉴스 브리핑</h1>
    <div class="meta"><span id="cnt">{len(기사)}</span>건 · 새 소식 {len(새것)}</div></div>
  <div class="search">
    <input id="q" type="search" placeholder="제목·출처로 검색" autocomplete="off"
           enterkeyhint="search" aria-label="검색">
    <button id="clear" aria-label="지우기">&times;</button>
  </div>
</header>
<div class="chips">{분야칩}</div>
{_색인(기사)}
{''.join(본문)}
<div id="none">검색 결과가 없습니다.</div>
<footer>{갱신.astimezone(KST):%Y-%m-%d %H:%M} 기준 · 1시간마다 자동 갱신 ·
페이지는 {REFRESH // 60}분마다 스스로 새로고침합니다.{주의}</footer>
<script>{_JS}</script>
</body></html>"""
