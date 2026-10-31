"""测试夹具：把插件当成一个真实的「包」加载进来。

裸 ``spec_from_file_location`` 加载带 ``from .config import ...`` 的多文件插件会
直接 ImportError —— 必须给 ``submodule_search_locations`` 并先注册 ``sys.modules``，
这和 Runner 里 ``PluginLoader`` 的做法一致（见 ``plugin_loader.py:592-611``）。
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

PLUGIN_DIR = Path(__file__).parents[1]
REPO_ROOT = PLUGIN_DIR.parent

#: 让 ``import maibot_paths`` 能命中仓库根目录那份（三个脚本共用）。
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_PKG_NAME = "_maibot_plugin_lirick_maimai_bridge"


def _load_plain(name: str, filename: str) -> ModuleType:
    """加载不依赖 maibot_sdk 的纯模块，用独立模块名避免与外部同名包相撞。"""

    full = f"_maimai_bridge_{name}"
    cached = sys.modules.get(full)
    if cached is not None:
        return cached
    spec = spec_from_file_location(full, PLUGIN_DIR / filename)
    module = module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def plugin_module() -> ModuleType:
    """隔离加载 plugin.py，返回模块对象（整个会话只加载一次）。"""

    cached = sys.modules.get(_PKG_NAME)
    if cached is not None:
        return cached
    spec = spec_from_file_location(
        _PKG_NAME,
        PLUGIN_DIR / "plugin.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = module_from_spec(spec)
    module.__path__ = [str(PLUGIN_DIR)]
    sys.modules[_PKG_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def constants() -> ModuleType:
    """``constants.py``：默认值 + ``resolve_*``。"""

    return _load_plain("constants", "constants.py")


@pytest.fixture(scope="session")
def sites() -> ModuleType:
    """``sites.py``：站点知识表 + 翻译函数。"""

    return _load_plain("sites", "sites.py")


@pytest.fixture(scope="session")
def config_module() -> ModuleType:
    """``config.py``：配置模型（依赖 maibot_sdk，单独加载）。"""

    full = "_maimai_bridge_config"
    cached = sys.modules.get(full)
    if cached is not None:
        return cached
    spec = spec_from_file_location(full, PLUGIN_DIR / "config.py")
    module = module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def plugin(plugin_module: ModuleType):
    """一个刚创建、还没跑 on_load 的插件实例（已注入最小可用的 Context）。"""

    from maibot_sdk.context import PluginContext

    async def fake_rpc(*args, **kwargs):
        return {"success": True}

    instance = plugin_module.create_plugin()
    instance._set_context(PluginContext("lirick.maimai-bridge", rpc_call=fake_rpc))
    return instance


@pytest.fixture()
def fake_maibot(tmp_path: Path) -> Path:
    """搭一个最小可用的 MaiBot 目录（只造探测逻辑真正会看的那些文件）。"""

    home = tmp_path / "modules" / "MaiBot"
    (home / "config").mkdir(parents=True)
    (home / "plugins").mkdir(parents=True)
    (home / "config" / "bot_config.toml").write_text(
        '[http]\nhost = ["0.0.0.0"]\nport = 8001\n',
        encoding="utf-8",
    )
    return home