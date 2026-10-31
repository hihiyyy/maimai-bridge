"""MaiBot 目录与 WebUI 地址的探测工具 —— 仓库里几个脚本共用。

为什么不写死：

- 一键包的安装目录名是个随机 hash（每个新装的实例都不一样），
  写进代码里换台机器就废了；
- WebUI 端口在 ``config/bot_config.toml`` 的 ``[http].port`` 里，
  用户完全可以改，八百一千这类数字不该散落在各个脚本里。

统一规则：**显式参数 → 环境变量 → 自动探测 → 常见位置**，
每一级如果「给了值但对不上」就直接报错退出，绝不静默退到某个
可能不存在的路径上——那种静默失败最难查。

环境变量：

- ``MAIBOT_HOME``   MaiBot 安装目录（旧名 ``MAIMAI_HOME`` 仍兼容）
- ``MAIBOT_WEBUI``  麦麦 WebUI 地址，如 ``http://127.0.0.1:8001``

用法::

    from maibot_paths import find_maibot, read_webui_url

    home = find_maibot(args.maibot)
    base_url = read_webui_url(home, args.base_url)
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

#: 一键包的固定前缀（它下面还有一层随机 hash 目录）。
_ONEKEY_ROOT = Path("AppData") / "Roaming" / "MaiBotOneKeyDesktop"

#: 找不到时的兜底提示。
_HINT = (
    "请用 --maibot 指定，或设环境变量 MAIBOT_HOME，例如：\n"
    '  set MAIBOT_HOME=C:\\Users\\<你>\\AppData\\Roaming\\MaiBotOneKeyDesktop\\<hash>\\modules\\MaiBot'
)


def _env_path(*names: str) -> str:
    """按顺序读环境变量，返回第一个非空的。"""

    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def find_maibot(override: str = "") -> Path:
    """确定 MaiBot 安装目录（即包含 ``config/``、``plugins/`` 的那一层）。

    Args:
        override: 命令行传来的目录；空字符串表示交给自动探测。

    Raises:
        SystemExit: 指定了目录但不存在，或一个候选都找不到。
    """

    if override:
        path = Path(override).expanduser()
        if path.is_dir():
            return path
        raise SystemExit(f"--maibot 指向的目录不存在：{path}")

    env = _env_path("MAIBOT_HOME", "MAIMAI_HOME")
    if env:
        path = Path(env).expanduser()
        if path.is_dir():
            return path
        raise SystemExit(f"环境变量 MAIBOT_HOME 指向的目录不存在：{path}")

    # 一键包：<home>/AppData/Roaming/MaiBotOneKeyDesktop/<hash>/modules/MaiBot
    onekey = Path.home() / _ONEKEY_ROOT
    if onekey.is_dir():
        # 装了多个实例时取最新的那个（hash 目录名是时间无关的，按 mtime 更稳）
        children = sorted(
            (p for p in onekey.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for child in children:
            candidate = child / "modules" / "MaiBot"
            if candidate.is_dir():
                return candidate

    # 其他常见放法
    for candidate in (Path.home() / "MaiBot", Path("/opt/maibot")):
        if candidate.is_dir():
            return candidate

    raise SystemExit(f"找不到 MaiBot 目录。{_HINT}")


def read_webui_url(home: Path, override: str = "") -> str:
    """确定麦麦 WebUI 的基址。

    优先级：显式参数 → ``MAIBOT_WEBUI`` 环境变量 →
    ``<home>/config/bot_config.toml`` 的 ``[http]`` → ``http://127.0.0.1:8001``。
    """

    if override:
        return override.rstrip("/")

    env = os.environ.get("MAIBOT_WEBUI", "").strip()
    if env:
        return env.rstrip("/")

    config_path = Path(home) / "config" / "bot_config.toml"
    if config_path.is_file():
        try:
            with config_path.open("rb") as handle:
                config = tomllib.load(handle)
            http = config.get("http") or {}
            port = http.get("port")
            hosts = http.get("host") or []
            # 监听 * 或 0.0.0.0 时，本机访问仍走回环地址
            host = "127.0.0.1"
            for candidate in hosts:
                if isinstance(candidate, str) and candidate not in {"0.0.0.0", "::", "*"}:
                    host = candidate
                    break
            if isinstance(port, int) and port > 0:
                return f"http://{host}:{port}"
        except (OSError, tomllib.TOMLDecodeError, TypeError):
            # 配置读不出来不该拦住整个脚本，退回默认端口
            pass

    return "http://127.0.0.1:8001"
