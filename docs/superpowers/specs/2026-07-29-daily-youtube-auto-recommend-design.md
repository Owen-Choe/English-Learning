# 매일 자동 유튜브 학습 페이지 - 설계

## 목표
현재는 유튜브 URL을 손으로 넣어야 학습 페이지가 만들어진다. 이 기능은 매일 정해진 시간에
YouTube Data API로 영상을 자동 검색하고, 자막/슬랭 밀도를 검증한 뒤, 학습 페이지를
자동으로 생성해 날짜별로 쌓는다.

## 아키텍처
`app.py`에 `--daily` 모드를 추가한다. 기존 수동 모드(`python3 app.py <URL>`)는 그대로 둔다.
macOS launchd가 매일 정해진 시각(기본 08:00)에 `--daily`로 스크립트를 깨운다.

```
launchd (매일 08:00)
  -> app.py --daily
       -> YouTube Data API search.list (로테이션 검색어 + 최근 N일 필터)
       -> seen.json에 없는 후보만 순서대로 시도
            -> 자막 추출 실패/슬랭 부족 -> 다음 후보
            -> 성공 -> days/YYYY-MM-DD.html 생성, seen.json에 기록
       -> index.html을 "최근 학습 + 지난 날짜 목록"으로 재생성
```

## 컴포넌트
- **search_daily_candidate()**: YouTube Data API `search.list`를 `requests`로 직접 호출
  (google-api-python-client SDK는 추가하지 않음 — REST 호출 2종류뿐이라 SDK가 과함).
  로테이션 검색어 목록(예: "gen z vlog", "day in my life gen z", "gen z slang") 중
  하나를 날짜 기반으로 순환 선택하고, `publishedAfter`로 최근 N일(기본 30일) 필터.
- **seen.json**: 이미 사용한 video_id 목록. 검색 결과에서 이 목록에 있는 영상은 제외.
- **기존 파이프라인 재사용**: `fetch_transcript`, `call_llm`, `render_html`은 그대로 사용.
  실패 시(자막 없음/`TranscriptsDisabled`/LLM이 슬랭 부족 판단) 다음 후보로 넘어가는
  루프만 새로 추가.
- **날짜별 저장**: `days/YYYY-MM-DD.html`로 저장. `index.html`은 최신 파일로 리다이렉트하거나
  최신 내용 + 지난 날짜 링크 목록을 보여주는 형태로 재구성.
- **launchd plist**: `com.user.daily-english-learning.plist`. venv 활성화 후
  `app.py --daily` 실행, stdout/stderr를 로그 파일로 리다이렉트(터미널이 없는 상태로
  실행되므로 로그가 유일한 디버깅 수단).

## 에러 처리
- 그날 후보를 모두 시도해도 실패하면 로그만 남기고 조용히 종료. 기존 날짜 페이지는
  그대로 유지되고 `index.html`도 바뀌지 않는다.
- YouTube API 쿼터 초과(HTTP 403 quotaExceeded)면 에러 로그 남기고 종료, 다음날 재시도.
- 기존 수동 모드의 에러 처리(자막 비활성/JSON 파싱 실패 재시도)는 변경하지 않는다.

## 새 자격증명
- `YOUTUBE_API_KEY` — Google Cloud Console에서 별도 발급 (Anthropic 키와는 다른 자격증명).
  `.env`에 추가.

## 테스트/검증
- `search_daily_candidate()`가 실제로 seen.json에 있는 video_id를 걸러내는지 확인하는
  간단한 self-check(assert 기반, 프레임워크 없이).
- 후보 전원 실패 시나리오를 강제로 만들어(가짜 video_id 리스트) 조용히 종료되는지 확인.
- launchd plist는 `launchctl load`로 등록 후 수동으로 한 번 `launchctl start`로 트리거해
  로그 파일에 정상 실행 흔적이 남는지 확인.

## 범위 밖 (이번 설계에 포함 안 함)
- 영상 길이/화질 등 세부 필터링 고도화
- 검색어 로테이션의 다양성 튜닝 (일단 고정 목록으로 시작)
- 여러 영상을 하루에 여러 개 만드는 기능 (하루 1개로 시작)
