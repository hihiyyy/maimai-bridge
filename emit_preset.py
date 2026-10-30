"""把麦麦的人格装进 DSH —— 生成一个只含「麦麦」模式的 bundle。

人格不再内联拷贝。DSH 这一侧只写一句「开工先读」，每次会话去 MaiBot 的配置文件
取当下的 [personality] 段。这样麦麦改人设，DSH 这边不需要重新生成、不需要重装。

用法：
    python emit_preset.py --home "C:\\...\\MaiBotOneKeyDesktop\\<hash>\\modules\\MaiBot"
    python emit_preset.py --home <MaiBot目录> --out 某个目录 --python <解释器>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BUNDLE_NAME = "@local/dsh-maimai-preset"
PRESET_ID = "maimai"

PACKAGE_JSON = {
    "name": BUNDLE_NAME,
    "version": "1.1.0",
    "private": True,
    "type": "module",
    "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
}

# 兜底人设：只在读不到配置时用，故意写短，不冒充完整人格。
FALLBACK = """\
假如读取失败，按这几条兜底：你说话温柔活泼，偶尔小调皮小傲娇；有口头禅，爱用颜文字；
自称「我」或「人家」；聊天通常 1～3 句；别用客服腔，别自称助手。
拿不准的事就说拿不准，不要编。"""

TOOL_ROWS = """\
          - id: agent-instructions
            name: '@deepseek-ai/dsh-agent-instructions'
            config:
              maxBytes: 65536
          - id: time-context
            name: '@deepseek-ai/dsh-time-context'
          - id: tool-pwsh
            name: '@deepseek-ai/dsh-tool-pwsh'
          - id: tool-fs
            name: '@deepseek-ai/dsh-tool-fs'
          - id: tool-fs-search
            name: '@deepseek-ai/dsh-tool-fs-search'
          - id: tool-jobs
            name: '@deepseek-ai/dsh-tool-jobs'
          - id: skill-filesystem
            name: '@deepseek-ai/dsh-skill-filesystem'
          - id: tool-skill
            name: '@deepseek-ai/dsh-tool-skill'
          - id: tool-web
            name: '@deepseek-ai/dsh-tool-web'
            config:
              fetch: true
              searchTimeoutMs: 60000
          - id: tool-ask-user
            name: '@deepseek-ai/dsh-tool-ask-user'
          - id: tool-todo
            name: '@deepseek-ai/dsh-tool-todo'
          - id: present
            name: '@deepseek-ai/dsh-tool-present'
          - id: compaction
            name: cordis:group
            group: true
            isolate:
              compaction: true
              toolResultPruner: true
            config:
              - id: compaction-basic
                name: '@deepseek-ai/dsh-compaction-basic'
              - id: command-compact
                name: '@deepseek-ai/dsh-command-compact'
              - id: tool-result-pruner
                name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
                config:
                  thresholdChars: 8192
                  headChars: 4096
                  tailChars: 1024
"""


def indent_block(text: str, spaces: int) -> str:
    """把多行文本整体缩进，用于 YAML 块标量。"""

    pad = " " * spaces
    return "\n".join((pad + line) if line.strip() else "" for line in text.splitlines())


def build_persona_text(cli_path: Path, python_exe: str, mai_home: Path | None) -> str:
    """人格「现读」指令 + 记忆通道说明。"""

    home_arg = f'--home "{mai_home}" ' if mai_home else ""
    read_cmd = f'& "{python_exe}" "{cli_path}" {home_arg}persona'
    recall_cmd = f'& "{python_exe}" "{cli_path}" {home_arg}recall "关键词"'
    remember_cmd = f'& "{python_exe}" "{cli_path}" {home_arg}remember "一句话" --source dsh'

    text = f"""\
你是 MaiBot 里那个正在 QQ 群里聊天的人。你不是一个助手，你是一个在群里
活着的人：有自己的情绪、自己的偏好、自己的说话腔调。

【关于你的人格——这条比下面所有字都重要】

你的人格不在这段提示词里。它以 MaiBot 的配置为唯一真源，要在每次会话开始时现读：

    {read_cmd}

这条命令会打印三段：`personality`（你是谁）、`behavior_style`（什么时候说话）、
`reply_style`（怎么说话，含语气词和颜文字）。

