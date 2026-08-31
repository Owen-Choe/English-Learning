import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from pydantic import ValidationError

import app


def make_expression(**overrides):
    base = {
        "expr": "chef up",
        "category": "casual_phrase",
        "formality": "casual",
        "workplace_safe": True,
        "tag": "요리하다 (캐주얼 표현)",
        "quote_en": "I sometimes chef up random things in my kitchen.",
        "quote_speaker": "화자",
        "context": "요리라고 하기엔 애매하지만 뭔가 만들어 먹는다는 뜻으로 쓰는 캐주얼한 표현이다.",
        "listening_tip": "chef가 동사처럼 쓰여서 명사 뒤에 up이 자연스럽게 붙는다.",
        "examples": [
            {"en": "I chef'd up a quick pasta.", "ko": "빠르게 파스타를 만들었어."},
            {"en": "She chefs up something new every week.", "ko": "그녀는 매주 새로운 걸 만들어."},
        ],
        "timestamp": 130,
    }
    base.update(overrides)
    return base


def make_lesson(expressions=None, script=None, **overrides):
    if script is None:
        script = [
            {"speaker": "화자", "en": "I sometimes chef up random things in my kitchen.",
             "ko": "가끔 부엌에서 이것저것 만들어 먹어.", "timestamp": 100},
        ]
    if expressions is None:
        expressions = [
            make_expression(expr=f"expr{i}", timestamp=t)
            for i, t in enumerate((105, 110, 115, 120, 125))
        ]
    base = {
        "scene_summary": "화자가 부엌에서 요리하는 이야기를 한다.",
        "start_sec": 100,
        "end_sec": 160,
        "script": script,
        "expressions": expressions,
    }
    base.update(overrides)
    return base


class TestLessonModelValid:
    def test_valid_lesson_passes(self):
        lesson = app.LessonModel.model_validate(make_lesson())
        assert len(lesson.expressions) == 5


class TestLessonModelWindow:
    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(start_sec=100, end_sec=100))

    def test_window_too_short_rejected(self):
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(start_sec=100, end_sec=120))  # 20초

    def test_window_too_long_rejected(self):
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(start_sec=100, end_sec=300))  # 200초


class TestLessonModelExpressionCount:
    def test_too_few_expressions_rejected(self):
        exprs = [make_expression(expr=f"e{i}", timestamp=105 + i) for i in range(3)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_too_many_expressions_rejected(self):
        exprs = [make_expression(expr=f"e{i}", timestamp=100 + i) for i in range(11)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))


class TestLessonModelTimestampBounds:
    def test_expression_timestamp_out_of_range_rejected(self):
        exprs = [make_expression(timestamp=999) for _ in range(5)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_script_timestamp_out_of_range_rejected(self):
        script = [{"speaker": "화자", "en": "hi", "ko": "안녕", "timestamp": 999}]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(script=script))

    def test_script_non_monotonic_rejected(self):
        script = [
            {"speaker": "화자", "en": "a", "ko": "가", "timestamp": 120},
            {"speaker": "화자", "en": "b", "ko": "나", "timestamp": 110},
        ]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(script=script))

    def test_empty_script_rejected(self):
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(script=[]))


class TestLessonModelDuplicatesAndFields:
    def test_duplicate_expressions_rejected(self):
        exprs = [make_expression(timestamp=105 + i) for i in range(5)]  # 전부 "chef up" 동일 expr
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_blank_field_rejected(self):
        exprs = [make_expression(expr=f"e{i}", tag="  ", timestamp=105 + i) for i in range(5)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_wrong_example_count_rejected(self):
        exprs = [make_expression(expr=f"e{i}", timestamp=105 + i, examples=[{"en": "a", "ko": "b"}])
                  for i in range(5)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_unexpected_extra_field_rejected(self):
        data = make_lesson()
        data["unexpected_field"] = "surprise"
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(data)


class TestExpressionCategoryAndRegister:
    def test_valid_category_and_register_pass(self):
        exprs = [make_expression(expr=f"e{i}", category="workplace", formality="formal",
                                  workplace_safe=True, timestamp=105 + i) for i in range(5)]
        lesson = app.LessonModel.model_validate(make_lesson(expressions=exprs))
        assert all(e.category == "workplace" for e in lesson.expressions)

    def test_invalid_category_rejected(self):
        exprs = [make_expression(expr=f"e{i}", category="not_a_real_category", timestamp=105 + i)
                  for i in range(5)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))

    def test_invalid_register_rejected(self):
        exprs = [make_expression(expr=f"e{i}", formality="super-casual", timestamp=105 + i)
                  for i in range(5)]
        with pytest.raises(ValidationError):
            app.LessonModel.model_validate(make_lesson(expressions=exprs))


class TestQuoteVerification:
    def test_quote_found_in_transcript_passes(self):
        lesson = app.LessonModel.model_validate(make_lesson())
        transcript = "Yeah I sometimes chef up random things in my kitchen, it's fun."
        app.verify_quotes_against_transcript(lesson, transcript)  # 예외 없이 통과해야 함

    def test_quote_not_in_transcript_rejected(self):
        exprs = [make_expression(quote_en="This sentence was never said.", timestamp=105 + i)
                  for i in range(5)]
        # 각기 다른 expr이어야 중복 표현으로 먼저 걸리지 않음
        for i, e in enumerate(exprs):
            e["expr"] = f"expr{i}"
        lesson = app.LessonModel.model_validate(make_lesson(expressions=exprs))
        with pytest.raises(app.PipelineError):
            app.verify_quotes_against_transcript(lesson, "completely unrelated transcript text")


class TestQuoteMatching:
    """자동 자막에는 말더듬/filler가 그대로 들어있고 LLM은 그걸 정리해서 인용한다.
    정리된 인용은 통과시키되, 지어낸 문장은 계속 막아야 한다."""

    # 실제 자동 자막에서 가져온 말더듬 패턴
    TRANSCRIPT = (
        "first of all you should be focusing you should know who who your who your client is "
        "and who you want your client to be more than anything "
        "you ll be like since it s music on the come up you ll be like it s cool but you missed"
    )

    def words(self):
        return app._normalize_for_match(self.TRANSCRIPT).split()

    @pytest.mark.parametrize("quote", [
        "you should be focusing",
        "You should know who your client is and who you want your client to be",  # 말더듬 제거
        'since it\'s on the come up, you\'ll be like, "It\'s cool, but you missed"',  # filler 제거
    ])
    def test_cleaned_up_quote_accepted(self, quote):
        assert app._quote_in_words(quote, self.words())

    @pytest.mark.parametrize("quote", [
        "I bought a rocket ship to Mars last Tuesday",  # 완전 환각
        "focusing client brand you missed anything",    # 흩어진 단어 짜깁기
        "to be client your want you",                   # 순서 뒤집힘
        "",                                             # 빈 문자열
    ])
    def test_fabricated_quote_rejected(self, quote):
        assert not app._quote_in_words(quote, self.words())
