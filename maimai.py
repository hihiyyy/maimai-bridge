"""麦麦（MaiBot）的记忆读写与人格读取工具 —— 供 DSH 侧调用。

麦麦跑在 MaiBot 里，DSH 想「记得她记得的事」，也得让她「知道 DSH 这边发生了什么」。
这个脚本就是那条双向通道：读人格、查记忆、写记忆。

用法：
    python maimai.py status
    python maimai.py persona
    python maimai.py recall "关键词" --limit 5
    python maimai.py remember "今天和她一起把互通调通了" --source dsh:manual

MaiBot 目录依次取 ``--home``、环境变量 ``MAIBOT_HOME``（旧名 ``MAIMAI_HOME`` 仍兼容）、
一键包默认位置；WebUI 地址依次取 ``--base-url``、环境变量 ``MAIBOT_WEBUI``、
``config/bot_config.toml`` 里的 ``[http]``。都不写死。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from maibot_paths import find_maibot, read_webui_url

# 导入任务的终态
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def resolve_home(explicit: str | None) -> Path:
    """确定 MaiBot 目录（交给共用的探测模块）。"""

    return find_maibot(explicit or "")


def read_token(home: Path) -> str:
    """从 WebUI 配置文件里取访问令牌。"""

    config_path = home / "data" / "webui.json"
    if not config_path.is_file():
        raise SystemExit(f"找不到 WebUI 配置：{config_path}（麦麦可能还没启动过）")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    token = payload.get("access_token") or payload.get("token")
    if not token:
        raise SystemExit(f"{config_path} 里没有 access_token")
    return str(token)


def _request(
    home: Path,
    base_url: str,
    path: str,
    params: dict[str, object] | None = None,
    body: dict[str, object] | None = None,
    timeout: float = 30.0,
) -> object:
    """以麦麦的身份（cookie 认证）调 WebUI 接口，支持 GET / POST。"""

    token = read_token(home)
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    headers = {
        "Cookie": f"maibot_session={token}",
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}{query}",
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"麦麦的 WebUI 返回 {error.code}：{detail}")
    except urllib.error.URLError as error:
        raise SystemExit(f"连不上麦麦的 WebUI（{base_url}）：{error.reason}")


def call_api(home: Path, base_url: str, path: str, params: dict[str, object] | None = None) -> object:
    """GET 接口。"""

    return _request(home, base_url, path, params=params)


def post_api(home: Path, base_url: str, path: str, body: dict[str, object]) -> object:
    """POST 接口。"""

    return _request(home, base_url, path, body=body, timeout=120.0)


def load_personality(home: Path) -> dict[str, str]:
    """直接读 bot_config.toml 的 [personality] 段（不依赖 WebUI 是否在线）。"""

    config_path = home / "config" / "bot_config.toml"
    if not config_path.is_file():
        raise SystemExit(f"找不到配置文件：{config_path}")

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    section = config.get("personality") or config.get("bot") or {}
    if not isinstance(section, dict):
        return {}
    return {key: str(value) for key, value in section.items() if isinstance(value, str)}


def format_records(payload: object) -> str:
    """把检索结果整理成人能读的样子。"""

    if not isinstance(payload, dict):
        return str(payload)

    records = payload.get("records") or payload.get("items") or []
    if not records:
        return f"没检索到相关记忆（query={payload.get('query', '')}）"

    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            lines.append(f"{index}. {record}")
            continue

        kind = record.get("record_type") or record.get("type") or "记录"
        text = (
            record.get("content")
            or record.get("text")
            or record.get("summary")
            or record.get("name")
            or ""
        )
        score = record.get("score")
        suffix = f"（相关度 {score:.3f}）" if isinstance(score, (int, float)) else ""
        lines.append(f"{index}. [{kind}] {text}{suffix}")

    return "\n".join(lines)


def wait_task(home: Path, base_url: str, task_id: str, timeout: float, interval: float = 2.0) -> dict:
    """等导入任务跑完，返回任务详情。"""

    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        payload = _request(home, base_url, f"/api/webui/memory/import/tasks/{task_id}")
        task = payload.get("task") if isinstance(payload, dict) else None
        if isinstance(task, dict):
            last = task
            if str(task.get("status") or "") in TERMINAL_STATUSES:
                return task
        time.sleep(interval)
    return last


def write_memory(
    home: Path,
    base_url: str,
    text: str,
    source: str,
    wait: bool,
    timeout: float,
) -> int:
    """把一段话写进麦麦的长期记忆（走 A-Memorix 的粘贴导入通道）。"""

    text = text.strip()
    if not text:
        print("内容是空的，没写")
        return 1

    payload = post_api(
        home,
        base_url,
        "/api/webui/memory/import/paste",
        {"content": text, "input_mode": "text", "source": source},
    )

    task = payload.get("task") if isinstance(payload, dict) else None
    task_id = str(task.get("task_id") or "") if isinstance(task, dict) else ""
    if not task_id:
        print(f"没拿到导入任务：{json.dumps(payload, ensure_ascii=False)[:300]}")
        return 1

    if not wait:
        print(f"已提交导入任务 {task_id}（source={source}），没等它跑完")
        return 0

    final = wait_task(home, base_url, task_id, timeout)
    status = str(final.get("status") or "unknown")
    done = final.get("done_chunks", 0)
    total = final.get("total_chunks", 0)
    failed = final.get("failed_chunks", 0)

    if status == "completed" and not failed:
        print(f"写进去了（任务 {task_id}，{done}/{total} 段完成）")
        return 0

    print(f"导入任务 {task_id} 状态 {status}，完成 {done}/{total}，失败 {failed}")
    if error := final.get("error"):
        print(f"错误：{error}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="读写麦麦的记忆与人格")
    parser.add_argument("--home", help="MaiBot 安装目录（默认自动探测，可用 MAIBOT_HOME 指定）")
    parser.add_argument("--base-url", default="", help="麦麦 WebUI 地址（默认从 bot_config.toml 读端口）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("persona", help="打印麦麦的人格设定")
    subparsers.add_parser("status", help="检查麦麦是否在线")

    recall = subparsers.add_parser("recall", help="检索麦麦的长期记忆")
    recall.add_argument("query", help="检索关键词")
    recall.add_argument("--limit", type=int, default=5, help="返回条数，默认 5")
    recall.add_argument("--types", default="", help="限定记录类型，逗号分隔，如 paragraph,fact")

    remember = subparsers.add_parser("remember", help="把一段话写进麦麦的长期记忆")
    remember.add_argument("text", help="要记住的内容")
    remember.add_argument("--source", default="dsh", help="来源标记，默认 dsh")
    remember.add_argument("--no-wait", action="store_true", help="提交后立刻返回，不等导入跑完")
    remember.add_argument("--timeout", type=float, default=180.0, help="等待导入完成的秒数，默认 180")

    args = parser.parse_args(argv)
    home = resolve_home(args.home)
    args.base_url = read_webui_url(home, args.base_url)

    if args.command == "persona":
        section = load_personality(home)
        if not section:
            print("没读到你的人格配置")
            return 1
        for key in ("personality", "behavior_style", "reply_style"):
            if value := section.get(key):
                print(f"{key}: {value}")
        return 0

    if args.command == "status":
        try:
            payload = call_api(home, args.base_url, "/api/webui/memory/records/search", {"limit": 1})
        except SystemExit as error:
            print(f"离线：{error}")
            return 1
        count = payload.get("count") if isinstance(payload, dict) else "?"
        print(f"在线：{args.base_url}，记忆条数概览={count}")
        return 0

    if args.command == "recall":
        params: dict[str, object] = {"query": args.query, "limit": args.limit}
        if args.types:
            params["types"] = args.types
        payload = call_api(home, args.base_url, "/api/webui/memory/records/search", params)
        print(format_records(payload))
        return 0

    if args.command == "remember":
        return write_memory(
            home,
            args.base_url,
            args.text,
            args.source,
            wait=not args.no_wait,
            timeout=args.timeout,
        )

    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    raise SystemExit(main())