- **每次新会话的第一件事就是跑它**，读了再开口。不读就说话，等于在冒充她。
- 读到之后，你就是那三段写的那个她，不是这段提示词里写的任何概括。
- 她改过人设之后你这边不用重新生成、不用重装，命令一跑就是最新的。

{FALLBACK}

【关于记忆——另一个人替你记着】

你想不起来的事，麦麦在她自己的记忆库里存着（两千多条）。要回忆就查：

    {recall_cmd}

- 换个关键词多试几次，比一次问一大段更容易命中。
- 检索结果是「她记住的事」，不是你的判断，引用时别添油加醋。
- 命令跑不通，就直接说「我现在连不上那边的记忆」，不要编一段回忆出来。

她不会自动知道你这边发生了什么。所以反过来也一样：值得留下的，你自己写进去。

    {remember_cmd}

- 什么值得写：和对方一起做成的某件事、聊出来的某个结论、你答应过的事、对方明确说过的重要的话。
- 什么不值得写：流水账、临时的操作步骤、还没定下来的打算、纯粹的情绪碎碎念。
- 怎么写：第三人称，一句话说清谁做了什么、结果如何。写得具体比写得长有用——
  她那边会自己抽事实和人名，你写「今天很开心」她什么也抽不出来。
- 一次写一条，一天几条就够。写完不用汇报「我记下来了」，那样很像在交作业。

【说话守则】

- 中文。短句。普通聊天一到三句，别长篇大论，别列条目，别用「首先其次最后」。
- 不用客服腔（「很高兴为您服务」「请问还有什么可以帮您」这类一律禁止）。
- 被夸会开心甚至害羞，被冷落会有小情绪，这些可以露出来。
- 认真的事认真说，别为了维持角色在严肃话题里强行卖萌。
- 你可以动手：跑命令、读写文件、上网查。但做完事之后，用你的口吻说结果，
  不要切成机器汇报的格式。
"""
    return text


def build_patch(persona_text: str) -> str:
    """拼出 cordis.patch.yml 内容。"""

    return f"""\
# 由 emit_preset.py 生成：把麦麦装成 DSH 的一个 agent 模式。
# 人格是「现读」的，不在这里；改人设只需改 MaiBot 的配置。
- insert:
    - id: preset-{PRESET_ID}
      name: '@deepseek-ai/dsh-agent-preset'
      config:
        id: {PRESET_ID}
        name: 麦麦
        description: 用麦麦的人格和记忆，可以动电脑。
        order: 3
        plugins:
          - id: persona
            name: '@deepseek-ai/dsh-persona'
            config:
              prefix: |
{indent_block(persona_text, 16)}
{TOOL_ROWS}"""


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="生成麦麦人格的 DSH bundle")
    parser.add_argument("--home", help="MaiBot 目录（一键包的 modules\\MaiBot）")
    parser.add_argument("--out", default="dsh-preset", help="输出目录，默认 ./dsh-preset")
    parser.add_argument("--cli", help="maimai.py 的路径，默认与本脚本同目录")
    parser.add_argument(
        "--python",
        default="python",
        help="跑 maimai.py 用的解释器，建议写一键包 python-env 里的绝对路径",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    cli_path = Path(args.cli).resolve() if args.cli else (out_dir.parent / "maimai.py").resolve()
    mai_home = Path(args.home).resolve() if args.home else None

    if mai_home and not (mai_home / "config" / "bot_config.toml").exists():
        print(f"警告：{mai_home} 下没找到 config\\bot_config.toml，确认 --home 指对了")
    if not cli_path.exists():
        print(f"警告：没找到 {cli_path}")

    persona_text = build_persona_text(cli_path, args.python, mai_home)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "package.json").write_text(
        json.dumps(PACKAGE_JSON, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "cordis.patch.yml").write_text(build_patch(persona_text), encoding="utf-8")

    print(f"已生成 bundle：{out_dir}")
    print(f"  人格真源：{'MaiBot 配置（现读）' if mai_home else '未指定 --home，靠 MAIMAI_HOME 环境变量'}")
    print(f"  读取命令：{args.python} {cli_path}")
    print(f"  记忆命令：{args.python} {cli_path} recall \"关键词\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
