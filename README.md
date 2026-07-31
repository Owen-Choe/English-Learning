# English-Learning

유튜브 영상 한 편에서 진짜 원어민이 쓰는 60초 표현을 뽑아, GitHub Pages로 배포하는 정적 영어 학습 페이지 생성기.

## 주요 기능
- 유튜브 자막 → Claude가 45~75초 하이라이트 구간 + 표현 5~10개 추출 (문화/유머 맥락, 리스닝 포인트, 예문 포함)
- Pydantic으로 LLM 출력 스키마·범위·중복 검증, 실제 자막과 인용문 대조
- 영상 재생과 동기화되는 스크립트 하이라이트, 표현 타임스탬프 클릭 이동
- `--daily` 모드: Gen Z가 즐겨보는 미국 유튜버 채널에서 매일 자동으로 영상을 골라 생성·배포
- 날짜별 정적 페이지(`days/YYYY-MM-DD.html`) + GitHub Pages 배포

## 프로젝트 구조
```
app.py              # 파이프라인 전체 (CLI, 자막/LLM/렌더/배포)
requirements.txt    # 고정된 의존성
.env.example        # 필요한 환경 변수 목록
tests/              # pytest 테스트
days/               # 날짜별로 쌓이는 학습 페이지 (생성물)
index.html          # 최신 학습 페이지 + 지난 날짜 목록 (생성물)
seen.json           # 이미 처리한 영상과 그 결과 상태 (생성물)
```

## 설치
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 아래 값을 채워 넣는다
```

### 필요한 환경 변수 (`.env`)
| 변수 | 용도 | 발급처 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 학습 자료 생성 | console.anthropic.com → API Keys |
| `YOUTUBE_API_KEY` | 채널/영상 검색 | console.cloud.google.com → YouTube Data API v3 사용 설정 후 API 키 생성 |
| `GITHUB_TOKEN` | 배포용 git push | github.com/settings/tokens → classic token, `repo` 스코프 |

## 실행

**수동 모드** — 유튜브 URL 하나를 직접 넣어 로컬 브라우저로 확인:
```bash
python3 app.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

**데일리 모드** — 채널 목록에서 자동으로 영상을 골라 생성 + GitHub Pages 배포:
```bash
python3 app.py --daily
```

## 테스트
```bash
python3 -m pytest tests/ -v
```

## 배포
`--daily` 모드가 `git add/commit/push`까지 자동으로 수행한다. GitHub Pages는 `main` 브랜치 루트에서 서빙하도록 설정돼 있다.

## 보안 참고
- `.env`, `.venv/`, `.claude/`는 `.gitignore`에 있어 커밋되지 않는다.
- git history에 API 키가 없는지 확인: `git log -p --all | grep -iE "ANTHROPIC_API_KEY=sk-ant|GITHUB_TOKEN=ghp_|YOUTUBE_API_KEY=AIza"` (아무것도 안 나오면 안전)
- 유튜브 자막/LLM 출력은 신뢰할 수 없는 외부 데이터로 취급한다 — 화면에 표시되는 모든 데이터는 `textContent`로만 삽입되고 `innerHTML`은 쓰지 않는다.

## 알려진 제한 (다음 단계)
- 표현 카테고리 분류, 퀴즈/복습, 재생 속도·구간 반복 등은 아직 없음
- 모바일에서 영상 sticky 해제 등 세부 UX 개편은 이후 단계
- `app.py` 한 파일에 파이프라인이 모여 있음 — 모듈 분리는 다음 단계에서 진행 예정
