# -*- coding: utf-8 -*-
"""弹一个可见浏览器让用户自己登录某个平台，登录成功后把 Cookie 存进 logins.json。

B站 会额外写一份给「刷B站」插件用的 bili_credential.json（读字幕要它）。

用法：
    python cookie_login.py --site bilibili --maibot <MaiBot 目录>
    python cookie_login.py --site xhs --timeout 300 --debug

为什么要验证：光看 Cookie 里有没有登录标志键不够——小红书这类站**没登录也会种
`web_session`**，于是「浏览器刚打开就说登录成功」。所以这里加了两层：

1. `VERIFY`：能用「我是谁」接口的站，直接带着 Cookie 去问一次，真的登录了才认。
2. 没接口的站（小红书 / 豆瓣）：对比刚打开时的 Cookie 基线，标志键的值**变了**才算。
"""

import argparse
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def find_maibot(override: str = "") -> Path:
    """按「命令行 → 环境变量 → 一键包默认位置 → 用户主目录」的顺序找 MaiBot 目录。

    一键包的目录名是个随机 hash，写死在代码里换台机器就废了，所以这里运行时现找。
    找不到就抛 SystemExit 并提示怎么指定，不静默退到某个可能不存在的路径。
    """
    if override:
        path = Path(override).expanduser()
        if path.is_dir():
            return path
        raise SystemExit(f"--maibot 指向的目录不存在：{path}")

    env = os.environ.get("MAIBOT_HOME", "").strip()
    if env:
        path = Path(env).expanduser()
        if path.is_dir():
            return path
        raise SystemExit(f"环境变量 MAIBOT_HOME 指向的目录不存在：{path}")

    candidates = [
        Path.home() / "AppData" / "Roaming" / "MaiBotOneKeyDesktop",
        Path.home() / "MaiBot",
        Path("/opt/maibot"),
    ]
    onekey_roots = [c for c in candidates if "MaiBotOneKeyDesktop" in str(c)]
    for root in onekey_roots:
        if not root.is_dir():
            continue
        # 一键包：<root>\<hash>\modules\MaiBot
        for child in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
            cand = child / "modules" / "MaiBot"
            if cand.is_dir():
                return cand
    for root in candidates:
        if "MaiBotOneKeyDesktop" not in str(root) and root.is_dir():
            return root

    raise SystemExit(
        "找不到 MaiBot 目录。请用 --maibot 指定，或设环境变量 MAIBOT_HOME，"
        "例如：--maibot \"C:\\Users\\<你>\\AppData\\Roaming\\MaiBotOneKeyDesktop\\<hash>\\modules\\MaiBot\""
    )

#: 每个平台：怎么打开、认哪个域名、看到哪个 cookie 才算「可能登录了」。
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

#: 各平台的「我是谁」验证：(地址, 类型, 判断函数)。没有的走 Cookie 基线对比。
VERIFY = {
    "bilibili": (
        "https://api.bilibili.com/x/web-interface/nav",
        "json",
        lambda d: bool((d.get("data") or {}).get("isLogin")),
    ),
    "tieba": (
        "https://tieba.baidu.com/dc/common/tbs",
        "json",
        lambda d: d.get("is_login") == 1,
    ),
    "zhihu": (
        "https://www.zhihu.com/api/v4/me",
        "json",
        lambda d: bool(d.get("id")),
    ),
    "weibo": (
        "https://weibo.com/ajax/profile/info",
        "json",
        lambda d: d.get("code") == 100000,
    ),
    "github": (
        "https://api.github.com/user",
        "json",
        lambda d: bool(d.get("login")),
    ),
    "xiaoheihe": (
        "https://api.xiaoheihe.cn/account/get_user_info/",
        "json",
        lambda d: d.get("status") == "ok",
    ),
    "steam": (
        "https://store.steampowered.com/account/",
        "text",
        lambda t: "account_name" in t,
    ),
}


def matching(cookies, domains):
    """只留这些域名下的 cookie。"""

    picked = []
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").lstrip(".")
        if any(domain == d or domain.endswith("." + d) for d in domains):
            picked.append(cookie)
    return picked


def verify_login(ctx, site_key, debug=False):
    """带着当前 Cookie 去问一次「我是谁」。返回 True / False / None（问不出来）。"""

    spec = VERIFY.get(site_key)
    if not spec:
        return None
    url, kind, check = spec
    try:
        resp = ctx.request.get(url, timeout=15000)
    except Exception as exc:  # noqa: BLE001
        if debug:
            print(f"  [verify] {url} 请求失败：{type(exc).__name__}", flush=True)
        return None
    if kind == "json":
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            if debug:
                print(f"  [verify] {url} 返回的不是 JSON（{resp.status}）", flush=True)
            return False
        try:
            ok = bool(check(data))
        except Exception:  # noqa: BLE001
            ok = False
        if debug:
            print(f"  [verify] {url} -> {ok}（{str(data)[:120]}）", flush=True)
        return ok
    try:
        ok = bool(check(resp.text() or ""))
    except Exception:  # noqa: BLE001
        ok = False
    if debug:
        print(f"  [verify] {url} -> {ok}", flush=True)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="bilibili", choices=sorted(SITES.keys()))
    ap.add_argument("--maibot", default="", help="MaiBot 目录；不填就自动找，也可用环境变量 MAIBOT_HOME")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--channel", default="msedge")
    ap.add_argument("--debug", action="store_true", help="打印每轮 cookie 名和验证结果")
    args = ap.parse_args()

    site = SITES[args.site]
    label = site["label"]
    maibot = find_maibot(args.maibot)
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
            f"**看到自己的头像或昵称再等两秒**，脚本会自己发现并保存，然后关窗口。",
            flush=True,
        )

        deadline = time.time() + args.timeout
        baseline = None
        round_no = 0
        while time.time() < deadline:
            round_no += 1
            try:
                current = ctx.cookies()
            except Exception:  # noqa: BLE001
                current = []
            picked = matching(current, site["domains"])
            jar_now = {c.get("name"): c.get("value") for c in picked if c.get("name")}

            if baseline is None:
                baseline = dict(jar_now)
                if args.debug:
                    print(f"  [基线] {sorted(baseline)}", flush=True)

            present = [m for m in site["markers"] if m in jar_now]
            if present:
                if args.debug:
                    print(f"  第 {round_no} 轮：看到 {present}，开始验证", flush=True)
                verdict = verify_login(ctx, args.site, debug=args.debug)
                if verdict is True:
                    cookies = picked
                    break
                if verdict is None:
                    # 没有验证接口（小红书 / 豆瓣）：要求标志键的值相对打开时变过
                    changed = [m for m in present if jar_now.get(m) != baseline.get(m)]
                    if changed:
                        cookies = picked
                        print(f"  （{label} 没有验证接口，靠 Cookie 变化判定：{changed}）", flush=True)
                        break
                    if args.debug:
                        print(f"  第 {round_no} 轮：Cookie 还在，但值跟刚打开时一模一样，应该还没登录", flush=True)
                elif args.debug:
                    print(f"  第 {round_no} 轮：验证没通过，继续等", flush=True)
            elif args.debug and round_no % 5 == 0:
                print(f"  第 {round_no} 轮：还没有登录标志 cookie（现有 {len(jar_now)} 条）", flush=True)
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
