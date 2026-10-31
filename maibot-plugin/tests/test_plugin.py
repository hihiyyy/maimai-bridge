"""``plugin.py``：插件类、组件定义、斜杠命令兜底。

这里测的是「注册进 Runner 之后长什么样」—— 组件类型、命令正则、Hook 元信息。
名字写错、正则匹配不上、多出一个不会触发的 EventHandler，都该在这里崩。
"""

from __future__ import annotations

import inspect
import re

from maibot_sdk.components import collect_components

TOOL_NAMES = {
    "ask_permission",
    "bili_react",
    "bili_taste_status",
    "dsh_task",
    "end_outing",
    "look_around",
    "maimai_persona",
    "maimai_recall",
    "maimai_remember",
    "maimai_speak",
    "outing_status",
    "page_act",
    "watch_video",
}
COMMAND_NAMES = {"dshhelp", "look", "watch_video"}


def _by_type(plugin_module, instance):
    grouped = {}
    for component in collect_components(instance):
        grouped.setdefault(component["type"], {})[component["name"]] = component
    return grouped


def test_create_plugin返回插件实例(plugin_module):
    assert type(plugin_module.create_plugin()).__name__ == "MaiMaiBridgePlugin"


def test_配置模型挂对了(plugin_module):
    assert plugin_module.MaiMaiBridgePlugin.config_model.__name__ == "MaiMaiBridgeConfig"


def test_三个生命周期都在且是async(plugin_module):
    cls = plugin_module.MaiMaiBridgePlugin
    for name in ("on_load", "on_unload", "on_config_update"):
        assert hasattr(cls, name), f"缺 {name}"
        assert inspect.iscoroutinefunction(getattr(cls, name)), f"{name} 不是 async"


def test_on_config_update参数签名(plugin_module):
    params = list(inspect.signature(plugin_module.MaiMaiBridgePlugin.on_config_update).parameters)
    assert params == ["self", "scope", "config_data", "version"]


def test_组件类型分布(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    assert set(grouped["TOOL"]) == TOOL_NAMES
    assert set(grouped["COMMAND"]) == COMMAND_NAMES
    assert set(grouped["HOOK_HANDLER"]) == {"slash_bridge"}
    assert set(grouped["API"]) == {"persona"}


def test_没有EventHandler(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    assert "EVENT_HANDLER" not in grouped, "ON_MESSAGE 在主程序里没有发射点，不该有 EventHandler"


def test_命令名不带斜杠(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    for name in grouped["COMMAND"]:
        assert not name.startswith("/"), f"{name} 不应带斜杠"


def test_命令正则能匹配真实输入(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    cases = {
        "look": ["/看 B站 猫", "/看"],
        "watch_video": ["/看视频 BV1GJ411x7h7"],
        "dshhelp": ["/dshhelp"],
    }
    for name, samples in cases.items():
        pattern = grouped["COMMAND"][name]["metadata"]["command_pattern"]
        compiled = re.compile(pattern)
        for sample in samples:
            assert compiled.search(sample), f"{name} 匹配不上 {sample!r}"


def test_watch_video能取出BV号(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    pattern = grouped["COMMAND"]["watch_video"]["metadata"]["command_pattern"]
    match = re.compile(pattern).search("/看视频 BV1GJ411x7h7")
    assert match.groupdict()["rest"] == "BV1GJ411x7h7"


def test_兜底hook的元信息(plugin_module, plugin):
    grouped = _by_type(plugin_module, plugin)
    meta = grouped["HOOK_HANDLER"]["slash_bridge"]["metadata"]
    assert meta["hook"] == "chat.receive.after_process"
    assert meta["mode"] == "blocking"
    assert meta["order"] == "early"


def test_斜杠路由顺序(plugin_module, plugin):
    routes = plugin_module.MaiMaiBridgePlugin._SLASH_ROUTES
    assert [name for _, name in routes] == ["watch_video", "look", "dshhelp"]


def test_非斜杠消息不拦截(plugin_module, plugin):
    result = plugin.handle_slash_bridge(message={"processed_plain_text": "今天天气不错"})
    assert inspect.isawaitable(result)
    import asyncio

    assert asyncio.run(result) == {"action": "continue"}


def test_空消息不炸(plugin_module, plugin):
    import asyncio

    result = plugin.handle_slash_bridge(message=None)
    assert asyncio.run(result) == {"action": "continue"}


def test_能改配置(plugin_module, plugin):
    data = plugin.config_model().model_dump()
    data["plugin"]["allow_dsh"] = False
    plugin.set_plugin_config(data)
    got = plugin.config
    assert got is not None, "配置校验失败，plugin.config 返回 None"
    assert got.plugin.allow_dsh is False