"""麦麦 × DeepSeek Harness 桥插件。

四件事：
1. 人格互通：把麦麦当前人格（人设 / 行为风格 / 表达风格）暴露给 DSH。
2. 记忆互通：让外部读取麦麦的长期记忆，也让外部能请求麦麦记下一件事。
3. 双向互联：麦麦可以把活交给 DSH 执行；DSH 可以请求麦麦用她自己的口吻说话。
4. 出去看看：麦麦可以自己用无头浏览器去看外面的世界（B站 / 贴吧 / 小黑盒 / Steam……）。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from maibot_sdk import API, Command, Field, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

#: 插件目录。扩展插件跑在独立的 runner 进程里，未必有包上下文，
#: 所以把目录本身塞进 sys.path，让 `bili_video` 能作为顶层包被导入。
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

# 视频模块导入失败不能让整个插件挂掉（以前踩过 manifest 一个字节就静默不加载的坑），
# 失败时只关掉看视频这一块，其余功能照常。
_VIDEO_IMPORT_ERROR = ""
try:
    from bili_video import reactions  # noqa: E402
    from bili_video.client import BiliClient, BiliError, VideoPacket  # noqa: E402
    from bili_video.credential import ensure_credential_file, resolve_credential  # noqa: E402
    from bili_video.digest import render_watch  # noqa: E402
    from bili_video.target import parse_target  # noqa: E402
except Exception as _video_exc:  # noqa: BLE001
    reactions = None  # type: ignore[assignment]
    BiliClient = None  # type: ignore[assignment,misc]
    BiliError = None  # type: ignore[assignment,misc]
    VideoPacket = None  # type: ignore[assignment,misc]
    ensure_credential_file = None  # type: ignore[assignment]
    resolve_credential = None  # type: ignore[assignment]
    render_watch = None  # type: ignore[assignment]
    parse_target = None  # type: ignore[assignment]
    _VIDEO_IMPORT_ERROR = f"{type(_video_exc).__name__}: {_video_exc}"


class BridgeCoreConfig(PluginConfigBase):
    """桥的核心配置。"""

    __ui_label__ = "桥接"
    __ui_icon__ = "link"
    __ui_order__ = 0

    config_version: str = Field(default="1.2.0", description="配置版本")

    # —— 总开关 ——
    enabled: bool = Field(default=True, description="是否启用桥接功能（关闭后 dsh_task 不可用）")

    # —— 记忆互通 ——
    recall_limit: int = Field(default=5, description="maimai_recall 默认返回条数（1-20）")
    allow_memory_write: bool = Field(
        default=True,
        description="是否允许通过 maimai_remember 让麦麦写入长期记忆",
    )

    # —— 双向互联：调 DSH ——
    dsh_command: str = Field(default="dsh", description="DSH 可执行文件（或完整路径）")
    dsh_profile: str = Field(default="headless", description="调用 DSH 时使用的 profile")
    dsh_timeout_seconds: int = Field(default=240, description="单次 DSH 任务最长等待秒数")
    dsh_cwd: str = Field(default="", description="DSH 子进程的工作目录（留空则继承 MaiBot 的）")
    dsh_extra_args: str = Field(
        default="",
        description="追加给 dsh 的参数，按空格拆开（例如 --session-id <id> 续用同一会话）",
    )

    # —— 双向互联：让麦麦说话 ——
    speak_model: str = Field(default="", description="maimai_speak 使用的模型名（留空用宿主默认）")


class BridgeBrowseConfig(PluginConfigBase):
    """「出去看看」的配置：无头浏览器。"""

    __ui_label__ = "出去看看"
    __ui_icon__ = "compass"
    __ui_order__ = 10

    enabled: bool = Field(default=True, description="是否允许麦麦自己用浏览器出去看（关掉后 look_around 不可用）")
    browser_channel: str = Field(
        default="msedge",
        description="浏览器通道：msedge（系统 Edge）/ chrome / 留空改用 playwright 自带 chromium",
    )
    headless: bool = Field(default=True, description="是否无头运行（关掉会弹窗口，会占你的屏）")
    timeout_seconds: int = Field(default=45, description="打开页面最长等待秒数")
    max_chars: int = Field(default=1200, description="返回给麦麦的正文最多多少字")
    wait_after_load_ms: int = Field(default=1200, description="页面加载后再等多久（毫秒），给动态内容一点时间")
    cooldown_seconds: int = Field(default=20, description="两次 look_around 之间至少间隔多少秒（防止她连刷）")
    max_per_hour: int = Field(default=12, description="每小时最多出去看几次（0 表示不限制）")


class BridgeVideoConfig(PluginConfigBase):
    """「看视频」的配置：走 B站 接口，读字幕 / 简介 / 弹幕 / 热评。"""

    __ui_label__ = "看视频"
    __ui_icon__ = "play-circle"
    __ui_order__ = 20

    enabled: bool = Field(default=True, description="是否允许看视频（关掉后 watch_video 不可用）")
    sessdata: str = Field(
        default="",
        description="B站 SESSDATA（填了才读得到字幕；留空则读凭证文件 bili_credential.json）",
    )
    bili_jct: str = Field(default="", description="B站 bili_jct（可选，留空则读凭证文件）")
    user_agent: str = Field(default="", description="自定义 UA（留空用内置的桌面 Edge UA）")
    credential_file: str = Field(
        default="",
        description="凭证文件相对路径（相对插件 data 目录），留空用 bili_credential.json",
    )
    subtitle: bool = Field(default=True, description="是否读字幕（这是「真的看懂视频」的关键）")
    subtitle_max_chars: int = Field(default=3000, description="字幕最多取多少字")
    desc_max_chars: int = Field(default=500, description="简介最多取多少字")
    comment_limit: int = Field(default=12, description="热门评论取几条")
    danmaku: bool = Field(default=True, description="是否抽样弹幕")
    danmaku_limit: int = Field(default=40, description="弹幕抽样几条")
    related_limit: int = Field(default=4, description="相关推荐取几条")
    proxy: str = Field(default="", description="代理地址，如 http://127.0.0.1:7890（留空直连）")
    timeout_seconds: int = Field(default=20, description="单次接口请求超时秒数")


class BridgeTasteConfig(PluginConfigBase):
    """「喜欢就自己动手」的配置：看完一个东西觉得好，自己点赞 / 收藏。"""

    __ui_label__ = "喜欢就自己动手"
    __ui_icon__ = "heart"
    __ui_order__ = 30

    enabled: bool = Field(default=True, description="是否允许她自己点赞 / 收藏（关掉后只会嘴上说喜欢，不动手）")
    auto_like: bool = Field(default=True, description="遇到喜欢的能不能自己点赞")
    auto_fav: bool = Field(default=True, description="遇到特别喜欢的能不能自己收藏")
    fav_folder: str = Field(
        default="",
        description="收藏到哪个收藏夹（留空 = 默认收藏夹；填名字或 id 都行）",
    )
    daily_limit: int = Field(default=10, description="每天最多自己动手几次（0 表示不限制）")
    cooldown_seconds: int = Field(default=300, description="两次动手之间至少隔多少秒（防止一激动连点一串）")
    require_reason: bool = Field(
        default=True,
        description="是否必须说明「为什么喜欢」。开着能挡住没头没脑的乱点，她也更容易记住自己喜欢什么",
    )
    dry_run: bool = Field(
        default=False,
        description="试运行：只在日志和返回里说「我本来想赞这个」，不真的发出去",
    )


class MaiMaiBridgeConfig(PluginConfigBase):
    """桥插件配置。"""

    plugin: BridgeCoreConfig = Field(default_factory=BridgeCoreConfig)
    browse: BridgeBrowseConfig = Field(default_factory=BridgeBrowseConfig)
    video: BridgeVideoConfig = Field(default_factory=BridgeVideoConfig)
    taste: BridgeTasteConfig = Field(default_factory=BridgeTasteConfig)


# 站点简写 → 搜索页模板。{q} 会被替换成 URL 编码后的关键词。
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

# 站点简写 → 首页（关键词为空时用）
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

# 这些站的搜索页对未登录 / 无头访问是死路（验证页或登录墙），只能看首页流。
# 用户给了关键词时，我们不硬碰搜索页，直接去看首页，并如实说明「只能看首页」。
SITE_BROWSE_ONLY = {"weibo", "微博", "douban", "豆瓣", "xiaoheihe", "小黑盒"}

# 站点配方：告诉抽取层「一条结果长什么样」。
# item 是一条结果的选择器；fields 是字段名 → (选择器, 取哪个属性，None 表示取文字)；
# link 是卡片的链接选择器（空字符串表示卡片本身就是 <a>）。没配方的站点回退到整页正文。
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

# 平台规范名：用户在命令里怎么叫都行，内部统一成一个键。
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

# 平台规范名 → 中文显示名
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

# 平台规范名 → cookie 该挂到哪些域（登录态注入用）
SITE_DOMAINS: Dict[str, list] = {
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

LOGIN_FILENAME = "logins.json"


def _canonical_site(raw: str) -> str:
    """把各种叫法统一成规范平台名；不认识的返回空串。"""

    key = (raw or "").strip().lower()
    return SITE_CANON.get(key, "")


def _plugin_dir() -> str:
    """插件自己所在的目录（数据文件都放这儿）。"""

    import os

    return os.path.dirname(os.path.abspath(__file__))


def _login_path() -> str:
    """登录信息的存放路径。"""

    import os

    return os.path.join(_plugin_dir(), LOGIN_FILENAME)


def _load_logins() -> Dict[str, Dict[str, str]]:
    """读回各平台的登录信息；文件坏了就当空的。"""

    import os

    path = _login_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for site, entry in data.items():
        if isinstance(entry, dict):
            result[str(site)] = {
                "cookie": str(entry.get("cookie", "") or ""),
                "ua": str(entry.get("ua", "") or ""),
            }
    return result


def _save_logins(data: Dict[str, Dict[str, str]]) -> None:
    """写回登录信息（只写非空项）。"""

    import os

    cleaned = {
        site: {"cookie": str(entry.get("cookie", "") or ""), "ua": str(entry.get("ua", "") or "")}
        for site, entry in data.items()
        if str(entry.get("cookie", "") or "").strip()
    }
    with open(_login_path(), "w", encoding="utf-8") as handle:
        json.dump(cleaned, handle, ensure_ascii=False, indent=2)


def _cookies_for(site: str) -> list:
    """把某平台的 cookie 字符串摊成 playwright 能吃的 cookie 列表。"""

    canon = _canonical_site(site)
    if not canon:
        return []
    entry = _load_logins().get(canon)
    if not entry:
        return []
    raw = str(entry.get("cookie", "") or "").strip()
    if not raw:
        return []
    cookies: list = []
    for domain in SITE_DOMAINS.get(canon, []):
        for chunk in raw.split(";"):
            piece = chunk.strip()
            if not piece or "=" not in piece:
                continue
            name, _, value = piece.partition("=")
            name = name.strip()
            value = value.strip().strip('"')
            if not name:
                continue
            cookies.append(
                {"name": name, "value": value, "domain": domain, "path": "/"}
            )
    return cookies


def _format_items(label: str, what: str, result: Dict[str, Any], limit: int = 5) -> str:
    """把抓到的条目排成一段能直接发到群里的文字。"""

    title = f"{label} · {what}" if what else label
    items = result.get("items") or []
    if not items:
        excerpt = str(result.get("excerpt") or "").strip()
        head = f"{title}\n（没按结构抓到条目）"
        return f"{head}\n{excerpt[:400]}" if excerpt else head
    lines = [f"{title}（共 {result.get('matched', len(items))} 条）", ""]
    for index, item in enumerate(items[:limit], 1):
        name = item.get("标题") or item.get("条目") or "（无标题）"
        lines.append(f"{index}. {name}")
        extras = [
            str(value)
            for key, value in item.items()
            if key not in ("标题", "条目", "链接") and str(value or "").strip()
        ]
        if extras:
            lines.append("   " + " · ".join(extras))
        link = str(item.get("链接") or "").strip()
        if link:
            if link.startswith("//"):
                link = "https:" + link
            lines.append(f"   {link}")
    return "\n".join(lines)


def _digest(result: Dict[str, Any], limit: int = 12) -> str:
    """把抓到的条目压成一段纯文本，喂给「说说你有什么感觉」用。

    跟 `_format_items` 的区别：那个是给人看的（带序号和换行排版），
    这个是给模型看的（去掉链接，尽量密）。
    """

    items = result.get("items") or []
    if items:
        rows = []
        for index, item in enumerate(items[:limit], 1):
            parts = [
                str(value)
                for key, value in item.items()
                if key != "链接" and str(value or "").strip()
            ]
            if parts:
                rows.append(f"{index}. " + " · ".join(parts))
        if rows:
            return "\n".join(rows)
    return str(result.get("excerpt") or "")[:1500]


# 站点弹出验证时页面上会出现的字样：命中就当成「被挡住了」，不要硬看。
_BLOCK_MARKERS = (    "百度安全验证",
    "请完成下方验证",
    "滑动验证",
    "安全验证",
    "验证码",
    "Just a moment",
    "Enable JavaScript and cookies",
    "异常流量",
)


def _resolve_recipe(site: str, url: str) -> Dict[str, Any]:
    """按站点简写或网址挑一个抽取配方；没有就返回空字典。"""

    key = (site or "").strip().lower()
    # 中文站点名要先翻成规范名（微博 / 豆瓣 / 小黑盒 在 SITE_RECIPES 里是 weibo / douban / xiaoheihe）
    canon = SITE_CANON.get(key, key)
    for candidate in (key, canon):
        if candidate in SITE_RECIPES:
            return SITE_RECIPES[candidate]

    lowered = (url or "").lower()
    if "bilibili.com" in lowered:
        return SITE_RECIPES["bilibili"]
    if "steampowered.com" in lowered or "steamcommunity.com" in lowered:
        return SITE_RECIPES["steam"]
    if "github.com" in lowered:
        return SITE_RECIPES["github"]
    if "weibo.cn" in lowered or "weibo.com" in lowered:
        return SITE_RECIPES["weibo"]
    if "douban.com" in lowered:
        return SITE_RECIPES["douban"]
    if "xiaoheihe.cn" in lowered:
        return SITE_RECIPES["xiaoheihe"]
    return {}


def _extract_items(page: Any, recipe: Dict[str, Any]) -> list:
    """按配方把页面上的结果抽成结构化条目（抓不到就返回空列表）。"""

    limit = int(recipe.get("limit") or 8)
    items: list = []
    try:
        cards = page.locator(recipe["item"])
        total = cards.count()
    except Exception:  # noqa: BLE001
        return items

    for index in range(min(total, limit)):
        card = cards.nth(index)
        row: Dict[str, str] = {}
        for name, spec in (recipe.get("fields") or {}).items():
            selector, attr = spec
            try:
                node = card.locator(selector).first if selector != "." else card
                if node.count() == 0:
                    continue
                value = node.get_attribute(attr) if attr else node.inner_text()
            except Exception:  # noqa: BLE001
                continue
            if value:
                row[name] = re.sub(r"\s+", " ", str(value)).strip()[:120]

        link_selector = recipe.get("link", "a")
        try:
            if link_selector:
                anchor = card.locator(link_selector).first
                href = anchor.get_attribute("href") if anchor.count() else None
            else:
                href = card.get_attribute("href")
        except Exception:  # noqa: BLE001
            href = None
        if href:
            row["链接"] = href.split("?")[0] if "bilibili" not in href else href

        if row.get("标题") or row.get("条目"):
            items.append(row)
    return items


def _normalize_whitespace(text: str) -> str:
    """把连续空白压成一个，去掉空行。"""

    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _pick_excerpt(text: str, what: str, max_chars: int) -> str:
    """从正文里挑出和 what 最相关的一段；挑不到就取开头。"""

    cleaned = _normalize_whitespace(text)
    lines = [line for line in cleaned.split("\n") if len(line) >= 4]
    if not lines:
        return cleaned[:max_chars]

    terms = [term for term in re.split(r"[\s,，、;；]+", what or "") if len(term) >= 2]
    if terms:
        for index, line in enumerate(lines):
            if any(term in line for term in terms):
                start = max(0, index - 4)
                return "\n".join(lines[start : start + 50])[:max_chars]

    return "\n".join(lines)[:max_chars]


def _resolve_url(site: str, what: str, url: str) -> Tuple[str, str]:
    """决定要打开哪个地址，并返回一句来源说明。"""

    from urllib.parse import quote

    if url.strip():
        return url.strip(), "你给的网址"

    key = (site or "").strip().lower()
    query = (what or "").strip()

    # 微博 / 豆瓣 / 小黑盒：搜索页在未登录 + 无头下是死路（验证页或登录墙），
    # 与其硬撞，不如去看首页流，并在来源里如实说明，别让她以为搜过了。
    if key in SITE_BROWSE_ONLY and key in SITE_HOMES:
        return SITE_HOMES[key], f"{site} 的搜索页要登录或过验证，只能看首页流"

    template = SITE_TEMPLATES.get(key)
    if template and query:
        return template.format(q=quote(query)), f"{site} 的搜索结果"

    home = SITE_HOMES.get(key)
    if home:
        return home, f"{site} 首页"

    # 没给站点也没给网址：拿关键词去 Bing 搜
    if query:
        return f"https://www.bing.com/search?q={quote(query)}", "网页搜索结果"

    return "https://www.bing.com/", "随便看看"


def _browse_sync(
    url: str,
    what: str,
    max_chars: int,
    timeout_seconds: int,
    channel: str,
    headless: bool,
    wait_after_load_ms: int,
    recipe: Dict[str, Any] | None = None,
    cookies: list | None = None,
) -> Dict[str, Any]:
    """真正去打开网页并抓正文（同步，跑在线程里）。

    给了配方就优先抽结构化条目；抽不到再把整页正文作为兜底。
    cookies 是这个平台已保存的登录态，注入后能看到登录后才有的内容。
    """

    from playwright.sync_api import sync_playwright

    launch_kwargs: Dict[str, Any] = {"headless": headless}
    if channel.strip():
        launch_kwargs["channel"] = channel.strip()

    items: list = []
    matched = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_kwargs)
        try:
            context = browser.new_context(
                locale="zh-CN",
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
                ),
            )
            if cookies:
                try:
                    context.add_cookies(cookies)
                except Exception:  # noqa: BLE001
                    pass
            page = context.new_page()
            page.goto(url, timeout=timeout_seconds * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(max(0, wait_after_load_ms))
            title = page.title()
            if recipe:
                # 有些站（微博）先渲染一堆空壳卡片，内容稍后才填进去。
                # 配方里给了 wait_for 就先等它出现，别在空壳上抽字段。
                wait_for = recipe.get("wait_for")
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=8000)
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    matched = page.locator(recipe["item"]).count()
                except Exception:  # noqa: BLE001
                    matched = 0
                if matched:
                    items = _extract_items(page, recipe)
            body = page.inner_text("body")
        finally:
            browser.close()

    blocked = ""
    probe = f"{title} {body[:600]}"
    for marker in _BLOCK_MARKERS:
        if marker in probe:
            blocked = marker
            break

    return {
        "url": url,
        "title": title,
        "excerpt": _pick_excerpt(body, what, max_chars),
        "total_chars": len(body),
        "items": items,
        "matched": matched,
        "blocked": blocked,
    }


class MaiMaiBridgePlugin(MaiBotPlugin):
    """麦麦 × DSH 桥插件。"""

    config_model = MaiMaiBridgeConfig

    def __init__(self) -> None:
        """初始化运行时状态。"""

        super().__init__()
        self._browse_lock = asyncio.Lock()
        self._browse_times: list[float] = []
        self._bili_lock = asyncio.Lock()
        self._bili: Optional[Any] = None
        self._bili_cred_path: Optional[Path] = None

    async def on_load(self) -> None:
        """插件加载。"""
        self.ctx.logger.info("[maimai_bridge] 桥插件已加载")
        if _VIDEO_IMPORT_ERROR:
            self.ctx.logger.warning(
                "[maimai_bridge] 看视频模块导入失败，相关功能已关闭：%s", _VIDEO_IMPORT_ERROR
            )

    async def on_unload(self) -> None:
        """插件卸载。"""
        if self._bili is not None:
            try:
                await self._bili.close()
            except Exception:  # noqa: BLE001
                pass
            self._bili = None
        self.ctx.logger.info("[maimai_bridge] 桥插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        """处理配置热重载事件。

        Args:
            scope: 配置变更范围。
            config_data: 最新配置数据。
            version: 配置版本号。
        """

        self.ctx.logger.info("[maimai_bridge] 配置已更新，版本 %s，范围 %s", version, scope)
        del config_data

    # ===== 看视频（B站） =====

    def _video_data_dir(self) -> Path:
        """插件自己的数据目录：凭证文件放这儿。"""

        data_dir = getattr(getattr(self.ctx, "paths", None), "data_dir", None)
        if data_dir is None:
            data_dir = Path(_PLUGIN_DIR) / "data"
        return Path(data_dir)

    async def _video_client(self) -> Any:
        """惰性建 B站 客户端（复用连接池，插件生命周期内只有一个）。"""

        if _VIDEO_IMPORT_ERROR:
            raise RuntimeError(f"看视频模块不可用：{_VIDEO_IMPORT_ERROR}")

        async with self._bili_lock:
            if self._bili is not None:
                return self._bili

            cfg = self.config.video
            data_dir = self._video_data_dir()
            credential, cred_path = resolve_credential(
                config_sessdata=str(cfg.sessdata or ""),
                config_bili_jct=str(cfg.bili_jct or ""),
                config_user_agent=str(cfg.user_agent or ""),
                data_dir=data_dir,
                configured_path=str(cfg.credential_file or ""),
            )
            if ensure_credential_file(cred_path):
                self.ctx.logger.info("[maimai_bridge] 已生成B站登录凭证模板：%s", cred_path)
            self._bili_cred_path = cred_path

            client = BiliClient(
                sessdata=credential.sessdata,
                bili_jct=credential.bili_jct,
                user_agent=credential.user_agent,
                proxy=str(cfg.proxy or ""),
                timeout_seconds=float(cfg.timeout_seconds or 20),
            )
            client.credential_source = credential.source
            await client.start()
            self._bili = client
            self.ctx.logger.info(
                "[maimai_bridge] B站客户端就绪：登录状态=%s（%s）",
                "已登录" if credential.has_login else "未登录，读不到字幕",
                credential.source,
            )
            return self._bili

    async def _open_video(self, raw_target: str) -> Tuple[Any, str]:
        """把一句话/BV号/链接变成读完的视频素材。

        Returns:
            ``(视频素材, 失败原因)``。成功时失败原因为空串。
        """

        cfg = self.config.video
        client = await self._video_client()
        target = parse_target(raw_target)
        if target is None:
            return None, "没看懂要看哪个视频"

        bvid, aid = target.bvid, target.aid
        page = target.page
        if target.needs_short_link_resolve:
            try:
                final_url = await client.resolve_short_link(target.short_link)
            except BiliError as exc:
                return None, str(exc)
            resolved = parse_target(final_url)
            if resolved is None or resolved.kind != "video" or not (resolved.bvid or resolved.aid):
                return None, "这条短链没解析出视频"
            bvid, aid, page = resolved.bvid, resolved.aid, resolved.page

        if target.kind == "search":
            try:
                hits = await client.search(keyword=target.keyword, limit=3)
            except BiliError as exc:
                return None, str(exc)
            if not hits:
                return None, f"搜「{target.keyword}」什么都没搜到"
            bvid, aid, page = hits[0].bvid, 0, 1

        try:
            packet = await client.fetch_video(
                bvid=bvid,
                aid=aid,
                page=page,
                want_subtitle=bool(cfg.subtitle),
                subtitle_max_chars=int(cfg.subtitle_max_chars),
                comment_limit=int(cfg.comment_limit),
                danmaku_limit=int(cfg.danmaku_limit) if cfg.danmaku else 0,
                related_limit=int(cfg.related_limit),
            )
        except BiliError as exc:
            return None, str(exc)
        return packet, ""

    # ===== 喜欢就自己动手（点赞 / 收藏） =====

    def _taste_path(self) -> Path:
        """点赞/收藏的记账文件（按天分账，跨天自动清零）。"""

        return self._video_data_dir() / "plugins" / "maimai_bridge" / "taste.json"

    def _load_taste(self) -> Dict[str, Any]:
        """读今天的账；日期变了就重开一本。"""

        today = time.strftime("%Y-%m-%d")
        path = self._taste_path()
        data: Any = {}
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
        if not isinstance(data, dict) or data.get("date") != today:
            data = {"date": today, "liked": [], "faved": [], "events": []}
        for key in ("liked", "faved", "events"):
            if not isinstance(data.get(key), list):
                data[key] = []
        return data

    def _save_taste(self, data: Dict[str, Any]) -> None:
        path = self._taste_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.warning("[maimai_bridge] 写 taste.json 失败：%s", exc)

    def _taste_block_reason(self, data: Dict[str, Any]) -> str:
        """额度 / 冷却检查。返回空串表示可以动手。"""

        cfg = self.config.taste
        if not cfg.enabled:
            return "「喜欢就自己动手」这块是关着的"
        limit = int(cfg.daily_limit or 0)
        used = len(data["liked"]) + len(data["faved"])
        if limit > 0 and used >= limit:
            return f"今天已经动手 {used} 次了，到上限了（每天 {limit} 次），明天再说吧"
        cooldown = int(cfg.cooldown_seconds or 0)
        if cooldown > 0 and data["events"]:
            try:
                last_ts = float(data["events"][-1].get("ts") or 0)
            except (TypeError, ValueError, AttributeError):
                last_ts = 0.0
            if last_ts:
                gap = time.time() - last_ts
                if gap < cooldown:
                    return f"刚动过手，{int(cooldown - gap)} 秒后再来（一激动连点一串会被当成刷赞）"
        return ""

    async def _react(self, action: str, raw_target: str, reason: str) -> str:
        """真正去点赞 / 收藏，返回一句给人看的结果。"""

        cfg = self.config.taste
        if _VIDEO_IMPORT_ERROR or reactions is None:
            return f"看视频模块没装好，动不了手：{_VIDEO_IMPORT_ERROR}"

        action = (action or "like").strip().lower()
        if action not in ("like", "fav", "both"):
            return f"action 只能是 like / fav / both，收到的是「{action}」"

        reason = (reason or "").strip()
        if cfg.require_reason and not reason:
            return "得先说一句为什么喜欢——不是走流程，是让你自己记住为什么。想不出来，那大概也没那么喜欢"

        want_like = action in ("like", "both") and bool(cfg.auto_like)
        want_fav = action in ("fav", "both") and bool(cfg.auto_fav)
        if not want_like and not want_fav:
            return "配置里既没允许点赞，也没允许收藏"

        data = self._load_taste()
        blocked = self._taste_block_reason(data)
        if blocked:
            return blocked

        target = parse_target(raw_target)
        if target is None:
            return "没看懂要赞哪个视频"

        client = await self._video_client()
        http = getattr(client, "_client", None)
        csrf = str(getattr(client, "_bili_jct", "") or "")
        if http is None:
            return "B站客户端还没起来，稍后再试"

        try:
            view = await client.view(bvid=target.bvid, aid=target.aid)
        except BiliError as exc:
            return f"取视频信息失败：{exc}"

        bvid = str(view.get("bvid") or target.bvid or "")
        aid = int(view.get("aid") or 0)
        title = str(view.get("title") or bvid)
        if not bvid or aid <= 0:
            return "没取到这个视频的 id"

        try:
            state = await reactions.relation(http, bvid)
        except Exception as exc:  # noqa: BLE001
            return f"查状态失败：{exc}"

        notes: list[str] = []
        acted = False

        if want_like:
            if state.get("like"):
                notes.append("这条已经赞过了")
            elif cfg.dry_run:
                notes.append("（试运行）我本来想点赞")
            else:
                try:
                    await reactions.set_like(http, csrf, aid, liked=True)
                    notes.append("点了赞")
                    acted = True
                    data["liked"].append(
                        {"aid": aid, "bvid": bvid, "title": title, "reason": reason, "ts": time.time()}
                    )
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"点赞失败：{exc}")

        if want_fav:
            if state.get("favorite"):
                notes.append("这条已经在收藏夹里了")
            else:
                try:
                    mid, _uname = await reactions.whoami(http)
                    folders = await reactions.fav_folders(http, mid) if mid else []
                    folder, hint = reactions.pick_folder(folders, str(cfg.fav_folder or ""))
                    if folder is None:
                        notes.append(f"收藏失败：{hint}")
                    elif cfg.dry_run:
                        notes.append(f"（试运行）我本来想收藏到「{folder['title']}」")
                    else:
                        await reactions.add_to_favorites(http, csrf, aid, int(folder["id"]))
                        notes.append(f"收藏到「{folder['title']}」")
                        acted = True
                        data["faved"].append(
                            {"aid": aid, "bvid": bvid, "title": title, "reason": reason, "ts": time.time()}
                        )
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"收藏失败：{exc}")

        if acted:
            data["events"].append({"ts": time.time(), "action": action, "bvid": bvid, "title": title, "reason": reason})
            self._save_taste(data)

        used = len(data["liked"]) + len(data["faved"])
        limit = int(cfg.daily_limit or 0)
        tail = f"（今天第 {used} 次" + (f"，上限 {limit}" if limit > 0 else "") + "）"
        return f"《{title}》：" + "，".join(notes) + tail

    @Tool(
        "bili_react",
        description=(
            "遇到真正喜欢的视频时，自己动手点赞或收藏（会真的发到你自己的 B站 账号上）。"
            "只有真心觉得好才用，「还行」就别用；用了要说一句为什么喜欢。"
        ),
        parameters=[
            ToolParameterInfo(
                name="target", param_type=ToolParamType.STRING, description="BV 号、视频链接或关键词", required=True
            ),
            ToolParameterInfo(
                name="action",
                param_type=ToolParamType.STRING,
                description="like=点赞（默认）/ fav=收藏 / both=都来",
                required=False,
            ),
            ToolParameterInfo(
                name="reason",
                param_type=ToolParamType.STRING,
                description="为什么喜欢，一句话，会记进当天的账里",
                required=False,
            ),
        ],
    )
    async def tool_bili_react(self, target: str = "", action: str = "like", reason: str = "", **kwargs: Any) -> Dict[str, Any]:
        """自己点赞 / 收藏。"""

        del kwargs
        if not target:
            return {"name": "bili_react", "content": "得说清楚是哪个视频"}
        text = await self._react(action, target, reason)
        return {"name": "bili_react", "content": text}

    @Tool(
        "bili_taste_status",
        description="看看今天自己动手了几次、赞过收藏过什么。想回顾一下自己的口味时用。",
    )
    async def tool_bili_taste_status(self, **kwargs: Any) -> Dict[str, Any]:
        """返回当天的点赞 / 收藏记账。"""

        del kwargs
        cfg = self.config.taste
        data = self._load_taste()
        used = len(data["liked"]) + len(data["faved"])
        limit = int(cfg.daily_limit or 0)
        lines = [f"今天（{data['date']}）自己动手 {used} 次" + (f"，上限 {limit}" if limit > 0 else "（不限）")]
        for item in data["liked"][-5:]:
            lines.append(f"· 赞过《{item.get('title', '')}》—— {item.get('reason', '')}")
        for item in data["faved"][-5:]:
            lines.append(f"· 收藏《{item.get('title', '')}》—— {item.get('reason', '')}")
        if used == 0:
            lines.append("还没动手过")
        return {"name": "bili_taste_status", "content": "\n".join(lines)}

    # ===== 人格互通 =====

    @API("persona", description="读取麦麦当前人格设定，供 DSH 侧同步使用", version="1")
    async def api_persona(self) -> Dict[str, Any]:
        """返回麦麦当前的人格、行为风格与表达风格。"""

        current = await self.ctx.personality.get_current()
        return {"ok": True, "persona": current}

    @Tool(
        "maimai_persona",
        description="读取麦麦当前的人格设定（她是谁、怎么说话）。需要以麦麦的身份行动时先调这个。",
    )
    async def tool_persona(self, **kwargs: Any) -> Dict[str, Any]:
        """把人格设定作为工具结果返回。"""

        del kwargs
        current = await self.ctx.personality.get_current()
        return {"name": "maimai_persona", "content": json.dumps(current, ensure_ascii=False)}

    # ===== 记忆互通 =====

    @Tool(
        "maimai_recall",
        description="检索麦麦的长期记忆，看看她以前记住过什么。要回忆旧事时使用。",
        parameters=[
            ToolParameterInfo(name="query", param_type=ToolParamType.STRING, description="检索关键词", required=True),
            ToolParameterInfo(name="limit", param_type=ToolParamType.INTEGER, description="返回条数，默认 5", required=False),
        ],
    )
    async def tool_recall(self, query: str = "", limit: int = 0, **kwargs: Any) -> Dict[str, Any]:
        """调用宿主的知识检索能力，读麦麦的长期记忆。"""

        del kwargs
        if not query:
            return {"name": "maimai_recall", "content": "检索词不能为空"}

        default_limit = self.config.plugin.recall_limit or 5
        count = int(limit) if limit else int(default_limit)
        count = max(1, min(20, count))

        result = await self.ctx.knowledge.search(query, count)
        return {"name": "maimai_recall", "content": str(result)}

    @Tool(
        "maimai_remember",
        description="让麦麦自己把一件事记进长期记忆。只在确实值得长期记住时使用。",
        parameters=[
            ToolParameterInfo(name="content", param_type=ToolParamType.STRING, description="要记住的内容", required=True),
            ToolParameterInfo(name="stream_id", param_type=ToolParamType.STRING, description="聊天流 ID", required=True),
        ],
    )
    async def tool_remember(self, content: str = "", stream_id: str = "", **kwargs: Any) -> Dict[str, Any]:
        """通过主动任务让麦麦走一遍她自己的记忆写入流程。"""

        del kwargs
        if not content or not stream_id:
            return {"name": "maimai_remember", "content": "content 与 stream_id 都不能为空"}

        if not self.config.plugin.allow_memory_write:
            return {"name": "maimai_remember", "content": "配置里关闭了记忆写入（allow_memory_write）"}

        await self.ctx.maisaka.proactive.trigger(
            stream_id,
            intent=f"把这件事记进你的长期记忆，别回复任何人：{content}",
            reason="maimai_bridge 记忆写入",
        )
        return {"name": "maimai_remember", "content": "已交给麦麦处理记忆写入"}

    # ===== 双向互联 =====

    @Tool(
        "maimai_speak",
        description="让麦麦用她自己的口吻写一段话（不会自动发送）。需要『像麦麦那样说』时使用。",
        parameters=[
            ToolParameterInfo(name="stream_id", param_type=ToolParamType.STRING, description="聊天流 ID", required=True),
            ToolParameterInfo(name="reference", param_type=ToolParamType.STRING, description="要写成什么样、说了什么材料", required=True),
        ],
    )
    async def tool_speak(self, stream_id: str = "", reference: str = "", **kwargs: Any) -> Dict[str, Any]:
        """复用宿主的人格与表达选择，生成一段麦麦口吻的文本。"""

        del kwargs
        if not stream_id or not reference:
            return {"name": "maimai_speak", "content": "stream_id 与 reference 都不能为空"}

        result = await self.ctx.maisaka.reply.generate(
            stream_id,
            reference,
            model_name=str(self.config.plugin.speak_model or ""),
        )
        return {"name": "maimai_speak", "content": json.dumps(result, ensure_ascii=False)}

    @Tool(
        "dsh_task",
        description="把一件需要动手的活交给 DeepSeek Harness 去执行（它能操作电脑、查资料、写文件）。",
        parameters=[
            ToolParameterInfo(name="task", param_type=ToolParamType.STRING, description="交给 DSH 的任务描述", required=True),
        ],
    )
    async def tool_dsh_task(self, task: str = "", **kwargs: Any) -> Dict[str, Any]:
        """以一次性进程调用 DSH headless，返回它的最终答复。"""

        del kwargs
        if not task:
            return {"name": "dsh_task", "content": "任务描述不能为空"}

        core = self.config.plugin
        if not core.enabled:
            return {"name": "dsh_task", "content": "桥接已在配置里关闭"}

        extra_args = [arg for arg in str(core.dsh_extra_args or "").split(" ") if arg.strip()]
        cwd = str(core.dsh_cwd or "").strip() or None

        try:
            process = await asyncio.create_subprocess_exec(
                core.dsh_command,
                *extra_args,
                "--profile",
                core.dsh_profile,
                task,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return {"name": "dsh_task", "content": f"找不到 DSH 命令：{core.dsh_command}"}

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=core.dsh_timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "name": "dsh_task",
                "content": f"DSH 超过 {core.dsh_timeout_seconds} 秒还没做完，已经中断。",
            }

        answer = stdout.decode("utf-8", errors="replace").strip()
        diagnostics = stderr.decode("utf-8", errors="replace").strip()
        if not answer:
            answer = f"DSH 没有给出答复（退出码 {process.returncode}）。诊断：{diagnostics[-800:]}"
        return {"name": "dsh_task", "content": answer}

    # ===== 看视频（B站） =====

    @Tool(
        "watch_video",
        description=(
            "打开一个B站视频，读出它的字幕正文、简介、弹幕抽样和热门评论——"
            "这是「真的把内容看了」，不是只看到标题。"
            "主人发来 BV 号、av 号、bilibili 链接（含 b23.tv 短链）让你看时，必须调用它；"
            "主人只给了标题或关键词也能传，它会先搜再打开最匹配的那条。"
            "它返回的是视频素材原文：你要用自己的语气讲自己看到了什么、弹幕在聊什么、评论区在争什么，"
            "不要逐条复述字段，也不要提「素材」这个词。没看成时它也会直说没看成，别编内容。"
        ),
        parameters=[
            ToolParameterInfo(
                name="target",
                param_type=ToolParamType.STRING,
                description="BV号、av号、B站视频链接，或视频标题关键词",
                required=True,
            )
        ],
    )
    async def tool_watch_video(self, target: str = "", **kwargs: Any) -> Dict[str, Any]:
        """看一个 B站视频：字幕 + 简介 + 弹幕 + 热评。"""

        del kwargs
        cfg = self.config.video
        if not cfg.enabled:
            return {"name": "watch_video", "content": "（配置里关掉了看视频，先让主人打开 video.enabled。）"}
        if _VIDEO_IMPORT_ERROR:
            return {
                "name": "watch_video",
                "content": f"（看视频模块没装上：{_VIDEO_IMPORT_ERROR}，跟主人说一声。）",
            }

        raw = str(target or "").strip()
        if not raw:
            return {"name": "watch_video", "content": "（没说是哪个视频，问一句是 BV 号还是链接。）"}

        try:
            packet, reason = await self._open_video(raw)
        except Exception as exc:  # noqa: BLE001
            return {
                "name": "watch_video",
                "content": f"（这次没能看成：{type(exc).__name__}: {str(exc)[:200]}）",
            }

        if packet is None:
            return {
                "name": "watch_video",
                "content": f"（这次没能看成：{reason}。可以如实告诉主人没看成，别编视频内容。）",
            }

        material = render_watch(
            packet,
            desc_max_chars=int(cfg.desc_max_chars),
            danmaku_limit=int(cfg.danmaku_limit),
            related_limit=int(cfg.related_limit),
        )
        self.ctx.logger.info("[maimai_bridge] 看完了 %s《%s》", packet.bvid, packet.title)
        return {"name": "watch_video", "content": material}

    # ===== 出去看看 =====

    @Tool(
        "look_around",
        description=(
            "用自己的浏览器出去看看外面的世界，看得见网页上的内容。"
            "想看 B站/贴吧/小黑盒/Steam/知乎/微博 这些平台时用 site 简写 + what 关键词；"
            "有具体网页就直接给 url。看完之后用自己的话讲给主人听，别把原文整段贴出来。"
            "返回里如果写「没抓到」或条目为空，就是真的没看到——直接说没看到，**绝对不要自己编内容**。"
            "注意：出去看之前先跟主人说一声，主人同意了再去（除非主人已经让你随便逛）。"
        ),
        parameters=[
            ToolParameterInfo(
                name="what",
                param_type=ToolParamType.STRING,
                description="你想看/想找什么（关键词或一句话）",
                required=True,
            ),
            ToolParameterInfo(
                name="site",
                param_type=ToolParamType.STRING,
                description="平台简写：bilibili / 贴吧 / 小黑盒 / steam / 知乎 / 微博 / 豆瓣 / 小红书 / github，可留空",
                required=False,
            ),
            ToolParameterInfo(
                name="url",
                param_type=ToolParamType.STRING,
                description="直接给网址（给了就不看 site 了），可留空",
                required=False,
            ),
        ],
    )
    async def tool_look_around(
        self,
        what: str = "",
        site: str = "",
        url: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """打开无头浏览器，抓一页内容回来。"""

        del kwargs
        browse = self.config.browse
        if not browse.enabled:
            return {"name": "look_around", "content": "配置里关闭了「出去看看」（browse.enabled）"}
        if not what and not url:
            return {"name": "look_around", "content": "至少告诉我你想看什么（what），或者给个网址（url）"}

        now = asyncio.get_running_loop().time()
        self._browse_times = [stamp for stamp in self._browse_times if now - stamp < 3600]
        limit = int(browse.max_per_hour or 0)
        if limit and len(self._browse_times) >= limit:
            return {
                "name": "look_around",
                "content": f"这个小时已经出去看了 {limit} 次，先歇歇吧。",
            }
        if browse.cooldown_seconds and self._browse_times:
            gap = now - self._browse_times[-1]
            if gap < browse.cooldown_seconds:
                wait = int(browse.cooldown_seconds - gap) + 1
                return {"name": "look_around", "content": f"刚看过一次，{wait} 秒后再来。"}

        target, source = _resolve_url(site, what, url)
        recipe = _resolve_recipe(site, target)
        cookies = _cookies_for(site)
        self._browse_times.append(now)

        async with self._browse_lock:
            try:
                result = await asyncio.to_thread(
                    _browse_sync,
                    target,
                    what,
                    max(200, int(browse.max_chars or 1200)),
                    max(5, int(browse.timeout_seconds or 45)),
                    str(browse.browser_channel or ""),
                    bool(browse.headless),
                    int(browse.wait_after_load_ms or 0),
                    recipe,
                    cookies,
                )
            except Exception as exc:  # noqa: BLE001
                return {
                    "name": "look_around",
                    "content": f"没能打开「{target}」：{type(exc).__name__}: {str(exc)[:300]}",
                }

        if result.get("blocked"):
            return {
                "name": "look_around",
                "content": (
                    f"「{source}」弹出了验证（{result['blocked']}），这次没看成。"
                    "这站现在不让看，换个地方或者过会儿再来；别硬试，也别猜内容。"
                ),
            }

        payload: Dict[str, Any] = {
            "来源": source,
            "地址": result["url"],
            "标题": result["title"],
        }
        if result["items"]:
            payload["抓到的条目"] = result["items"]
            payload["共匹配"] = result["matched"]
            payload["说明"] = "这些是页面上真实存在的结果，挑你感兴趣的讲给主人听，别逐条念。"
        else:
            payload["看到的内容"] = result["excerpt"]
            payload["整页字数"] = result["total_chars"]
            if recipe:
                payload["提示"] = (
                    "这个站这次没按结构抓到条目，下面是整页正文。"
                    "如果正文里也没有相关东西，就直说没看到，绝对不要自己编内容。"
                )
        return {"name": "look_around", "content": json.dumps(payload, ensure_ascii=False)}

    # —— 斜杠命令：人手一条，绕过麦麦的自主判断 ——

    @Command(
        "look",
        description="用 /看 直接去某个平台看一眼，立刻把结果贴回来",
        pattern=r"^/看(?:\s+(?P<rest>.*))?$",
    )
    async def command_look(self, **kwargs: Any) -> Tuple[bool, str, bool]:
        """人去哪个平台看什么，直接照做，不问她要不要。"""

        stream_id = str(kwargs.get("stream_id") or "")
        rest = str((kwargs.get("matched_groups") or {}).get("rest") or "").strip()

        if not rest or rest.lower() in ("帮助", "help", "?", "？"):
            return await self._say(stream_id, _look_help_text(), "显示了 /看 的用法")

        browse = self.config.browse
        if not browse.enabled:
            return await self._say(
                stream_id,
                "「出去看看」现在是关着的，先在插件配置里打开（browse.enabled）。",
                "browse 关闭",
            )

        site = ""
        what = ""
        url = ""
        if rest.lower().startswith(("http://", "https://")):
            url = rest
        else:
            parts = rest.split(None, 1)
            head = parts[0]
            tail = parts[1].strip() if len(parts) > 1 else ""
            if _canonical_site(head) or head.lower() in SITE_TEMPLATES:
                site, what = head, tail
            else:
                what = rest

        target, _source = _resolve_url(site, what, url)
        recipe = _resolve_recipe(site, target)
        cookies = _cookies_for(site)
        canon = _canonical_site(site)
        label = SITE_LABELS.get(canon, site or "网页")

        # 抓取要几秒到十几秒，先说一句「收到了」，免得以为没反应。
        where = f"{label}「{what}」" if what else label
        await self._notify(stream_id, f"收到，去{where}看一眼，等我下喵～")

        async with self._browse_lock:
            try:
                result = await asyncio.to_thread(
                    _browse_sync,
                    target,
                    what,
                    max(200, int(browse.max_chars or 1200)),
                    max(5, int(browse.timeout_seconds or 45)),
                    str(browse.browser_channel or ""),
                    bool(browse.headless),
                    int(browse.wait_after_load_ms or 0),
                    recipe,
                    cookies,
                )
            except Exception as exc:  # noqa: BLE001
                return await self._say(
                    stream_id,
                    f"没能打开「{target}」：{type(exc).__name__}: {str(exc)[:200]}",
                    "抓取失败",
                )

        if result.get("blocked"):
            return await self._say(
                stream_id,
                f"{label}：这站现在弹验证（{result['blocked']}），没看成。过会儿再试，或者换个平台。",
                f"被 {result['blocked']} 挡住",
            )

        answer = await self._say(
            stream_id,
            _format_items(label, what, result),
            f"看了 {label}",
        )
        await self._impression(stream_id, label, what, _digest(result))
        return answer

    @Command(
        "watch_video",
        description="用 /看视频 打开一个B站视频，把字幕和评论读回来",
        pattern=r"^/看视频(?:\s+(?P<rest>.*))?$",
    )
    async def command_watch_video(self, **kwargs: Any) -> Tuple[bool, str, bool]:
        """人手触发：直接读一个视频，不经过她自己的判断。"""

        stream_id = str(kwargs.get("stream_id") or "")
        rest = str((kwargs.get("matched_groups") or {}).get("rest") or "").strip()
        cfg = self.config.video

        if not cfg.enabled:
            return await self._say(stream_id, "配置里关掉了看视频（video.enabled）。", "video 关闭")
        if not rest:
            return await self._say(
                stream_id,
                "用法：/看视频 BV号\n"
                "　　　/看视频 视频链接（b23.tv 短链也行）\n"
                "　　　/看视频 关键词（先搜再打开最匹配的那条）\n"
                "第一次用要先把 SESSDATA 填进 bili_credential.json，不然读不到字幕。",
                "显示了 /看视频 用法",
            )

        try:
            await self._notify(stream_id, f"收到，我去看看「{rest[:30]}」，读完就回来喵～")
            packet, reason = await self._open_video(rest)
        except Exception as exc:  # noqa: BLE001
            return await self._say(
                stream_id, f"没能打开：{type(exc).__name__}: {str(exc)[:200]}", "看视频失败"
            )
        if packet is None:
            return await self._say(stream_id, f"这次没看成：{reason}", "看视频失败")

        text = render_watch(
            packet,
            desc_max_chars=min(300, int(cfg.desc_max_chars)),
            danmaku_limit=min(20, int(cfg.danmaku_limit)),
            related_limit=0,
        )
        if len(text) > 1800:
            text = text[:1800].rstrip() + "\n…（到这儿吧，再长就刷屏了）"
        self.ctx.logger.info("[maimai_bridge] /看视频 完成：%s《%s》", packet.bvid, packet.title)
        answer = await self._say(stream_id, text, f"看了 {packet.bvid}")
        await self._impression(
            stream_id,
            "B站",
            f"{packet.title}",
            text[:1500],
        )
        return answer

    async def _impression(self, stream_id: str, label: str, what: str, digest: str) -> None:
        """看完之后补一句她自己的观感。

        结果列表是「看到了什么」，这条是「所以呢」——用 Host 的人格和口吻生成，
        不是复述条目。生成失败就安静跳过，不能因为补一句感想把整条命令搞挂。
        """

        if not stream_id or not str(digest or "").strip():
            return
        maisaka = getattr(self.ctx, "maisaka", None)
        reply = getattr(maisaka, "reply", None) if maisaka is not None else None
        if reply is None:
            return

        subject = f"{label}「{what}」" if what else label
        try:
            result = await reply.generate(
                stream_id,
                f"我刚自己去{subject}转了一圈，看到的是：\n{digest[:1500]}",
                format_instruction=(
                    "用你自己的口吻说一两句观感：你看到了什么、有什么想法、觉得哪里有意思或者哪里无聊。"
                    "别罗列条目，别复述原文，别用列表符号，1-2 句，像在群里随口跟人聊。"
                ),
                timeout_ms=60000,
            )
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.info("[maimai_bridge] 生成观感失败：%s", type(exc).__name__)
            return

        text = ""
        if isinstance(result, dict):
            if not result.get("success", True):
                return
            text = str(result.get("text") or "")
        elif result:
            text = str(result)
        text = text.strip()
        if text:
            await self._notify(stream_id, text)

    async def _notify(self, stream_id: str, text: str) -> None:
        """先回一句「收到了」，让发命令的人知道没被吞掉。

        抓取动辄几秒到十几秒，中间一点动静都没有会让人以为命令没生效。
        这条只是安抚，发失败了也不影响主流程。
        """

        if not stream_id:
            return
        try:
            await self.ctx.send.text(text, stream_id)
        except Exception:  # noqa: BLE001
            pass

    async def _say(self, stream_id: str, text: str, log: str) -> Tuple[bool, str, bool]:
        """把结果真的发到群里。

        命令的返回值只是给日志看的，框架不会自动发送——必须自己调 send.text。
        """

        if not stream_id:
            return False, "没有 stream_id，发不出去", False
        try:
            await self.ctx.send.text(text, stream_id)
        except Exception as exc:  # noqa: BLE001
            return False, f"发送失败：{type(exc).__name__}: {str(exc)[:200]}", False
        return True, log, True


def _look_help_text() -> str:
    """`/看` 的用法说明。"""

    sites = " ".join(
        f"{label}({name})" for name, label in SITE_LABELS.items()
    )
    return (
        "用法：\n"
        "/看 <平台> <关键词>   去那个平台搜\n"
        "/看 <关键词>          用必应搜\n"
        "/看 <网址>            直接打开\n\n"
        f"平台：{sites}\n\n"
        "登录过的平台会带着登录态去看（内容更全）。"
    )


def create_plugin() -> MaiMaiBridgePlugin:
    """创建桥插件实例。"""

    return MaiMaiBridgePlugin()
