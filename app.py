"""
유튜브 URL 하나 -> 자막 추출 -> LLM으로 Gen Z 슬랭 5~10개 + 60초 하이라이트 구간 추출
-> index.html 렌더 -> 브라우저로 열기.

사용법: python3 app.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"
"""
import functools
import json
import os
import re
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

load_dotenv()

MODEL = "claude-sonnet-5"
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def get_video_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
    if not match:
        sys.exit(f"[에러] 유효한 유튜브 URL이 아닙니다: {url}")
    return match.group(1)


def fetch_transcript(video_id: str):
    api = YouTubeTranscriptApi()
    try:
        return api.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except NoTranscriptFound:
        pass
    except TranscriptsDisabled:
        sys.exit(
            "[에러] 이 영상은 자막이 비활성화되어 있습니다. "
            "자막이 있는 다른 유튜브 URL을 넣어주세요."
        )
    # 영어 자막이 없으면 사용 가능한 첫 번째 자막으로 폴백
    try:
        transcripts = api.list(video_id)
        first = next(iter(transcripts))
        return first.fetch()
    except (NoTranscriptFound, TranscriptsDisabled, StopIteration):
        sys.exit(
            "[에러] 이 영상에서 자막을 찾을 수 없습니다. "
            "자막이 있는 다른 유튜브 URL을 넣어주세요."
        )


def transcript_to_text(transcript) -> str:
    return "\n".join(f"[{int(s.start)}] {s.text}" for s in transcript)


PROMPT_TEMPLATE = """당신은 유튜브 영상 자막에서 Gen Z 슬랭/일상 표현을 찾아 한국인 영어 학습자를 위한 학습 자료를 만드는 전문가입니다.
아래 스키마는 실제 서비스 중인 영어 학습 앱(Speakable)의 "스토리 → 스크립트 → 표현" 구성을 참고한 것입니다.

아래는 영상 자막입니다. 형식은 "[초] 텍스트" 입니다.

할 일:
1. Gen Z 슬랭/일상 표현이 가장 밀집된 약 60초 구간(start_sec, end_sec, 둘의 차이는 45~75초 사이)을 하나 고른다.
2. 그 구간의 장면을 한국어 2~3문장으로 요약한다(scene_summary).
3. 그 구간의 대화를 화자별로 나눠 script 배열로 만든다. 화자를 구분할 수 없으면 "화자"로 표기한다. 각 줄은
   en(영어 원문), ko(한국어 번역), timestamp(그 줄이 시작되는 시각, 초 단위 정수)를 포함한다.
4. 그 구간 "안에서" 한국인 학습자에게 유용한 표현 5~10개를 뽑는다. 각 표현마다:
   - expr: 표현 원문
   - tag: 짧은 한국어 뜻 + 격식 수준 (예: "닥쳐, 입 다물어 (직접적인 구어 표현)")
   - quote_en: 그 표현이 나오는 실제 문장
   - quote_speaker: 그 문장을 말한 화자(구분 불가하면 "화자")
   - context: 문화적 배경, 유머 포인트, 어떤 상황에서 왜 쓰는지에 대한 한국어 설명 (3~5문장)
   - listening_tip: 발음/리스닝 포인트 - 실제 발음이 어떻게 들리는지, 강세나 축약 등 (한국어, 1~2문장)
   - examples: 그 표현을 쓴 다른 예문 2개, 각각 en(영어)과 ko(한국어 번역)
   - timestamp: 그 표현이 등장하는 시각(초, 정수)

중요한 규칙:
- 모든 표현의 timestamp는 반드시 start_sec 이상 end_sec 이하여야 한다. 구간 밖의 표현은 절대 포함하지 않는다.
- script 배열은 start_sec~end_sec 구간의 대화만 담고, 각 줄의 timestamp는 실제 등장 순서대로
  이전 줄보다 크거나 같아야 한다(단조 증가).
- 아래 스키마와 정확히 일치하는 JSON만 반환한다. 코드블록, 설명, 다른 텍스트를 절대 덧붙이지 않는다.

{{"scene_summary": "", "start_sec": 0, "end_sec": 0,
"script": [{{"speaker": "", "en": "", "ko": "", "timestamp": 0}}],
"expressions": [{{"expr": "", "tag": "", "quote_en": "", "quote_speaker": "", "context": "", "listening_tip": "", "examples": [{{"en": "", "ko": ""}}], "timestamp": 0}}]}}

자막:
{transcript}
"""


