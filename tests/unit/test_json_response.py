import pytest

from gitpilot.llm.json_response import parse_json_response


def test_repairs_invalid_backslashes_in_local_model_json():
    result = parse_json_response(r'{"pattern":"/\.stories\.js$/"}')

    assert result == {"pattern": r"/\.stories\.js$/"}


def test_preserves_valid_json_escapes():
    result = parse_json_response(r'{"content":"first\nsecond\\path"}')

    assert result == {"content": "first\nsecond\\path"}


def test_accepts_literal_control_characters_in_string_values():
    result = parse_json_response('{"content":"first\nsecond\tindented"}')

    assert result == {"content": "first\nsecond\tindented"}


def test_does_not_hide_other_json_errors():
    with pytest.raises(ValueError):
        parse_json_response('{"missing": }')
