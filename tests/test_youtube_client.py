import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import app


class TestGetVideoId:
    def test_watch_url(self):
        assert app.get_video_id("https://www.youtube.com/watch?v=aGE5mK0n0LE") == "aGE5mK0n0LE"

    def test_short_url(self):
        assert app.get_video_id("https://youtu.be/aGE5mK0n0LE") == "aGE5mK0n0LE"

    def test_invalid_url_exits(self):
        with pytest.raises(SystemExit):
            app.get_video_id("https://example.com/not-a-video")


class TestParseIso8601Duration:
    @pytest.mark.parametrize(
        "duration,expected",
        [
            ("PT15S", 15),
            ("PT1M30S", 90),
            ("PT2H", 7200),
            ("PT4M", 240),
            ("P0D", 0),  # 라이브 방송 등 비표준 포맷
            ("", 0),
        ],
    )
    def test_parses(self, duration, expected):
        assert app.parse_iso8601_duration(duration) == expected


class TestChunked:
    def test_splits_into_batches_of_size(self):
        batches = list(app.chunked(list(range(120)), 50))
        assert [len(b) for b in batches] == [50, 50, 20]

    def test_empty_input(self):
        assert list(app.chunked([], 50)) == []


class TestSeenStorage:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app, "SEEN_PATH", str(tmp_path / "seen.json"))
        seen = {}
        app.mark_seen(seen, "abc123", "processed")
        loaded = app.load_seen()
        assert loaded["abc123"]["status"] == "processed"
        assert "last_attempted_at" in loaded["abc123"]

    def test_migrates_legacy_list_schema(self, tmp_path, monkeypatch):
        seen_path = tmp_path / "seen.json"
        seen_path.write_text('["old1", "old2"]')
        monkeypatch.setattr(app, "SEEN_PATH", str(seen_path))
        loaded = app.load_seen()
        assert set(loaded) == {"old1", "old2"}
        assert loaded["old1"]["status"] == "processed"

    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app, "SEEN_PATH", str(tmp_path / "does-not-exist.json"))
        assert app.load_seen() == {}


class TestTodayKst:
    def test_returns_a_date(self):
        assert isinstance(app.today_kst(), __import__("datetime").date)
