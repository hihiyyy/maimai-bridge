"""``constants.py``：内置默认值与解析函数。

这里的重点是「留空就回退内置值」的约定 —— 用户把字段清空等价于「用默认」，
不是「禁用」。
"""

from __future__ import annotations

import pytest


def test_parse_csv_支持逗号(constants):
    assert constants.parse_csv("a,b,c") == ["a", "b", "c"]


def test_parse_csv_支持中文逗号(constants):
    assert constants.parse_csv("甲，乙，丙") == ["甲", "乙", "丙"]


def test_parse_csv_支持换行(constants):
    assert constants.parse_csv("甲\n乙\n丙") == ["甲", "乙", "丙"]


def test_parse_csv_支持分号(constants):
    assert constants.parse_csv("a;b;c") == ["a", "b", "c"]


def test_parse_csv_空串返回空列表(constants):
    assert constants.parse_csv("") == []
    assert constants.parse_csv("   ") == []


def test_parse_csv_去掉首尾空白但保留项内空格(constants):
    assert constants.parse_csv("  hello world , x ") == ["hello world", "x"]


def test_parse_csv_丢弃空项(constants):
    assert constants.parse_csv("a,,b,,") == ["a", "b"]


def test_resolve_csv_留空回退内置(constants):
    fallback = ["x", "y"]
    assert constants.resolve_csv("", fallback) == ("x", "y")


def test_resolve_csv_非空则整体覆盖(constants):
    fallback = ["x", "y"]
    assert constants.resolve_csv("a,b", fallback) == ("a", "b")


def test_resolve_user_agent_留空回退(constants):
    assert constants.resolve_user_agent("") == constants.DEFAULT_USER_AGENT


def test_resolve_user_agent_非空覆盖(constants):
    assert constants.resolve_user_agent("MyUA/1.0") == "MyUA/1.0"


@pytest.mark.parametrize(
    ("resolver", "fallback_name"),
    [
        ("resolve_block_markers", "DEFAULT_BLOCK_MARKERS"),
        ("resolve_action_redlines", "DEFAULT_ACTION_REDLINES"),
        ("resolve_action_social", "DEFAULT_ACTION_SOCIAL"),
        ("resolve_approve_words", "DEFAULT_APPROVE_WORDS"),
        ("resolve_deny_words", "DEFAULT_DENY_WORDS"),
    ],
)
def test_resolve_参数化留空回退内置(constants, resolver, fallback_name):
    got = getattr(constants, resolver)("")
    assert got == getattr(constants, fallback_name)


def test_contains_any_命中返回该词(constants):
    assert constants.contains_any("帮我转账一百块", ["付款", "转账"]) == "转账"


def test_contains_any_未命中返回空串(constants):
    assert constants.contains_any("今天天气不错", ["转账", "付款"]) == ""


def test_contains_any_空输入返回空串(constants):
    assert constants.contains_any("", ["转账"]) == ""


def test_extract_speak_抽出多句并剥掉标记(constants):
    text = "正文开头 [[speak]]第一句[[/speak]] 中间 [[speak]]第二句[[/speak]] 结尾"
    lines, cleaned = constants.extract_speak(text)
    assert lines == ["第一句", "第二句"]
    assert "[[speak]]" not in cleaned
    assert "正文开头" in cleaned and "结尾" in cleaned


def test_extract_speak_容错标记内空格(constants):
    lines, _ = constants.extract_speak("[[ speak ]]有空格也认[[ / speak ]]")
    assert lines == ["有空格也认"]


def test_extract_speak_空台词不收录(constants):
    lines, cleaned = constants.extract_speak("前[[speak]]   [[/speak]]后")
    assert lines == []
    assert "[[speak]]" not in cleaned


def test_extract_speak_没有标记时原样返回(constants):
    lines, cleaned = constants.extract_speak("就是一句普通的话")
    assert lines == []
    assert cleaned == "就是一句普通的话"


def test_extract_speak_压缩多余空行(constants):
    _, cleaned = constants.extract_speak("甲\n\n\n\n乙")
    assert "\n\n\n" not in cleaned
    assert cleaned == "甲\n\n乙"


def test_代发红线覆盖钱与账号类词(constants):
    joined = " ".join(constants.DEFAULT_RELAY_REDLINES)
    for word in ("转账", "付款", "密码", "验证码", "银行卡", "身份证"):
        assert word in joined


def test_所有人不在红线词里而在提及词里(constants):
    assert "@所有人" not in constants.DEFAULT_RELAY_REDLINES
    assert "@所有人" in constants.RELAY_MENTIONS
    assert "@全体成员" in constants.RELAY_MENTIONS


def test_speak_标记约定出现在提示里(constants):
    assert "[[speak]]" in constants.RELAY_HINT
    assert "[[/speak]]" in constants.RELAY_HINT