# 기사 목록을 폰에서 읽기 좋은 정적 HTML 한 장으로 만듭니다
import datetime as dt
import html

from sources import 분야순서

REFRESH = 600  # 페이지 자동 새로고침(초). 수집 주기보다 짧게 둘 이유가 없습니다.
KST = dt.timezone(dt.timedelta(hours=9))

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif;
 background:#faf9f7;color:#1c1a17;padding:0 0 48px}
@media(prefers-color-scheme:dark){body{background:#14130f;color:#e8e4dc}}
header{position:sticky;top:0;z-index:2;padding:14px 18px;border-bottom:1px solid #0002;
 background:#faf9f7ee;backdrop-filter:blur(8px)}
@media(prefers-color-scheme:dark){header{background:#14130fee;border-color:#fff2}}
h1{font-size:17px;letter-spacing:-.02em}
.meta{font-size:12.5px;opacity:.6;margin-top:3px}
nav{display:flex;gap:6px;overflow-x:auto;padding:10px 18px 0;-webkit-overflow-scrolling:touch}
nav a{flex:0 0 auto;font-size:13px;padding:5px 11px;border-radius:99px;text-decoration:none;
 color:inherit;border:1px solid #0002}
@media(prefers-color-scheme:dark){nav a{border-color:#fff3}}
section{padding:22px 18px 0}
h2{font-size:14px;letter-spacing:.02em;opacity:.55;text-transform:uppercase;margin-bottom:10px}
ul{list-style:none}
li{padding:11px 0;border-bottom:1px solid #0001}
@media(prefers-color-scheme:dark){li{border-color:#fff1}}
a.t{color:inherit;text-decoration:none;font-size:15.5px;font-weight:600;line-height:1.42;
 display:block}
a.t:hover{text-decoration:underline}
.sub{font-size:12px;opacity:.55;margin-top:4px}
.new{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;
 background:#c2410c;color:#fff;border-radius:3px;padding:1px 5px;margin-right:6px;
 vertical-align:1.5px}
.sum{font-size:13.5px;opacity:.78;margin-top:5px;line-height:1.5}
.empty{opacity:.45;font-size:13.5px;padding:6px 0}
footer{padding:30px 18px 0;font-size:12px;opacity:.45;line-height:1.7}
"""


def _시각표기(d: dt.datetime | None) -> str:
    if d is None:
        return ""
    d = d.astimezone(KST)
    지금 = dt.datetime.now(KST)
    차 = 지금 - d
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
    return (f'<li><a class="t" href="{e(g["url"])}" target="_blank" rel="noopener">'
            f'{뱃지}{e(g["title"])}</a><div class="sub">{부가}</div>{요약}</li>')


def 만들기(기사: list[dict], 새것: set, 실패: list[str], 갱신: dt.datetime) -> str:
    """분야별로 묶은 한 장짜리 HTML 을 돌려줍니다."""
    e = html.escape
    묶음 = {분야: [] for 분야 in 분야순서}
    for g in 기사:
        묶음.setdefault(g["topic"], []).append(g)

    본문 = []
    for 분야 in 분야순서:
        목록 = 묶음.get(분야, [])
        n = sum(1 for g in 목록 if g["fp"] in 새것)
        머리 = f"{e(분야)} <span style='opacity:.7'>{len(목록)}</span>"
        머리 += f" <span style='color:#c2410c'>+{n}</span>" if n else ""
        속 = ("".join(_기사(g, 새것) for g in 목록) if 목록
              else '<li class="empty">새 소식이 없습니다.</li>')
        본문.append(f'<section id="{e(분야)}"><h2>{머리}</h2><ul>{속}</ul></section>')

    탭 = "".join(f'<a href="#{e(t)}">{e(t)}</a>' for t in 분야순서)
    주의 = (f"<br>수집 실패: {e(', '.join(실패))}" if 실패 else "")
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{REFRESH}">
<title>뉴스 브리핑</title><style>{_CSS}</style></head><body>
<header><h1>뉴스 브리핑</h1>
<div class="meta">{갱신.astimezone(KST):%Y-%m-%d %H:%M} 기준 · 전체 {len(기사)}건 · 새 소식 {len(새것)}건</div>
</header>
<nav>{탭}</nav>
{''.join(본문)}
<footer>1시간마다 자동 갱신됩니다. 페이지는 {REFRESH // 60}분마다 스스로 새로고침합니다.{주의}</footer>
</body></html>"""
