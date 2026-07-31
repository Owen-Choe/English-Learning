import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

import app

MALICIOUS_PAYLOADS = [
    "<img src=x onerror=alert(1)>",
    "<script>alert(1)</script>",
    '"><svg onload=alert(1)>',
]


def data_with_payload(payload: str) -> dict:
    return {
        "scene_summary": payload,
        "start_sec": 0,
        "end_sec": 60,
        "script": [{"speaker": payload, "en": payload, "ko": payload, "timestamp": 0}],
        "expressions": [{
            "expr": payload, "tag": payload, "quote_en": payload, "quote_speaker": payload,
            "context": payload, "listening_tip": payload,
            "examples": [{"en": payload, "ko": payload}, {"en": payload, "ko": payload}],
            "timestamp": 0,
        }],
    }


class TestNoRawPayloadOutsideJsonBlob:
    """LLM/자막에서 온 값에 악성 HTML이 섞여도, JSON 데이터 블록 밖의 정적 마크업/스크립트
    소스에는 원문 그대로 노출되면 안 된다(JSON 안에만 문자열로 존재하는 건 안전 — JS가
    textContent로만 꺼내 쓰기 때문)."""

    def test_payload_confined_to_json_blob(self):
        for payload in MALICIOUS_PAYLOADS:
            html = app.render_html("vid123", data_with_payload(payload))
            before_blob, _, after_blob = html.partition('<script id="expr-data"')
            _, _, rest = after_blob.partition("</script>")
            assert payload not in before_blob, f"payload leaked before JSON blob: {payload}"
            assert payload not in rest, f"payload leaked after JSON blob: {payload}"

    def test_script_tag_close_is_escaped_in_json_blob(self):
        html = app.render_html("vid123", data_with_payload("</script><script>alert(1)</script>"))
        # 원본 "</script>" 시퀀스가 이스케이프 없이 그대로 나오면 안 됨(JSON 블록을 조기 종료시킴)
        blob_start = html.index('<script id="expr-data"')
        blob_region = html[blob_start:blob_start + 2000]
        assert "</script><script>alert(1)" not in blob_region


class TestJsUsesTextContentNotInnerHtml:
    """데이터 삽입 지점이 innerHTML이 아니라 el()/textContent 기반인지 소스 수준에서 확인."""

    def test_no_innerhtml_assignment_with_template_literal_of_data(self):
        js = re.search(r'<script>\s*// 보안 참고([\s\S]*?)</script>', app.HTML_TEMPLATE)
        assert js, "메인 스크립트 블록을 찾지 못함"
        # e.expr/e.context 등 데이터 필드가 innerHTML 대입에 직접 쓰이면 안 됨
        assert ".innerHTML = `" not in js.group(1)
        assert ".innerHTML=`" not in js.group(1)
