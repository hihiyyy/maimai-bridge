"""``config.py``：配置模型。

Runner 会按这个模型生成 ``config.toml``，WebUI 会按它渲染表单 —— 所以
「字段有没有默认值」「有没有中文 label」都是可验证的硬约束，不是风格问题。
"""

from __future__ import annotations

from pydantic import BaseModel

TOP_SECTIONS = ("plugin", "browse", "video", "taste", "actions", "outing", "relay")

#: 会随环境变化、必须能从配置改的值（不允许再写死在代码里）。
TUNABLE_FIELDS = (
    ("browse", "user_agent"),
    ("browse", "block_markers"),
    ("actions", "redlines"),
    ("actions", "social_block"),
)


def _leaf_fields(model_cls):
    """只取「真正让用户填的」字段：嵌套模型的字段由子模型自己负责。"""

    for name, field in model_cls.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            continue
        yield name, field


def test_顶层七节都在(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    for section in TOP_SECTIONS:
        assert hasattr(cfg, section), f"缺少 [{section}] 节"


def test_plugin节不含宿主保留键(config_module):
    fields = config_module.BridgeCoreConfig.model_fields
    assert "enabled" not in fields
    assert "allow_dsh" in fields


def test_allow_dsh默认开启(config_module):
    assert config_module.MaiMaiBridgeConfig().plugin.allow_dsh is True


def test_配置版本是1点3点0(config_module):
    assert config_module.MaiMaiBridgeConfig().plugin.config_version == "1.3.0"


def test_配置版本字段对用户隐藏(config_module):
    extra = config_module.BridgeCoreConfig.model_fields["config_version"].json_schema_extra or {}
    assert extra.get("hidden") is True
    assert extra.get("disabled") is True


def test_所有字段都有默认值(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    for section in TOP_SECTIONS:
        sub = getattr(cfg, section)
        for name, field in _leaf_fields(type(sub)):
            assert not field.is_required(), f"{section}.{name} 没有默认值"


def test_所有叶子字段都有中文label(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    missing = []
    for section in TOP_SECTIONS:
        sub = getattr(cfg, section)
        for name, field in _leaf_fields(type(sub)):
            extra = field.json_schema_extra or {}
            label = extra.get("label")
            if not label:
                missing.append(f"{section}.{name}")
    assert not missing, f"缺 label 的字段：{missing}"


def test_每个子节都有中文标题(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    for section in TOP_SECTIONS:
        sub = getattr(cfg, section)
        assert getattr(type(sub), "__ui_label__", ""), f"[{section}] 缺 __ui_label__"


def test_会变的值都能从配置改(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    for section, name in TUNABLE_FIELDS:
        sub = getattr(cfg, section)
        assert name in type(sub).model_fields, f"[{section}].{name} 不存在"


def test_多值字段默认留空走内置默认(config_module):
    cfg = config_module.MaiMaiBridgeConfig()
    for section, name in TUNABLE_FIELDS:
        assert getattr(getattr(cfg, section), name) == "", f"[{section}].{name} 默认值应为空"