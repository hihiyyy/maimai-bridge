# -*- coding: utf-8 -*-
"""弹一个可见浏览器让用户自己登录某个平台，登录成功后把 Cookie 存进 logins.json。

B站 会额外写一份给「刷B站」插件用的 bili_credential.json（读字幕要它）。

用法：
    python cookie_login.py --site bilibili --maibot <MaiBot 目录>
    python cookie_login.py --site tieba --timeout 300

判断「登录成功」的方式统一是看 Cookie 里有没有该站的登录标志键——这比猜页面
DOM 稳，因为各站改版改不到自己的登录凭证上。
"""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_MAIBOT = r"C:\Users\lirick\AppData\Roaming\MaiBotOneKeyDesktop\d3c27d5c70b9\modules\MaiBot"

#: 每个平台：怎么打开、认哪个域名、看到哪个 cookie 就算登录成功。
SITES = {
    "bilibili": {
        "label": "B站",
        "home": "https://www.bilibili.com/",
        "domains": ("bilibili.com",),
        "markers": ("SESSDATA",),
    },
    "tieba": {
        "label": "贴吧",
        "home": "https://tieba.baidu.com/",
        "domains": ("baidu.com",),
        "markers": ("BDUSS",),
    },
    "xiaoheihe": {
        "label": "小黑盒",
        "home": "https://www.xiaoheihe.cn/app/bbs/home",
        "domains": ("xiaoheihe.cn",),
        "markers": ("heybox_id", "heybox_uid", "heybox_token"),
    },
    "steam": {
        "label": "Steam",
        "home": "https://store.steampowered.com/login/",
        "domains": ("steampowered.com", "steamcommunity.com"),
        "markers": ("steamLoginSecure",),
    },
    "zhihu": {
        "label": "知乎",
        "home": "https://www.zhihu.com/signin",
        "domains": ("zhihu.com",),
        "markers": ("z_c0",),
    },
    "weibo": {
        "label": "微博",
        "home": "https://weibo.com/login.php",
        "domains": ("weibo.com", "weibo.cn"),
        "markers": ("SUB",),
    },
    "douban": {
        "label": "豆瓣",
        "home": "https://www.douban.com/",
        "domains": ("douban.com",),
        "markers": ("dbcl2",),
    },
    "xhs": {
        "label": "小红书",
        "home": "https://www.xiaohongshu.com/",
        "domains": ("xiaohongshu.com",),
        "markers": ("web_session",),
    },
    "github": {
        "label": "GitHub",
        "home": "https://github.com/login",
        "domains": ("github.com",),
        "markers": ("user_session",),
    },
}


def matching(cookies, domains):
    """只留这些域名下的 cookie。"""

    picked = []
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").lstrip(".")
        if any(domain == d or domain.endswith("." + d) for d in domains):
            picked.append(cookie)
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="bilibili", choices=sorted(SITES.keys()))
    ap.add_argument("--maibot", default=DEFAULT_MAIBOT)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    site = SITES[args.site]
    label = site["label"]
    maibot = Path(args.maibot)
    plugin_dir = maibot / "plugins" / "maimai_bridge"
    profile = plugin_dir / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)

    print(f"正在打开 {label}：{site['home']}", flush=True)
    cookies = None
    ua = ""

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=args.channel,
            headless=False,
            viewport={"width": 1280, "height": 880},
            locale="zh-CN",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(site["home"], wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001
            print(f"打开页面时出错（不影响继续等）：{exc}", flush=True)

        print(
            f"请在这个浏览器窗口里登录 {label}（最多等 {args.timeout} 秒）。"
            "登录成功后会自动保存，然后窗口自己关。",
            flush=True,
        )

        deadline = time.time() + args.timeout
        found = []
        while time.time() < deadline:
            try:
                current = ctx.cookies()
            except Exception:  # noqa: BLE001
                current = []
            picked = matching(current, site["domains"])
            names = {c.get("name") for c in picked}
            if any(marker in names for marker in site["markers"]):
                cookies = picked
                break
            time.sleep(3)

        if cookies is None:
            print(f"没等到 {label} 的登录状态，这次先算了。", flush=True)
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass
            return

        try:
            ua = page.evaluate("navigator.userAgent")
        except Exception:  # noqa: BLE001
            ua = ""
        print(f"{label} 登录成功，拿到 {len(cookies)} 条 cookie。", flush=True)
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass

    jar = {c["name"]: c["value"] for c in cookies if c.get("name")}
    pair_text = "; ".join(f"{k}={v}" for k, v in jar.items())
    if not pair_text:
        print("奇怪：判断登录成功了，但没取到 cookie，放弃。", flush=True)
        return

    logins_path = plugin_dir / "logins.json"
    data = {}
    if logins_path.exists():
        try:
            data = json.loads(logins_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
    if not isinstance(data, dict):
        data = {}
    data[args.site] = {"cookie": pair_text, "ua": ua or ""}
    logins_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {logins_path}（{args.site}，{len(pair_text)} 字符）", flush=True)

    # B站 额外供一份给「刷B站」插件读字幕
    if args.site == "bilibili":
        bili_data = maibot / "data" / "plugins" / "maibot.bilibili-browser"
        if bili_data.exists():
            cred_path = bili_data / "bili_credential.json"
            cred = {}
            if cred_path.exists():
                try:
                    cred = json.loads(cred_path.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    cred = {}
            cred["sessdata"] = jar.get("SESSDATA", "")
            cred["bili_jct"] = jar.get("bili_jct", "")
            cred["user_agent"] = ua or ""
            cred_path.write_text(
                json.dumps(cred, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"已写入 {cred_path}", flush=True)


if __name__ == "__main__":
    main()
