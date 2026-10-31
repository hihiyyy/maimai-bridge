"""站点知识表：去哪儿看、看什么、怎么认一条结果。

这里是「平台形状」的唯一来源。站点会改版，所以这些表只做**内置默认值**——
运行时可以在配置里覆盖（见 ``BridgeBrowseConfig``），改版时不必改代码。

约定：

- 所有键都用**规范名**（``bilibili`` / ``tieba`` / ``xiaoheihe`` / ``steam`` /
  ``zhihu`` / ``weibo`` / ``douban`` / ``xhs`` / ``github``）。
  用户嘴里的各种叫法（中文名、缩写）统一由 :func:`canonical_site` 翻译。
- 没配方的站点回退到「整页正文」，不要因为没写配方就报错。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

#: 站点简写 → 搜索页模板。``{q}`` 会被替换成 URL 编码后的关键词。
SITE_TEMPLATES: Dict[str, str] = {
    "bilibili": "https://search.bilibili.com/all?keyword={q}",
    "b站": "https://search.bilibili.com/all?keyword={q}",
    "bili": "https://search.bilibili.com/all?keyword={q}",
    "贴吧": "https://tieba.baidu.com/f/search/res?qw={q}",
    "tieba": "https://tieba.baidu.com/f/search/res?qw={q}",
    "小黑盒": "https://www.xiaoheihe.cn/search?q={q}",
    "xiaoheihe": "https://www.xiaoheihe.cn/search?q={q}",
    "steam": "https://store.steampowered.com/search/?term={q}",
    "知乎": "https://www.zhihu.com/search?type=content&q={q}",
    "zhihu": "https://www.zhihu.com/search?type=content&q={q}",
    "微博": "https://s.weibo.com/weibo?q={q}",
    "weibo": "https://s.weibo.com/weibo?q={q}",
    "豆瓣": "https://www.douban.com/search?q={q}",
    "douban": "https://www.douban.com/search?q={q}",
    "小红书": "https://www.xiaohongshu.com/search_result?keyword={q}",
    "github": "https://github.com/search?q={q}",
}

#: 站点简写 → 首页（关键词为空时用）。
SITE_HOMES: Dict[str, str] = {
    "bilibili": "https://www.bilibili.com/",
    "b站": "https://www.bilibili.com/",
    "bili": "https://www.bilibili.com/",
    "贴吧": "https://tieba.baidu.com/",
    "tieba": "https://tieba.baidu.com/",
    # 小黑盒的 /search 和 /home 都是空壳，只有 bbs 首页真的带内容流
    "小黑盒": "https://www.xiaoheihe.cn/app/bbs/home",
    "xiaoheihe": "https://www.xiaoheihe.cn/app/bbs/home",
    "steam": "https://store.steampowered.com/",
    "知乎": "https://www.zhihu.com/",
    "zhihu": "https://www.zhihu.com/",
    # 微博走手机版：桌面版的 s.weibo.com 搜索要登录，m.weibo.cn 不用
    "微博": "https://m.weibo.cn/",
    "weibo": "https://m.weibo.cn/",
    "豆瓣": "https://www.douban.com/",
    "douban": "https://www.douban.com/",
    "小红书": "https://www.xiaohongshu.com/",
    "github": "https://github.com/",
}

#: 这些站的搜索页对未登录 / 无头访问是死路（验证页或登录墙），只能看首页流。
#: 用户给了关键词时，我们不硬碰搜索页，直接去看首页，并如实说明「只能看首页」。
SITE_BROWSE_ONLY = frozenset({"weibo", "微博", "douban", "豆瓣", "xiaoheihe", "小黑盒"})

#: 站点配方：告诉抽取层「一条结果长什么样」。
#: item 是一条结果的选择器；fields 是字段名 → (选择器, 取哪个属性，None 表示取文字)；
#: link 是卡片的链接选择器（空字符串表示卡片本身就是 ``<a>``）。
SITE_RECIPES: Dict[str, Dict[str, Any]] = {
    "bilibili": {
        "item": ".bili-video-card",
        "limit": 8,
        "fields": {
            "标题": (".bili-video-card__info--tit", None),
            "作者": (".bili-video-card__info--author", None),
            "播放": (".bili-video-card__stats--item", None),
            "时长": (".bili-video-card__stats__duration", None),
            "日期": (".bili-video-card__info--date", None),
        },
        "link": "a",
    },
    "steam": {
        "item": "#search_resultsRows > a",
        "limit": 8,
        "fields": {
            "标题": (".title", None),
            "发售": (".search_released", None),
            "价格": (".discount_final_price", None),
        },
        "link": "",
    },
    "github": {
        "item": "div.search-title, .repo-list-item",
        "limit": 8,
        "fields": {
            "条目": (".", None),
        },
        "link": "a",
    },
    # 微博手机版：首页信息流，天然不用登录
    "weibo": {
        "item": "div.card.m-panel",
        "limit": 8,
        "wait_for": ".weibo-text",
        "fields": {
            "标题": (".weibo-text", None),
            "发布者": (".m-text-box .m-text-cut", None),
        },
        "link": "a[href*='/detail/'], a[href*='/status/']",
    },
    # 豆瓣首页：热门话题列表
    "douban": {
        "item": "li.rec_topics",
        "limit": 8,
        "fields": {
            "标题": ("a.rec_topics_name", None),
            "热度": (".rec_topics_subtitle", None),
        },
        "link": "a",
    },
    # 小黑盒 bbs 首页信息流
    "xiaoheihe": {
        "item": "a.hb-cpt__bbs-content",
        "limit": 8,
        "fields": {
            "标题": (".bbs-content__title", None),
            "正文": (".bbs-content__content", None),
        },
        "link": "",
    },
}

#: 平台规范名：用户在命令里怎么叫都行，内部统一成一个键。
SITE_CANON: Dict[str, str] = {
    "bilibili": "bilibili",
    "b站": "bilibili",
    "bili": "bilibili",
    "哔哩哔哩": "bilibili",
    "贴吧": "tieba",
    "tieba": "tieba",
    "百度贴吧": "tieba",
    "小黑盒": "xiaoheihe",
    "xiaoheihe": "xiaoheihe",
    "steam": "steam",
    "蒸汽": "steam",
    "知乎": "zhihu",
    "zhihu": "zhihu",
    "微博": "weibo",
    "weibo": "weibo",
    "豆瓣": "douban",
    "douban": "douban",
    "小红书": "xhs",
    "xhs": "xhs",
    "xiaohongshu": "xhs",
    "github": "github",
    "gh": "github",
}

#: 平台规范名 → 中文显示名。
SITE_LABELS: Dict[str, str] = {
    "bilibili": "B站",
    "tieba": "贴吧",
    "xiaoheihe": "小黑盒",
    "steam": "Steam",
    "zhihu": "知乎",
    "weibo": "微博",
    "douban": "豆瓣",
    "xhs": "小红书",
    "github": "GitHub",
}

#: 平台规范名 → cookie 该挂到哪些域（登录态注入用）。
SITE_DOMAINS: Dict[str, List[str]] = {
    "bilibili": [".bilibili.com"],
    "tieba": [".baidu.com"],
    "xiaoheihe": [".xiaoheihe.cn"],
    "steam": [".steampowered.com", ".steamcommunity.com"],
    "zhihu": [".zhihu.com"],
    "weibo": [".weibo.com", ".weibo.cn"],
    "douban": [".douban.com"],
    "xhs": [".xiaohongshu.com"],
    "github": [".github.com"],
}

#: 按域名猜站点（recipe 兜底用）。顺序即优先级。
_DOMAIN_HINTS: tuple[tuple[str, str], ...] = (
    ("bilibili.com", "bilibili"),
    ("b23.tv", "bilibili"),
    ("steampowered.com", "steam"),
    ("steamcommunity.com", "steam"),
    ("github.com", "github"),
    ("weibo.cn", "weibo"),
    ("weibo.com", "weibo"),
    ("douban.com", "douban"),
    ("xiaoheihe.cn", "xiaoheihe"),
    ("zhihu.com", "zhihu"),
    ("xiaohongshu.com", "xhs"),
    ("tieba.baidu.com", "tieba"),
)


def canonical_site(raw: str) -> str:
    """把各种叫法统一成规范平台名；不认识的返回空串。"""

    key = (raw or "").strip().lower()
    return SITE_CANON.get(key, "")


def guess_site_from_url(url: str) -> str:
    """从网址反推站点规范名；猜不出返回空串。"""

    lowered = (url or "").lower()
    for needle, site in _DOMAIN_HINTS:
        if needle in lowered:
            return site
    return ""


def resolve_recipe(site: str, url: str) -> Dict[str, Any]:
    """按站点简写或网址挑一个抽取配方；没有就返回空字典（调用方回退整页正文）。"""

    key = (site or "").strip().lower()
    # 中文站点名要先翻成规范名（微博 / 豆瓣 / 小黑盒 在 SITE_RECIPES 里是 weibo / douban / xiaoheihe）
    canon = SITE_CANON.get(key, key)
    for candidate in (key, canon):
        if candidate in SITE_RECIPES:
            return SITE_RECIPES[candidate]

    guessed = guess_site_from_url(url)
    if guessed and guessed in SITE_RECIPES:
        return SITE_RECIPES[guessed]
    return {}


def parse_override(raw: str) -> Dict[str, Dict[str, Any]]:
    """把配置里「站点覆盖」的 JSON 文本解析成配方字典。

    允许用户只写要改的那几个站，例如：

    ``{"bilibili": {"item": ".new-card", "fields": {"标题": [".t", null]}}}``

    解析失败返回空字典——宁可退回内置配方，也不要让「出去看看」整个不可用。
    """

    text = (raw or "").strip()
    if not text:
        return {}
    import json

    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for name, spec in data.items():
        if isinstance(spec, dict):
            result[str(name).strip().lower()] = spec
    return result


_SELECTOR_SPLIT = re.compile(r",\s*")


def split_selector(selector: str) -> List[str]:
    """把复合选择器拆成列表（``Page.query_selector`` 只吃单个）。"""

    return [part for part in _SELECTOR_SPLIT.split(selector or "") if part]


__all__ = [
    "SITE_BROWSE_ONLY",
    "SITE_CANON",
    "SITE_DOMAINS",
    "SITE_HOMES",
    "SITE_LABELS",
    "SITE_RECIPES",
    "SITE_TEMPLATES",
    "canonical_site",
    "guess_site_from_url",
    "parse_override",
    "resolve_recipe",
    "split_selector",
]
