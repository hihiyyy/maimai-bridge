"""``maibot_paths.py``：MaiBot 目录与 WebUI 端口的探测。

一键包的目录名是随机 hash、WebUI 端口也可能被改过 —— 这两个值都不该写死在代码里。
这里测的是探测顺序和「指错了必须炸」的行为。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

maibot_paths = pytest.importorskip("maibot_paths")


@pytest.fixture()
def no_env(monkeypatch):
    """清掉所有相关环境变量，避免开发机上的设置影响断言。"""

    for name in ("MAIBOT_HOME", "MAIMAI_HOME", "MAIBOT_WEBUI"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture()
def home_only(no_env, tmp_path):
    """把 ``Path.home()`` 指向一个空目录，断掉对真实用户主目录的依赖。"""

    no_env.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def _make_onekey(home: Path, hash_name: str) -> Path:
    """在 ``<home>/AppData/Roaming/MaiBotOneKeyDesktop/<hash>`` 下造一个模块目录。"""

    modules = home / "AppData" / "Roaming" / "MaiBotOneKeyDesktop" / hash_name / "modules" / "MaiBot"
    (modules / "config").mkdir(parents=True)
    return modules


def test_显式参数最优先(no_env, tmp_path):
    target = tmp_path / "自定义" / "MaiBot"
    target.mkdir(parents=True)
    no_env.setenv("MAIBOT_HOME", str(tmp_path / "别的"))
    assert maibot_paths.find_maibot(str(target)) == target


def test_显式参数不存在要报错(no_env, tmp_path):
    with pytest.raises(SystemExit):
        maibot_paths.find_maibot(str(tmp_path / "根本没有这个目录"))


def test_环境变量优先于自动探测(no_env, home_only):
    _make_onekey(home_only, "abc123")
    target = home_only / "手动指定" / "MaiBot"
    target.mkdir(parents=True)
    no_env.setenv("MAIBOT_HOME", str(target))
    assert maibot_paths.find_maibot() == target


def test_环境变量指错必须失败(no_env, home_only):
    _make_onekey(home_only, "abc123")
    no_env.setenv("MAIBOT_HOME", str(home_only / "不存在"))
    with pytest.raises(SystemExit):
        maibot_paths.find_maibot()


def test_兼容旧环境变量名(no_env, home_only):
    target = home_only / "旧名" / "MaiBot"
    target.mkdir(parents=True)
    no_env.setenv("MAIMAI_HOME", str(target))
    assert maibot_paths.find_maibot() == target


def test_自动探测一键包(home_only):
    modules = _make_onekey(home_only, "d3c27d5c70b9")
    assert maibot_paths.find_maibot() == modules


def test_多个一键包实例按修改时间取最新(home_only):
    old = _make_onekey(home_only, "aaa111")
    new = _make_onekey(home_only, "zzz999")
    os.utime(old, (1_600_000_000, 1_600_000_000))
    os.utime(new, (1_700_000_000, 1_700_000_000))
    assert maibot_paths.find_maibot() == new


def test_全都找不到要报错(no_env, home_only):
    with pytest.raises(SystemExit):
        maibot_paths.find_maibot()


def test_webui_url_显式参数最优先(home_only):
    assert maibot_paths.read_webui_url(home_only, "http://10.0.0.5:9000") == "http://10.0.0.5:9000"


def test_webui_url_环境变量其次(no_env, home_only):
    no_env.setenv("MAIBOT_WEBUI", "http://127.0.0.1:7777")
    assert maibot_paths.read_webui_url(home_only) == "http://127.0.0.1:7777"


def test_webui_url_从配置文件读端口(home_only):
    cfg = home_only / "config"
    cfg.mkdir(parents=True)
    (cfg / "bot_config.toml").write_text(
        '[http]\nhost = ["127.0.0.1"]\nport = 8123\n', encoding="utf-8"
    )
    assert maibot_paths.read_webui_url(home_only) == "http://127.0.0.1:8123"


@pytest.mark.parametrize("host_line", ['host = ["0.0.0.0"]', 'host = ["::"]', 'host = ["*"]'])
def test_webui_url_通配地址回落本机(home_only, host_line):
    cfg = home_only / "config"
    cfg.mkdir(parents=True)
    (cfg / "bot_config.toml").write_text(f"[http]\n{host_line}\nport = 8123\n", encoding="utf-8")
    assert maibot_paths.read_webui_url(home_only) == "http://127.0.0.1:8123"


def test_webui_url_配置缺失兜底8001(home_only):
    assert maibot_paths.read_webui_url(home_only) == "http://127.0.0.1:8001"


def test_webui_url_配置写坏不炸(home_only):
    cfg = home_only / "config"
    cfg.mkdir(parents=True)
    (cfg / "bot_config.toml").write_text("这根本不是 toml [[[", encoding="utf-8")
    assert maibot_paths.read_webui_url(home_only) == "http://127.0.0.1:8001"