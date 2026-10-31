"""``sites.py``：站点知识表。

站点名有中文、有别名、有大小写差异，用户输入什么都有可能 —— 这一层就是把
「用户怎么叫」翻译成「代码里认的 key」。
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("bilibili", "bilibili"),
        ("B站", "bilibili"),
        ("b站", "bilibili"),
        ("哔哩哔哩", "bilibili"),
        ("  BILI  ", "bilibili"),
        ("github", "github"),
        ("gh", "github"),
        ("贴吧", "tieba"),
        ("百度贴吧", "tieba"),
        ("xiaohongshu", "xhs"),
        ("小红书", "xhs"),
        ("steam", "steam"),
        ("小黑盒", "xiaoheihe"),
    ],
)
def test_canonical_site_归一化(sites, raw, expected):
    assert sites.canonical_site(raw) == expected


def test_canonical_site_不认识返回空串(sites):
    assert sites.canonical_site("完全没听过的站") == ""
    assert sites.canonical_site("") == ""


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.bilibili.com/video/BV1xx", "bilibili"),
        ("https://b23.tv/abc", "bilibili"),
        ("https://github.com/hihiyyy/maimai-bridge", "github"),
        ("https://tieba.baidu.com/f?kw=x", "tieba"),
        ("https://www.zhihu.com/question/1", "zhihu"),
        ("https://m.weibo.cn/detail/1", "weibo"),
        ("https://www.douban.com/group/1", "douban"),
        ("https://www.xiaohongshu.com/explore", "xhs"),
        ("https://store.steampowered.com/app/1", "steam"),
        ("https://www.xiaoheihe.cn/app/bbs/home", "xiaoheihe"),
    ],
)
def test_guess_site_from_url(sites, url, expected):
    assert sites.guess_site_from_url(url) == expected


def test_guess_site_from_url_猜不出返回空串(sites):
    assert sites.guess_site_from_url("https://example.com/") == ""
    assert sites.guess_site_from_url("") == ""


def test_resolve_recipe_按规范名取(sites):
    recipe = sites.resolve_recipe("bilibili", "")
    assert recipe["item"] == ".bili-video-card"


def test_resolve_recipe_按中文名取(sites):
    assert sites.resolve_recipe("微博", "")["item"] == "div.card.m-panel"
    assert sites.resolve_recipe("豆瓣", "")["item"] == "li.rec_topics"
    assert sites.resolve_recipe("小黑盒", "")["item"] == "a.hb-cpt__bbs-content"


def test_resolve_recipe_名字不认识时按网址兜底(sites):
    recipe = sites.resolve_recipe("", "https://www.bilibili.com/video/BV1xx")
    assert recipe["item"] == ".bili-video-card"


def test_resolve_recipe_全空返回空字典(sites):
    assert sites.resolve_recipe("", "") == {}


def test_parse_override_正常解析(sites):
    raw = '{"bilibili": {"item": ".my-card", "wait_for": ".loaded"}}'
    got = sites.parse_override(raw)
    assert got["bilibili"]["item"] == ".my-card"
    assert got["bilibili"]["wait_for"] == ".loaded"


def test_parse_override_键小写去空白(sites):
    got = sites.parse_override('{"  BILI  ": {"item": ".x"}}')
    assert "bili" in got


def test_parse_override_坏JSON返回空字典(sites):
    assert sites.parse_override("{不是 json") == {}
    assert sites.parse_override("") == {}


def test_parse_override_顶层不是对象返回空字典(sites):
    assert sites.parse_override("[1, 2, 3]") == {}


def test_parse_override_跳过非对象值(sites):
    got = sites.parse_override('{"bilibili": ".x", "github": {"item": ".y"}}')
    assert "bilibili" not in got
    assert got["github"]["item"] == ".y"


def test_split_selector_按逗号切分(sites):
    assert sites.split_selector("a,b,c") == ["a", "b", "c"]
    assert sites.split_selector("a, b") == ["a", "b"]


def test_split_selector_空串返回空列表(sites):
    assert sites.split_selector("") == []


def test_browse_only_归一后是三个站(sites):
    assert {sites.canonical_site(x) for x in sites.SITE_BROWSE_ONLY} == {
        "weibo",
        "douban",
        "xiaoheihe",
    }


@pytest.mark.parametrize("site", ["bilibili", "steam", "github", "weibo", "douban", "xiaoheihe"])
def test_每个配方站点都有标签和域名(sites, site):
    assert site in sites.SITE_LABELS
    assert site in sites.SITE_DOMAINS
    assert site in sites.SITE_HOMES


def test_每个配方都有item选择器(sites):
    for site, recipe in sites.SITE_RECIPES.items():
        assert recipe.get("item"), f"{site} 缺 item 选择器"