def extract_json(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return fence.group(1).strip() if fence else text.strip()


def call_llm(client, transcript_text: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(transcript=transcript_text)
    messages = [{"role": "user", "content": prompt}]

    for attempt in range(2):
        resp = client.messages.create(
            model=MODEL, max_tokens=8000, messages=messages
        )
        raw = next(b.text for b in resp.content if b.type == "text")
        try:
            data = json.loads(extract_json(raw))
            break
        except json.JSONDecodeError:
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": "이전 응답은 유효한 JSON이 아니었습니다. "
                        "설명이나 코드블록 없이 JSON만 다시 반환해줘.",
                    }
                )
                continue
            sys.exit("[에러] LLM이 유효한 JSON을 반환하지 못했습니다. 다시 시도해주세요.")

    start_sec, end_sec = data["start_sec"], data["end_sec"]
    for e in data["expressions"]:
        e["timestamp"] = max(start_sec, min(end_sec, int(e["timestamp"])))

    prev = start_sec
    for line in data["script"]:
        ts = max(start_sec, min(end_sec, int(line["timestamp"])))
        line["timestamp"] = prev = max(ts, prev)
    return data


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>오늘의 학습 (Daily)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
  :root {{
    color-scheme: dark;
    --violet: #7C5CFC; --amber: #F5A623; --teal: #2DD4C6; --green: #34D399;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 20px 80px;
    background: #0f0f14; color: #f2f2f5;
    font-family: -apple-system, "Apple SD Gothic Neo", "Segoe UI", sans-serif;
  }}
  .display {{ font-family: "Space Grotesk", -apple-system, "Apple SD Gothic Neo", sans-serif; }}
  .wrap {{ max-width: 860px; margin: 0 auto; }}
  .sticky-col {{
    position: sticky; top: 0; z-index: 10;
    background: #0f0f14; padding: 10px 0; margin: 0 0 -10px;
  }}
  h1 {{ font-size: 28px; margin: 0 0 4px; }}
  .sub {{ color: #9a9aa5; margin: 0 0 28px; font-size: 15px; }}
  .player-box {{
    position: relative; width: 100%; aspect-ratio: 16/9;
    border-radius: 16px; overflow: hidden; background: #000;
    box-shadow: 0 8px 30px rgba(0,0,0,.4);
  }}
  #player {{ width: 100%; height: 100%; }}
  .hint {{ text-align: center; color: #6f6f7a; font-size: 13px; margin: 10px 0 32px; }}
  .badge {{ font-size: 12px; color: var(--violet); font-weight: 700;
           letter-spacing: .04em; margin-bottom: 10px; }}
  .section-title {{ display: flex; align-items: center; gap: 8px; font-weight: 700;
                    font-size: 18px; margin: 40px 0 14px; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
  .dot-violet {{ background: var(--violet); }}
  .dot-amber {{ background: var(--amber); }}
  .dot-teal {{ background: var(--teal); }}
  .dot-green {{ background: var(--green); }}
  .scene-box {{
    background: #1a1a22; border: 1px solid #2b2b36; border-radius: 14px;
    padding: 18px 22px; color: #d7d7de; font-size: 15px; line-height: 1.6;
  }}
  .script-box {{
    background: #1a1a22; border: 1px solid #2b2b36; border-radius: 14px;
    padding: 6px 22px;
  }}
  .script-line {{
    padding: 14px 12px; margin: 0 -12px; border-bottom: 1px solid #24242e;
    border-radius: 8px; border-left: 3px solid transparent;
  }}
  .script-line:last-child {{ border-bottom: none; }}
  .script-line.active {{ background: #7c5cfc1a; border-left-color: var(--violet); }}
  .speaker {{ font-size: 12px; font-weight: 700; color: var(--violet); letter-spacing: .04em; }}
  .script-en {{ font-size: 16px; color: #fff; margin: 4px 0 2px; }}
  .script-ko {{ font-size: 13px; color: #8f8f9a; }}

  .jump-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }}
  .jump-chip {{
    font-size: 13px; color: #d7d7de; background: #1a1a22; border: 1px solid #2b2b36;
    border-radius: 999px; padding: 6px 14px; text-decoration: none; white-space: nowrap;
    transition: border-color .15s, color .15s;
  }}
  .jump-chip:hover {{ border-color: var(--violet); color: #fff; }}

  .card {{
    display: block; background: #1a1a22; border: 1px solid #2b2b36; border-radius: 14px;
    padding: 0; margin-bottom: 14px; transition: border-color .15s;
  }}
  .card:hover {{ border-color: var(--violet); }}
  .card-top {{
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 20px 22px; cursor: pointer; list-style: none;
  }}
  .card-top::-webkit-details-marker {{ display: none; }}
  .card-top-main {{ display: flex; align-items: center; gap: 10px; min-width: 0; }}
  .chevron {{ color: #6f6f7a; transition: transform .2s; flex-shrink: 0; }}
  details[open] > .card-top .chevron {{ transform: rotate(180deg); }}
  .expr {{ font-size: 22px; font-weight: 700; color: #fff; }}
  .tag {{ font-size: 14px; color: #9a9aa5; margin-top: 4px; }}
  .ts {{
    font-size: 12px; font-weight: 700; color: var(--violet); background: #7c5cfc1a;
    padding: 5px 11px; border-radius: 999px; white-space: nowrap; border: none;
    cursor: pointer; font-family: inherit;
  }}
  .ts:hover {{ background: #7c5cfc33; }}
  .card-body {{ padding: 0 22px 22px; }}
  .subbox {{
    background: #14141a; border-radius: 10px; padding: 12px 16px; margin-top: 14px;
    border-left: 3px solid transparent;
  }}
  .subbox-quote {{ border-left-color: var(--violet); }}
  .subbox-context {{ border-left-color: var(--amber); }}
  .subbox-tip {{ border-left-color: var(--teal); }}
  .subbox-example {{ border-left-color: var(--green); }}
  .subbox-label {{ font-size: 11px; font-weight: 700; letter-spacing: .04em;
                   text-transform: uppercase; margin-bottom: 6px; }}
  .subbox-quote .subbox-label {{ color: var(--violet); }}
  .subbox-context .subbox-label {{ color: var(--amber); }}
  .subbox-tip .subbox-label {{ color: var(--teal); }}
  .subbox-example .subbox-label {{ color: var(--green); }}
  .quote {{ font-style: italic; color: #fff; font-size: 15px; }}
  .quote-speaker {{ color: #6f6f7a; font-size: 12px; margin-top: 4px; }}
  .context, .tip {{ color: #c3c3cc; font-size: 14px; line-height: 1.6; }}
  .example {{ margin-top: 8px; }}
  .example .en {{ color: #fff; font-size: 14px; }}
  .example .ko {{ color: #8f8f9a; font-size: 13px; }}

  a:focus-visible, button:focus-visible, summary:focus-visible {{
    outline: 2px solid var(--violet); outline-offset: 2px;
  }}
  @media (prefers-reduced-motion: reduce) {{
    * {{ transition: none !important; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="badge display">TODAY'S LEARNING · DAILY</div>
  <h1 class="display">오늘의 Gen Z 표현</h1>
  <p class="sub">{start_label} ~ {end_label} 구간에서 뽑은 표현 {count}개</p>

  <div class="sticky-col">
    <div class="player-box"><div id="player"></div></div>
  </div>
  <p class="hint">타임스탬프를 클릭하면 그 표현이 나오는 순간으로 이동합니다. 자동재생이 차단되면 영상을 한 번 클릭해주세요.</p>

  <div class="section-title"><span class="dot dot-violet"></span>오늘의 장면</div>
  <div class="scene-box" id="scene"></div>

  <div class="section-title"><span class="dot dot-teal"></span>스크립트</div>
  <div class="script-box" id="script"></div>

  <div class="section-title"><span class="dot dot-green"></span>오늘의 표현</div>
  <div class="jump-row" id="jump-row"></div>
  <div id="cards"></div>
</div>

<script id="expr-data" type="application/json">{data_json}</script>
<script>
  const data = JSON.parse(document.getElementById('expr-data').textContent);
  const cardsEl = document.getElementById('cards');
  const jumpEl = document.getElementById('jump-row');
  let player;

  document.getElementById('scene').textContent = data.scene_summary;

  const scriptEl = document.getElementById('script');
  const scriptLines = [];
  data.script.forEach((line) => {{
    const row = document.createElement('div');
    row.className = 'script-line';
    row.innerHTML = `
      <div class="speaker">${{line.speaker}}</div>
      <div class="script-en">${{line.en}}</div>
      <div class="script-ko">${{line.ko}}</div>
    `;
    scriptEl.appendChild(row);
    scriptLines.push({{ ts: line.timestamp, el: row }});
  }});

  // ponytail: naive 400ms poll, switch to rAF+state gating if this were a battery-sensitive app
  let activeLine = null;
  setInterval(() => {{
    if (!player || !player.getCurrentTime) return;
    const t = player.getCurrentTime();
    let current = scriptLines[0];
    for (const line of scriptLines) {{
      if (line.ts <= t) current = line; else break;
    }}
    if (current && current.el !== activeLine) {{
      if (activeLine) activeLine.classList.remove('active');
      current.el.classList.add('active');
      activeLine = current.el;
    }}
  }}, 400);

  function fmtTs(sec) {{
    return `${{String(Math.floor(sec/60)).padStart(2,'0')}}:${{String(sec%60).padStart(2,'0')}}`;
  }}

  function seek(ts) {{
    if (player && player.seekTo) {{
      player.seekTo(ts, true);
      player.playVideo();
    }}
  }}

  data.expressions.forEach((e, i) => {{
    const chip = document.createElement('a');
    chip.className = 'jump-chip display';
    chip.href = `#expr-${{i}}`;
    chip.textContent = e.expr;
    jumpEl.appendChild(chip);

    const examplesHtml = e.examples.map(ex => `
      <div class="example">
        <div class="en">${{ex.en}}</div>
        <div class="ko">${{ex.ko}}</div>
      </div>
    `).join('');

    const details = document.createElement('details');
    details.className = 'card';
    details.id = `expr-${{i}}`;
    if (i === 0) details.open = true;
    details.innerHTML = `
      <summary class="card-top">
        <div class="card-top-main">
          <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          <div>
            <div class="expr display">${{e.expr}}</div>
            <div class="tag">${{e.tag}}</div>
          </div>
        </div>
        <button class="ts" type="button">${{fmtTs(e.timestamp)}}</button>
      </summary>
      <div class="card-body">
        <div class="subbox subbox-quote">
          <div class="subbox-label">드라마 속 문장</div>
          <div class="quote">"${{e.quote_en}}"</div>
          <div class="quote-speaker">— ${{e.quote_speaker}}</div>
        </div>
        <div class="subbox subbox-context">
          <div class="subbox-label">문화 / 유머 포인트</div>
          <div class="context">${{e.context}}</div>
        </div>
        <div class="subbox subbox-tip">
          <div class="subbox-label">리스닝 포인트</div>
          <div class="tip">${{e.listening_tip}}</div>
        </div>
        <div class="subbox subbox-example">
          <div class="subbox-label">예문</div>
          ${{examplesHtml}}
        </div>
      </div>
    `;
    details.querySelector('.ts').addEventListener('click', (ev) => {{
      ev.preventDefault();
      ev.stopPropagation();
      seek(e.timestamp);
    }});
    cardsEl.appendChild(details);
  }});

  const tag = document.createElement('script');
  tag.src = 'https://www.youtube.com/iframe_api';
  document.body.appendChild(tag);

  window.onYouTubeIframeAPIReady = function() {{
    player = new YT.Player('player', {{
      videoId: data.video_id,
      playerVars: {{ start: data.start_sec, end: data.end_sec, autoplay: 1, rel: 0 }},
      events: {{
        onReady: (ev) => ev.target.playVideo()
      }}
    }});
  }};
</script>
</body>
</html>
"""


def fmt_time(sec: int) -> str:
    return f"{sec // 60:02d}:{sec % 60:02d}"


def render_html(video_id: str, data: dict) -> str:
    data["video_id"] = video_id
    data_json = json.dumps(data, ensure_ascii=False).replace("</script", "<\\/script")
    return HTML_TEMPLATE.format(
        start_label=fmt_time(data["start_sec"]),
        end_label=fmt_time(data["end_sec"]),
        count=len(data["expressions"]),
        data_json=data_json,
    )


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else input("유튜브 URL을 입력하세요: ").strip()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("[에러] .env 파일에 ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")

    import anthropic

    video_id = get_video_id(url)
    print(f"[1/3] 자막 추출 중... (video_id={video_id})")
    transcript = fetch_transcript(video_id)
    transcript_text = transcript_to_text(transcript)

    print("[2/3] LLM으로 표현/하이라이트 구간 추출 중...")
    client = anthropic.Anthropic(api_key=api_key)
    data = call_llm(client, transcript_text)

    print("[3/3] index.html 생성 중...")
    html = render_html(video_id, data)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    # file://로 열면 유튜브 IFrame API가 origin 오류(153)를 내므로 로컬 서버로 서빙한다
    handler = functools.partial(SimpleHTTPRequestHandler, directory=os.path.dirname(OUTPUT_HTML))
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    webbrowser.open(f"http://127.0.0.1:{port}/index.html")
    print(f"완료! http://127.0.0.1:{port}/index.html 를 브라우저에서 열었습니다. (종료: Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
