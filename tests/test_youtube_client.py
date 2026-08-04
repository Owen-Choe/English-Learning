import json
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


class TestLoadChannels:
    def test_filters_disabled_channels(self, tmp_path, monkeypatch):
        channels_path = tmp_path / "channels.json"
        channels_path.write_text(
            '[{"handle": "A", "enabled": true}, {"handle": "B", "enabled": false}, '
            '{"handle": "C"}]'
        )
        monkeypatch.setattr(app, "CHANNELS_PATH", str(channels_path))
        assert app.load_channels() == ["A", "C"]  # enabled 기본값은 true


class TestUpdateManifest:
    def test_creates_and_appends_entries(self, tmp_path, monkeypatch):
        manifest_path = tmp_path / "manifest.json"
        monkeypatch.setattr(app, "MANIFEST_PATH", str(manifest_path))

        data1 = {"video_title": "t1", "channel_name": "c1",
                 "expressions": [{"expr": "e1", "category": "slang"}]}
        data2 = {"video_title": "t2", "channel_name": "c2",
                 "expressions": [{"expr": "e2", "category": "workplace"}]}

        app.update_manifest("2026-07-29", "vid1", data1)
        app.update_manifest("2026-07-30", "vid2", data2)

        manifest = json.loads(manifest_path.read_text())
        assert [m["date"] for m in manifest] == ["2026-07-29", "2026-07-30"]
        assert manifest[0]["video_title"] == "t1"
        assert manifest[0]["categories"] == ["slang"]

    def test_replaces_same_date_entry(self, tmp_path, monkeypatch):
        manifest_path = tmp_path / "manifest.json"
        monkeypatch.setattr(app, "MANIFEST_PATH", str(manifest_path))

        data_v1 = {"video_title": "old", "channel_name": "c",
                   "expressions": [{"expr": "e1", "category": "slang"}]}
        data_v2 = {"video_title": "new", "channel_name": "c",
                   "expressions": [{"expr": "e1", "category": "slang"}]}

        app.update_manifest("2026-07-29", "vid-old", data_v1)
        app.update_manifest("2026-07-29", "vid-new", data_v2)

        manifest = json.loads(manifest_path.read_text())
        assert len(manifest) == 1
        assert manifest[0]["video_title"] == "new"
        assert manifest[0]["video_id"] == "vid-new"
