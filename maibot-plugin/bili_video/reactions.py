# -*- coding: utf-8 -*-
"""B站「写操作」接口：点赞、收藏。

单独成文件的原因：``client.py`` 是从上游插件（DomainDream/maibot-bilibili-browser）
移植来的**只读**客户端，我们不往里面加东西，免得以后跟着上游升级时冲突。
这里只用它的 ``httpx.AsyncClient``（已经带了 SESSDATA / bili_jct / buvid 指纹）和 csrf。

所有写操作都要 csrf，值就是 cookie 里的 ``bili_jct``。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

API_NAV = "https://api.bilibili.com/x/web-interface/nav"
API_RELATION = "https://api.bilibili.com/x/web-interface/archive/relation"
API_LIKE = "https://api.bilibili.com/x/web-interface/archive/like"
API_FAV_DEAL = "https://api.bilibili.com/x/v3/fav/resource/deal"
API_FAV_FOLDERS = "https://api.bilibili.com/x/v3/fav/folder/created/list-all"

REFERER = "https://www.bilibili.com/"

# B站错误码里最常撞的几条，翻成人话
_CODE_HINT = {
    -101: "没登录（SESSDATA 失效）",
    -111: "csrf 校验失败（bili_jct 不对或过期）",
    -400: "请求参数不对",
    -403: "被风控拦了，过一会儿再试",
    -404: "视频不存在或已删除",
    -650: "操作太频繁",
    65002: "这个收藏夹不存在（或者不是你的）",
    65004: "已经收藏过了",
    10003: "已经点过赞了",
}


class ReactionError(RuntimeError):
    """写操作失败，message 里是已经翻成人话的原因。"""


async def _request(
    http: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {"Referer": REFERER, "Origin": "https://www.bilibili.com"}
    try:
        resp = await http.request(method, url, params=params, data=data, headers=headers)
    except httpx.HTTPError as exc:
        raise ReactionError(f"网络请求失败: {exc}") from exc
    if resp.status_code in (412, 429):
        raise ReactionError(f"被风控拦了（HTTP {resp.status_code}），过一会儿再试")
    if resp.status_code >= 400:
        raise ReactionError(f"HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ReactionError("返回的不是 JSON（大概率被风控或登录失效）") from exc
    if not isinstance(payload, dict):
        raise ReactionError("返回结构异常")
    code = payload.get("code")
    try:
        code_int = int(code)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        code_int = 0
    if code_int != 0:
        hint = _CODE_HINT.get(code_int) or str(payload.get("message") or "未知错误")
        raise ReactionError(f"{hint}（code={code_int}）")
    return payload


async def whoami(http: httpx.AsyncClient) -> Tuple[int, str]:
    """返回 (mid, 昵称)；未登录时 mid 为 0。"""

    payload = await _request(http, "GET", API_NAV)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    try:
        mid = int(data.get("mid") or 0)
    except (TypeError, ValueError):
        mid = 0
    return mid, str(data.get("uname") or "")


async def relation(http: httpx.AsyncClient, bvid: str) -> Dict[str, int]:
    """这条视频我赞过/收藏过没有。返回 ``{"like": 0/1, "favorite": 0/1, "coin": n}``。"""

    payload = await _request(http, "GET", API_RELATION, params={"bvid": bvid})
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    out: Dict[str, int] = {}
    for key in ("like", "favorite", "coin", "attention"):
        try:
            out[key] = int(data.get(key) or 0)
        except (TypeError, ValueError):
            out[key] = 0
    return out


async def set_like(http: httpx.AsyncClient, csrf: str, aid: int, *, liked: bool = True) -> None:
    """点赞 / 取消赞。"""

    if not csrf:
        raise ReactionError("没有 bili_jct，点赞需要它（重新登录一次就有了）")
    await _request(
        http,
        "POST",
        API_LIKE,
        data={"aid": str(aid), "like": "1" if liked else "0", "csrf": csrf},
    )


async def fav_folders(http: httpx.AsyncClient, mid: int) -> List[Dict[str, Any]]:
    """列出这个人自己建的收藏夹（含「默认收藏夹」）。"""

    payload = await _request(http, "GET", API_FAV_FOLDERS, params={"up_mid": str(mid), "web_location": "333.1387"})
    items = (payload.get("data") or {}).get("list") if isinstance(payload.get("data"), dict) else None
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            fid = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if fid <= 0:
            continue
        out.append(
            {
                "id": fid,
                "title": str(item.get("title") or ""),
                "count": int(item.get("media_count") or 0),
            }
        )
    return out


async def add_to_favorites(http: httpx.AsyncClient, csrf: str, aid: int, media_id: int) -> None:
    """收藏到指定收藏夹（``type=2`` 表示视频）。"""

    if not csrf:
        raise ReactionError("没有 bili_jct，收藏需要它（重新登录一次就有了）")
    await _request(
        http,
        "POST",
        API_FAV_DEAL,
        data={
            "rid": str(aid),
            "type": "2",
            "add_media_ids": str(media_id),
            "csrf": csrf,
        },
    )


def pick_folder(
    folders: List[Dict[str, Any]], wanted: str
) -> Tuple[Optional[Dict[str, Any]], str]:
    """按名字或 id 挑收藏夹；``wanted`` 为空时用「默认收藏夹」。

    Returns:
        ``(选中的收藏夹或 None, 说明)``。
    """

    if not folders:
        return None, "这个账号一个收藏夹都没有"
    want = (wanted or "").strip()
    if not want:
        for item in folders:
            if "默认" in item["title"]:
                return item, f"用默认收藏夹「{item['title']}」"
        first = folders[0]
        return first, f"没有叫「默认」的，用第一个「{first['title']}」"
    for item in folders:
        if item["title"] == want:
            return item, f"按名字找到「{item['title']}」"
    for item in folders:
        if str(item["id"]) == want:
            return item, f"按 id 找到「{item['title']}」"
    names = "、".join(item["title"] for item in folders[:6])
    return None, f"没有叫「{want}」的收藏夹，现有的是：{names}"
