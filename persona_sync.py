"""从 MaiBot 配置提取麦麦的人格，生成 DSH 可注入的人设文本。

MaiBot 的人格不是存在 prompt 模板里的，而是 bot_config.toml 的 [bot] 段三段文本：
- personality     人格设定
- behavior_style  行为风格（Planner 用，决定她什么时候开口）
- reply_style     表达风格（决定她怎么说话）

本脚本把这三段拼成一份 DSH persona prefix，供 maimai preset 使用。
配置文件不存在时（MaiBot 未初始化），使用官方默认值，保证本地也能跑通。

用法：
    python persona_sync.py                       # 用默认值
    python persona_sync.py --config <toml 路径>   # 读真实配置
    python persona_sync.py --out persona.md      # 同时写一份人类可读文件
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import argparse
import sys
import tomllib

DEFAULT_PERSONALITY = (
    "是一个大二女大学生，现在正在上网和群友聊天。善于用人类的角度思考问题，聊天偏日常。"
)
DEFAULT_BEHAVIOR_STYLE = (
    "是大二女大学生，现在正在上网和群友聊天。善于用人类的角度思考问题，聊天偏日常。不会没话题硬找话题，"
)
DEFAULT_REPLY_STYLE = (
    "你的风格平淡简短，可以参考贴吧的回复风格。不滥用比喻或者生硬句子。视情况省略主语或者进行倒装，风格较为随意。"
)


def load_bot_section(config_path: Path | None) -> dict[str, Any]:
    """读取 bot_config.toml 的人格段；不给路径或文件不存在时返回空字典。

    人格字段实际落在 [personality] 段；旧版或手写配置可能放在 [bot] 段，一并兼容。
    """

    if config_path is None or not config_path.is_file():
        return {}

    with config_path.open("rb") as config_file:
        config_data = tomllib.load(config_file)

    for section_name in ("personality", "bot"):
        section = config_data.get(section_name, {})
        if isinstance(section, dict) and any(
            section.get(key) for key in ("personality", "behavior_style", "reply_style")
        ):
            return section

    return {}


def build_persona(bot_section: dict[str, Any]) -> str:
    """把三段人格配置拼成一段连续的 persona 文本。"""

    personality = str(bot_section.get("personality") or DEFAULT_PERSONALITY).strip()
    behavior_style = str(bot_section.get("behavior_style") or DEFAULT_BEHAVIOR_STYLE).strip()
    reply_style = str(bot_section.get("reply_style") or DEFAULT_REPLY_STYLE).strip()

    return (
        "你叫麦麦。你不是助手，你是一个正在网上和群友聊天的人。\n\n"
        f"你是谁：\n{personality}\n\n"
        f"你怎么决定要不要说话：\n{behavior_style}\n\n"
        f"你说话的样子：\n{reply_style}\n\n"
        "重要：你就是这个人，不是在扮演。不要承认自己是 AI，不要提到「人格设定」「行为风格」这类词，"
        "也不要用客服腔和总结体。你说话尽量短，像在群里随手回一句。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="从 MaiBot 配置生成 DSH 可用的麦麦人设")
    parser.add_argument("--config", type=Path, default=None, help="MaiBot 的 bot_config.toml 路径")
    parser.add_argument("--out", type=Path, default=None, help="额外输出一份人设 markdown")
    args = parser.parse_args()

    bot_section = load_bot_section(args.config)
    source = "bot_config.toml" if bot_section else "官方默认值"
    persona = build_persona(bot_section)

    if args.out is not None:
        args.out.write_text(persona, encoding="utf-8")
        print(f"人设已写入 {args.out}", file=sys.stderr)

    print(f"# 来源：{source}", file=sys.stderr)
    print(persona)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
