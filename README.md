# English-Learning

유튜브 영상 한 편에서 진짜 원어민이 쓰는 60초 표현을 뽑아, GitHub Pages로 배포하는 정적 영어 학습 페이지 생성기.

## 주요 기능
- 유튜브 자막 → Claude가 45~75초 하이라이트 구간 + 표현 5~10개 추출 (카테고리, 격식 수준, 직장 사용 가능 여부, 문화/유머 맥락, 리스닝 포인트, 예문 포함)
- Pydantic으로 LLM 출력 스키마·범위·중복 검증, 실제 자막과 인용문 대조
- 영상 재생과 동기화되는 스크립트 하이라이트, 표현 타임스탬프 클릭 이동, 재생 속도/구간 반복, 자막 모드(영어만/영한/숨기기)
- 표현 데이터로 만드는 3문제 복습 퀴즈 (localStorage에 완료 상태 저장)
- `--daily` 모드: 즐겨보는 유튜버 채널에서 매일 자동으로 영상을 골라 생성·배포
- 학습 페이지에서 "다음 학습 신청"으로 관심 주제를 남기면(GitHub 이슈) 다음날 그 주제를 우선 검색
- 날짜별 정적 페이지(`days/YYYY-MM-DD.html`) + 이전/전체/다음 내비게이션 + GitHub Pages 배포

## 프로젝트 구조
```
app.py                    # 파이프라인 전체 (CLI, 자막/LLM/렌더/배포)
channels.json             # 후보 영상을 가져올 유튜버 채널 목록 (자유롭게 추가/교체)
requirements.txt          # 고정된 의존성
.env.example              # 필요한 환경 변수 목록
.github/workflows/test.yml  # push/PR마다 pytest 실행
tests/                    # pytest 테스트
days/                     # 날짜별로 쌓이는 학습 페이지 (생성물)
index.html                # 최신 학습 페이지 + 지난 날짜 목록 (생성물)
seen.json                 # 이미 처리한 영상과 그 결과 상태 (생성물)
manifest.json             # 모든 날짜의 메타데이터 목록 (생성물, 홈 화면 고도화용)
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
| `GITHUB_TOKEN` | 배포용 git push + 관심사 이슈 조회/닫기 | github.com/settings/tokens → classic token, `repo` 스코프 |

## 실행

**수동 모드** — 유튜브 URL 하나를 직접 넣어 로컬 브라우저로 확인:
```bash
python3 app.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

**데일리 모드** — 채널 목록(또는 신청된 관심사)에서 자동으로 영상을 골라 생성 + GitHub Pages 배포:
```bash
python3 app.py --daily
```

## 관심 주제 신청 흐름
1. 학습 페이지 하단 "다음 학습 신청"에 주제를 입력하고 제출하면 `topic-request` 라벨이 붙은 GitHub 이슈가 열린다 (GitHub 로그인 필요).
2. 다음 `--daily` 실행 시 열린 이슈가 있으면 그 제목으로 먼저 검색하고, 적합한 영상을 찾으면 이슈에 결과 링크를 남기고 닫는다.
3. 적합한 영상을 못 찾으면 평소 채널 목록으로 자동 대체된다.

## 채널 추가/교체
`channels.json`의 `handle`을 수정하면 된다. `enabled: false`로 임시로 빼둘 수도 있다.

## 테스트
```bash
python3 -m pytest tests/ -v
```
`main` 브랜치에 `app.py`/`tests/`가 바뀐 채로 push되면 GitHub Actions가 자동으로 같은 테스트를 실행한다.

## 배포
`--daily` 모드가 `git add/commit/push`까지 자동으로 수행한다. GitHub Pages는 `main` 브랜치 루트에서 서빙하도록 설정돼 있다.

## 보안 참고
- `.env`, `.venv/`, `.claude/`는 `.gitignore`에 있어 커밋되지 않는다.
- git history에 API 키가 없는지 확인: `git log -p --all | grep -iE "ANTHROPIC_API_KEY=sk-ant|GITHUB_TOKEN=ghp_|YOUTUBE_API_KEY=AIza"` (아무것도 안 나오면 안전)
- 유튜브 자막/LLM 출력은 신뢰할 수 없는 외부 데이터로 취급한다 — 화면에 표시되는 모든 데이터는 `textContent`로만 삽입되고 `innerHTML`은 쓰지 않는다.

## 알려진 제한 (다음 단계)
- 후보 구간을 저비용으로 미리 스코어링한 뒤 상위 후보만 정밀 생성하는 단계는 아직 없음 (매 후보를 그대로 정밀 생성)
- private 파이프라인 저장소 / public 산출물 저장소 분리는 보류 (현재 단일 공개 저장소)
- `app.py` 한 파일에 파이프라인이 모여 있음 — templates/static/모듈 분리는 다음 단계에서 진행 예정
- 복습 스케줄은 정답/오답 2단계로 단순화(스펙의 "애매함" 3단계 SRS는 다음 단계)
