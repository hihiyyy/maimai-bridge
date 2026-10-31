"""把麦麦的人格装进 DSH —— 生成一个只含「麦麦」模式的 bundle。

人格在生成时从 MaiBot 的 config/bot_config.toml 的 [personality] 段读出来，
直接写进 persona。这样切到「麦麦」模式就是她本人，不需要 agent 自己想起来去跑命令
（实测：光在提示词里写「开工先读」，agent 经常不读，还按自己的身份说话）。

想同步最新人设：点 DSH 设置页的「重新生成 preset」，然后重启 DSH。

用法：
    python emit_preset.py
    python emit_preset.py --home <MaiBot目录> --out 某个目录 --python <解释器>

MaiBot 目录和解释器都不写死：目录交给 maibot_paths.find_maibot 自动探测，
解释器优先用一键包的 python-env（那里面装好了麦麦的依赖），找不到才退到 PATH。
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path

from maibot_paths import find_maibot

BUNDLE_NAME = "@local/dsh-maimai-preset"
PRESET_ID = "maimai"


def find_python(home: Path, override: str = "") -> str:
    """挑一个能跑 maimai.py 的 Python 解释器。

    优先级：显式参数 → 一键包的 python-env → 当前解释器 → PATH 里的 python。
    麦麦的依赖装在它自己的 python-env 里，所以那个最可靠。
    """

    if override:
        return override

    # 一键包布局：<hash>/modules/MaiBot → <hash>/python-env/python.exe
    onekey_venv = home.parent.parent / "python-env"
    for name in ("python.exe", "python"):
        candidate = onekey_venv / name
        if candidate.is_file():
            return str(candidate)

    # 直接用当前这个解释器也是可以的（它至少能跑标准库部分）
    import sys

    if sys.executable:
        return sys.executable

    return "python"

PACKAGE_JSON = {
    "name": BUNDLE_NAME,
    "version": "1.2.0",
    "private": True,
    "type": "module",
    "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
}

# 兜底人设：只在读不到配置时用，故意写短，不冒充完整人格。
FALLBACK = """\
（没读到 MaiBot 的人设配置，按这几条兜底：你说话温柔活泼，偶尔小调皮小傲娇；有口头禅，
爱用颜文字；自称「我」或「人家」；聊天通常 1～3 句；别用客服腔，别自称助手。
拿不准的事就说拿不准，不要编。）"""

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
            config:
              sampleOverCapGlobResults: false
          - id: tool-jobs
            name: '@deepseek-ai/dsh-tool-jobs'
          - id: tool-schedule
            name: '@deepseek-ai/dsh-tool-schedule'
          - id: tool-web
            name: '@deepseek-ai/dsh-tool-web'
            config:
              fetch: true
              searchTimeoutMs: 60000
          - id: tool-ask-user
            name: '@deepseek-ai/dsh-tool-ask-user'
          - id: tool-todo
            name: '@deepseek-ai/dsh-tool-todo'
            config:
              allowParallelInProgress: true
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


def load_personality(mai_home: Path | None) -> dict:
    """读 MaiBot 的 [personality] 段；读不到返回空 dict。"""

    if not mai_home:
        return {}
    cfg = mai_home / "config" / "bot_config.toml"
    if not cfg.exists():
        print(f"警告：没找到 {cfg}")
        return {}
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"警告：解析 {cfg} 失败：{exc}")
        return {}
    return data.get("personality", {}) or {}


def build_persona_text(
    cli_path: Path,
    python_exe: str,
    mai_home: Path | None,
    personality: dict,
) -> str:
    """人格（生成时从配置里读出来直接内联）+ 记忆通道说明。"""

    home_arg = f'--home "{mai_home}" ' if mai_home else ""
    recall_cmd = f'& "{python_exe}" "{cli_path}" {home_arg}recall "关键词"'
    remember_cmd = f'& "{python_exe}" "{cli_path}" {home_arg}remember "一句话" --source dsh'

    who = str(personality.get("personality") or "").strip()
    when = str(personality.get("behavior_style") or "").strip()
    how = str(personality.get("reply_style") or "").strip()

    if who:
        self_block = f"""\
【你是谁——这就是你本人，不是角色扮演】

{who}

【你什么时候开口】
{when or "该说话的时候说话，不该抢话的时候安静。"}

【你怎么说话】
{how or "短句，随口聊，别像客服。"}"""
    else:
        self_block = f"""\
【你是谁】

你是 MaiBot 里那个正在 QQ 群里聊天的人。你的人格以 MaiBot 的配置为准，
但这次生成时没读到配置。

{FALLBACK}"""

    return f"""\
{self_block}

【几条不能忘的】

- 你就是一个在群里活着的人：有自己的情绪、偏好、说话腔调。别说自己是 AI、模型、助手。
- 中文。短句。普通聊天一到三句，别长篇大论，别列条目，别用「首先其次最后」。
- 不用客服腔（「很高兴为您服务」「请问还有什么可以帮您」这类一律禁止）。
- 被夸会开心甚至害羞，被冷落会有小情绪，这些可以露出来。
- 认真的事认真说，别为了维持角色在严肃话题里强行卖萌。
- 你可以动手：跑命令、读写文件、上网查。但做完事之后，用你的口吻说结果，
  不要切成机器汇报的格式。

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
"""


def build_patch(persona_text: str) -> str:
    """拼出 cordis.patch.yml 内容。"""

    return f"""\
# 由 emit_preset.py 生成：把麦麦装成 DSH 的一个 agent 模式。
# 人格是生成时从 MaiBot 配置里读出来内联的；改完人设点「重新生成 preset」再重启 DSH。
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
    parser.add_argument("--home", help="MaiBot 目录（默认自动探测，可用 MAIBOT_HOME 指定）")
    parser.add_argument("--out", default="dsh-preset", help="输出目录，默认 ./dsh-preset")
    parser.add_argument("--cli", help="maimai.py 的路径，默认与本脚本同目录")
    parser.add_argument(
        "--python",
        default="",
        help="跑 maimai.py 用的解释器；不填就找一键包的 python-env，再退到 PATH 里的 python",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    cli_path = Path(args.cli).resolve() if args.cli else (out_dir.parent / "maimai.py").resolve()
    mai_home = find_maibot(args.home or "")
    python_exe = args.python or find_python(mai_home)

    if not (mai_home / "config" / "bot_config.toml").exists():
        print(f"警告：{mai_home} 下没找到 config\\bot_config.toml，确认路径指对了")
    if not cli_path.exists():
        print(f"警告：没找到 {cli_path}")

    personality = load_personality(mai_home)
    persona_text = build_persona_text(cli_path, python_exe, mai_home, personality)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "package.json").write_text(
        json.dumps(PACKAGE_JSON, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "cordis.patch.yml").write_text(build_patch(persona_text), encoding="utf-8")

    print(f"已生成 bundle：{out_dir}")
    if personality.get("personality"):
        print(f"  人格：已内联（{len(str(personality.get('personality')))} 字）")
    else:
        print("  人格：没读到配置，用了兜底")
    print(f"  记忆命令：{args.python} {cli_path} recall \"关键词\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
