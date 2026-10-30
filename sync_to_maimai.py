"""把 DSH 这边的记忆，按天同步进麦麦的长期记忆。

DSH 和麦麦共用同一个 A-Memorix 库，但「共用」不等于「知道」——DSH 这边记下的
事，麦麦不会自动看见。这个脚本补的就是那一段：读 DSH 自己的 meow-memory，
把最近新增的、适合她知道的那几类记忆，写进 A-Memorix。

同步哪些：
    topic           —— 一件事的前因后果，她最该知道
    project 的      overview / decisions / quotes / todo —— 项目目的、拍板、
                      用户原话、待办
不同步 fact / lesson / rules / soul / user：那些是「怎么操作这台机器」的知识，
或者太私人的东西，搬过去只会稀释她的记忆。

用法：
    python sync_to_maimai.py --dry-run
    python sync_to_maimai.py
    python sync_to_maimai.py --since-hours 168 --limit 30
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maimai  # noqa: E402  （同目录的桥接脚本，复用它的写入通道）

DEFAULT_STATE = Path(__file__).resolve().parent / "sync-state.json"

# 只同步这几类：事件本身，而不是操作知识
PROJECT_SUBCATEGORIES = ("overview", "decisions", "quotes", "todo")
# 她那边是「群里聊天的人」，不需要技术细节：每条压到 120 字，整批压到 1500 字
MAX_ITEM_CHARS = 120
MAX_TEXT_CHARS = 1500


def find_db(explicit: str | None) -> Path:
    """定位 DSH 的记忆库。"""

    if explicit:
        return Path(explicit).expanduser().resolve()

    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / ".dsh-meow" / "memory.db",
        Path.cwd() / ".dsh-meow" / "memory.db",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"没找到 DSH 记忆库，试过：{[str(c) for c in candidates]}")


def load_state(path: Path) -> dict:
    """读同步水位。"""

    if not path.is_file():
        return {"syncedIds": [], "lastSyncAt": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"syncedIds": [], "lastSyncAt": 0}
    if not isinstance(payload, dict):
        return {"syncedIds": [], "lastSyncAt": 0}
    payload.setdefault("syncedIds", [])
    payload.setdefault("lastSyncAt", 0)
    return payload


def save_state(path: Path, state: dict) -> None:
    """存同步水位。"""

    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_rows(db: Path, since_ms: int) -> list[dict]:
    """取出待同步的记忆行。"""

    rows: list[dict] = []
    # 只读打开，避免和 meow-memory 本体抢写锁
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            "SELECT id, content, project, updated_at FROM topic "
            "WHERE status = 'active' AND updated_at > ?",
            (since_ms,),
        ):
            rows.append(dict(row, level="topic", subcategory=""))
        placeholders = ",".join("?" * len(PROJECT_SUBCATEGORIES))
        for row in connection.execute(
            f"SELECT id, content, project, subcategory, updated_at FROM project "
            f"WHERE status = 'active' AND updated_at > ? AND subcategory IN ({placeholders})",
            (since_ms, *PROJECT_SUBCATEGORIES),
        ):
            rows.append(dict(row, level="project"))
    finally:
        connection.close()
    rows.sort(key=lambda item: item.get("updated_at") or 0)
    return rows


def format_batch(rows: list[dict], now: datetime) -> tuple[str, int]:
    """把一批记忆拼成一段她读得懂的文本，超长就少写几条（而不是拦腰截断）。"""

    lines = [f"【DSH 这边最近发生的事 · {now:%Y-%m-%d}】"]
    used = 0
    for row in rows:
        content = str(row.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > MAX_ITEM_CHARS:
            content = content[:MAX_ITEM_CHARS].rstrip("，。、；,.;") + "…"
        project = str(row.get("project") or "").strip()
        tag = project if project and project != "全局" else ""
        prefix = f"· {tag}：" if tag else "· "
        line = f"{prefix}{content}"
        if used + len(line) > MAX_TEXT_CHARS:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines), len(lines) - 1


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="把 DSH 的记忆同步进麦麦的长期记忆")
    parser.add_argument("--db", help="DSH 记忆库路径，默认找工作区的 .dsh-meow/memory.db")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="同步水位文件")
    parser.add_argument("--home", help="MaiBot 目录（透传给 maimai.py）")
    parser.add_argument("--base-url", default=maimai.DEFAULT_WEBUI, help="麦麦 WebUI 地址")
    parser.add_argument("--since-hours", type=float, default=24.0, help="回看多少小时，默认 24")
    parser.add_argument("--limit", type=int, default=8, help="最多同步几条，默认 8")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = parser.parse_args(argv)

    db = find_db(args.db)
    state_path = Path(args.state).resolve()
    state = load_state(state_path)
    synced = set(str(item) for item in state.get("syncedIds", []))

    since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
    since_ms = since.timestamp() * 1000

    rows = [row for row in fetch_rows(db, int(since_ms)) if str(row.get("id")) not in synced]
    if not rows:
        print("没有新东西要同步")
        return 0

    rows = rows[: args.limit]
    text, used = format_batch(rows, datetime.now())
    rows = rows[:used]
    if used == 0:
        print("没有能塞进一条的内容")
        return 0

    if args.dry_run:
        print(f"—— 试运行：{len(rows)} 条，{len(text)} 字符 ——")
        print(text)
        return 0

    home = maimai.resolve_home(args.home)
    code = maimai.write_memory(
        home,
        args.base_url,
        text,
        "dsh:auto-sync",
        wait=True,
        timeout=240.0,
    )
    if code != 0:
        print("写入失败，水位不动")
        return code

    state["syncedIds"] = list(synced | {str(row.get("id")) for row in rows})
    state["lastSyncAt"] = int(datetime.now(timezone.utc).timestamp() * 1000)
    # 只留最近 2000 个 id，避免文件无限长大
    state["syncedIds"] = state["syncedIds"][-2000:]
    save_state(state_path, state)
    print(f"已同步 {len(rows)} 条到麦麦的记忆")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    raise SystemExit(main())
