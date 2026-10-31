# -*- coding: utf-8 -*-
"""弹一个可见浏览器让用户登录 B站，然后把登录态写进两个地方：
1. plugins/maimai_bridge/logins.json  —— 给 /看、look_around 用
2. data/plugins/maibot.bilibili-browser/bili_credential.json —— 给 bilibili_watch 读字幕用
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maibot", default="", help="MaiBot 目录；不填就自动找，也可用环境变量 MAIBOT_HOME")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--channel", default="msedge")
    args = ap.parse_args()

    maibot = find_maibot(args.maibot)
    plugin_dir = maibot / "plugins" / "maimai_bridge"
    bili_data = maibot / "data" / "plugins" / "maibot.bilibili-browser"
    profile = plugin_dir / "browser-profile"
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel=args.channel,
            headless=False,
            viewport={"width": 1280, "height": 880},
            locale="zh-CN",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=60000)
        print(f"已经在浏览器里打开 B站，请扫码登录（最多等 {args.timeout} 秒）……", flush=True)

        deadline = time.time() + args.timeout
        payload = None
        while time.time() < deadline:
            try:
                info = page.evaluate(
                    "async () => { const r = await fetch('https://api.bilibili.com/x/web-interface/nav', {credentials:'include'}); return await r.json(); }"
                )
                if (info.get("data") or {}).get("isLogin"):
                    payload = info["data"]
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3)

        if payload is None:
            print("没等到登录，这次先算了。", flush=True)
            ctx.close()
            return

        print("登录成功：" + str(payload.get("uname")) + " (uid " + str(payload.get("mid")) + ")", flush=True)
        try:
            ua = page.evaluate("navigator.userAgent")
        except Exception:  # noqa: BLE001
            ua = ""
        cookies = [c for c in ctx.cookies() if "bilibili" in (c.get("domain") or "")]
        ctx.close()

    jar = {c["name"]: c["value"] for c in cookies}
    sess = jar.get("SESSDATA", "")
    jct = jar.get("bili_jct", "")
    if not sess:
        print("奇怪：登录成功但没拿到 SESSDATA，放弃。", flush=True)
        return

    pairs = [f"SESSDATA={sess}"]
    if jct:
        pairs.append(f"bili_jct={jct}")

    logins_path = plugin_dir / "logins.json"
    data = {}
    if logins_path.exists():
        try:
            data = json.loads(logins_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
    data["bilibili"] = {"cookie": "; ".join(pairs), "ua": ""}
    logins_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已写入 " + str(logins_path), flush=True)

    if bili_data.exists():
        cred_path = bili_data / "bili_credential.json"
        cred = {}
        if cred_path.exists():
            try:
                cred = json.loads(cred_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                cred = {}
        cred["sessdata"] = sess
        cred["bili_jct"] = jct
        cred["user_agent"] = ua
        cred_path.write_text(json.dumps(cred, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写入 " + str(cred_path), flush=True)
    else:
        print("（没有装 bilibili-browser，跳过它的凭证文件）", flush=True)


if __name__ == "__main__":
    main()
