@echo off
REM Hourly news brief: collect -> render -> publish to GitHub Pages.
REM Called by Windows Task Scheduler. Keep this file CRLF + ASCII only:
REM   LF breaks cmd parsing, and Korean text here corrupts the shared log.
cd /d "D:\.CODE\AXdata\axdata_15_news_brief"
set PYTHONIOENCODING=utf-8
set LOG=D:\.CODE\AXdata\axdata_15_news_brief\brief_log.txt
set PY=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe

"%PY%" -X utf8 -u brief.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [%date% %time%] collect failed, not publishing >> "%LOG%"
  exit /b 1
)

REM Commit only when the page actually changed, to avoid empty commits.
git diff --quiet -- docs/index.html
if errorlevel 1 (
  git add docs/index.html >> "%LOG%" 2>&1
  git commit -q -m "chore: refresh news brief" >> "%LOG%" 2>&1
  git push -q origin main >> "%LOG%" 2>&1
  echo [%date% %time%] published >> "%LOG%"
) else (
  echo [%date% %time%] no change, skipped publish >> "%LOG%"
)
