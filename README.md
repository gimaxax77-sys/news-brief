# 뉴스 브리핑

관심 분야 뉴스를 2시간마다 모아 한 장짜리 웹페이지로 띄우고, 그중 핫뉴스를 골라 텔레그램으로 알립니다.
한국시간 **01~08시에는 아무것도 하지 않고**, 그동안 쌓인 것을 **09시에 한 번에** 묶어 알립니다.

**서버가 없습니다.** 윈도우 작업 스케줄러가 `brief.py` 를 부르고, 결과 HTML 을 GitHub Pages 가 서빙합니다.

```
[수집] RSS 23개  →  [정리] 중복 제거·신규 판정  →  [발행] docs/index.html
                                              →  [알림] 텔레그램
```

## 분야

| 분야 | 소스 |
|---|---|
| AI·클로드 | 구글뉴스(한·영) · Claude Code 릴리스 · Hacker News · OpenAI · Google AI |
| 게임개발 | 구글뉴스 · Game Developer · Godot · Unity |
| 유튜브·쇼츠 | YouTube 공식 · YouTube Creators · TubeFilter |
| IT이슈 | 구글뉴스 · ZDNet Korea · 전자신문 · IT동아 · 네이버 D2 · The Verge · Ars Technica · TechCrunch · Hacker News |

## 쓰는 법

```bash
pip install requests python-dotenv
cp .env.example .env    # 키를 채웁니다. 비워 두면 알림·요약만 빠지고 나머지는 돕니다.
python -X utf8 -u brief.py
```

`.env` 항목

| 이름 | 없으면 |
|---|---|
| `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` | 알림을 보내지 않습니다 |
| `ANTHROPIC_API_KEY` | 한줄요약 없이 제목·링크만 나옵니다 |
| `BRIEF_URL` | 알림에 페이지 주소를 넣지 않습니다 |

## 테스트

```bash
python -X utf8 -u test_brief.py
```

망 접속 없이 돕니다.
