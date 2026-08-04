import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app


def make_data():
    return {
        "scene_summary": "장면 요약",
        "start_sec": 0,
        "end_sec": 60,
        "script": [{"speaker": "화자", "en": "Hello", "ko": "안녕", "timestamp": 0}],
        "expressions": [{
            "expr": "chef up", "tag": "요리하다",
            "quote_en": "I chef up random things.", "quote_speaker": "화자",
            "context": "설명", "listening_tip": "팁",
            "examples": [{"en": "a", "ko": "가"}, {"en": "b", "ko": "나"}],
            "timestamp": 10,
        }],
    }


class TestRenderHtml:
    def test_embeds_video_id_and_data(self):
        html = app.render_html("vid123", make_data())
        m = re.search(r'<script id="expr-data" type="application/json">([\s\S]*?)</script>', html)
        data = json.loads(m.group(1))
        assert data["video_id"] == "vid123"
        assert data["scene_summary"] == "장면 요약"

    def test_time_labels(self):
        html = app.render_html("vid123", make_data())
        assert "00:00 ~ 01:00" in html

    def test_days_nav_defaults_empty(self):
        html = app.render_html("vid123", make_data())
        assert "{days_nav}" not in html  # 포맷 문자열이 실제로 치환됐는지

    def test_days_nav_injected_when_provided(self):
        html = app.render_html("vid123", make_data(), days_nav='<div class="jump-row">TEST</div>')
        assert '<div class="jump-row">TEST</div>' in html


class TestBuildDaysNav:
    def test_no_days_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app, "DAYS_DIR", str(tmp_path / "does-not-exist"))
        assert app.build_days_nav() == ""

    def test_lists_dates_sorted_desc(self, tmp_path, monkeypatch):
        days_dir = tmp_path / "days"
        days_dir.mkdir()
        (days_dir / "2026-07-29.html").write_text("x")
        (days_dir / "2026-07-31.html").write_text("x")
        (days_dir / "2026-07-30.html").write_text("x")
        monkeypatch.setattr(app, "DAYS_DIR", str(days_dir))
        nav = app.build_days_nav()
        i31, i30, i29 = nav.index("2026-07-31"), nav.index("2026-07-30"), nav.index("2026-07-29")
        assert i31 < i30 < i29


class TestBuildDateNav:
    def _make_days(self, tmp_path, monkeypatch, dates):
        days_dir = tmp_path / "days"
        days_dir.mkdir()
        for d in dates:
            (days_dir / f"{d}.html").write_text("x")
        monkeypatch.setattr(app, "DAYS_DIR", str(days_dir))

    def test_single_day_index_has_no_nav(self, tmp_path, monkeypatch):
        self._make_days(tmp_path, monkeypatch, ["2026-07-29"])
        assert app.build_date_nav(None, is_days_page=False) == ""

    def test_latest_day_next_is_disabled(self, tmp_path, monkeypatch):
        self._make_days(tmp_path, monkeypatch, ["2026-07-29", "2026-07-30", "2026-07-31"])
        nav = app.build_date_nav("2026-07-31", is_days_page=True)
        assert 'disabled" aria-disabled="true">다음 학습' in nav
        assert 'href="2026-07-30.html">← 이전 학습' in nav
        assert 'href="../index.html">전체 학습' in nav

    def test_oldest_day_prev_is_disabled(self, tmp_path, monkeypatch):
        self._make_days(tmp_path, monkeypatch, ["2026-07-29", "2026-07-30", "2026-07-31"])
        nav = app.build_date_nav("2026-07-29", is_days_page=True)
        assert 'disabled" aria-disabled="true">← 이전 학습' in nav
        assert 'href="2026-07-30.html">다음 학습' in nav

    def test_middle_day_has_both_links(self, tmp_path, monkeypatch):
        self._make_days(tmp_path, monkeypatch, ["2026-07-29", "2026-07-30", "2026-07-31"])
        nav = app.build_date_nav("2026-07-30", is_days_page=True)
        assert 'href="2026-07-29.html">← 이전 학습' in nav
        assert 'href="2026-07-31.html">다음 학습' in nav

    def test_index_page_links_into_days_subfolder(self, tmp_path, monkeypatch):
        self._make_days(tmp_path, monkeypatch, ["2026-07-29", "2026-07-30"])
        nav = app.build_date_nav(None, is_days_page=False)
        assert 'href="days/2026-07-29.html">← 이전 학습' in nav
        assert 'href="index.html">전체 학습' in nav
