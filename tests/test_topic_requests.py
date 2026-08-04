import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app


def fake_response(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestListTopicRequests:
    def test_filters_out_pull_requests(self, monkeypatch):
        issues = [
            {"number": 1, "title": "BTS 최근 인터뷰"},
            {"number": 2, "title": "PR로 착각되는 항목", "pull_request": {}},
        ]
        monkeypatch.setattr(app.SESSION, "get", lambda *a, **k: fake_response(issues))
        result = app.list_topic_requests("fake-token")
        assert len(result) == 1
        assert result[0]["number"] == 1

    def test_empty_list(self, monkeypatch):
        monkeypatch.setattr(app.SESSION, "get", lambda *a, **k: fake_response([]))
        assert app.list_topic_requests("fake-token") == []


class TestResolveTopicRequest:
    def test_posts_comment_then_closes(self, monkeypatch):
        calls = []

        def fake_post(url, **kwargs):
            calls.append(("post", url, kwargs.get("json")))
            return fake_response({})

        def fake_patch(url, **kwargs):
            calls.append(("patch", url, kwargs.get("json")))
            return fake_response({})

        monkeypatch.setattr(app.SESSION, "post", fake_post)
        monkeypatch.setattr(app.SESSION, "patch", fake_patch)

        app.resolve_topic_request("fake-token", 42, "완료했습니다")

        assert calls[0][0] == "post"
        assert calls[0][1].endswith("/issues/42/comments")
        assert calls[0][2] == {"body": "완료했습니다"}
        assert calls[1][0] == "patch"
        assert calls[1][1].endswith("/issues/42")
        assert calls[1][2] == {"state": "closed"}


class TestFilterEligible:
    def test_filters_short_and_non_english(self):
        meta = {
            "a": {"duration_sec": 120, "audio_lang": "en", "channel_id": "c1"},
            "b": {"duration_sec": 10, "audio_lang": "en", "channel_id": "c2"},
            "c": {"duration_sec": 120, "audio_lang": "hi", "channel_id": "c3"},
            "d": {"duration_sec": 120, "audio_lang": "", "channel_id": "c4"},
        }
        result = app._filter_eligible(["a", "b", "c", "d"], meta)
        assert result == ["a", "d"]
