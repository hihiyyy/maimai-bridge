"""麦麦 × DeepSeek Harness 桥插件。

三件事：
1. 人格互通：把麦麦当前人格（人设 / 行为风格 / 表达风格）暴露给 DSH。
2. 记忆互通：让外部读取麦麦的长期记忆，也让外部能请求麦麦记下一件事。
3. 双向互联：麦麦可以把活交给 DSH 执行；DSH 可以请求麦麦用她自己的口吻说话。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from maibot_sdk import API, Field, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType


class BridgeCoreConfig(PluginConfigBase):
    """桥的核心配置。"""

    __ui_label__ = "桥接"
    __ui_icon__ = "link"
    __ui_order__ = 0

    config_version: str = Field(default="1.1.0", description="配置版本")

    # —— 总开关 ——
    enabled: bool = Field(default=True, description="是否启用桥接功能（关闭后 dsh_task 不可用）")

    # —— 记忆互通 ——
    recall_limit: int = Field(default=5, description="maimai_recall 默认返回条数（1-20）")
    allow_memory_write: bool = Field(
        default=True,
        description="是否允许通过 maimai_remember 让麦麦写入长期记忆",
    )

    # —— 双向互联：调 DSH ——
    dsh_command: str = Field(default="dsh", description="DSH 可执行文件（或完整路径）")
    dsh_profile: str = Field(default="headless", description="调用 DSH 时使用的 profile")
    dsh_timeout_seconds: int = Field(default=240, description="单次 DSH 任务最长等待秒数")
    dsh_cwd: str = Field(default="", description="DSH 子进程的工作目录（留空则继承 MaiBot 的）")
    dsh_extra_args: str = Field(
        default="",
        description="追加给 dsh 的参数，按空格拆开（例如 --session-id <id> 续用同一会话）",
    )

    # —— 双向互联：让麦麦说话 ——
    speak_model: str = Field(default="", description="maimai_speak 使用的模型名（留空用宿主默认）")


class MaiMaiBridgeConfig(PluginConfigBase):
    """桥插件配置。"""

    plugin: BridgeCoreConfig = Field(default_factory=BridgeCoreConfig)


class MaiMaiBridgePlugin(MaiBotPlugin):
    """麦麦 × DSH 桥插件。"""

    config_model = MaiMaiBridgeConfig

    async def on_load(self) -> None:
        """插件加载。"""
        self.ctx.logger.info("[maimai_bridge] 桥插件已加载")

    async def on_unload(self) -> None:
        """插件卸载。"""
        self.ctx.logger.info("[maimai_bridge] 桥插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        """处理配置热重载事件。

        Args:
            scope: 配置变更范围。
            config_data: 最新配置数据。
            version: 配置版本号。
        """

        self.ctx.logger.info("[maimai_bridge] 配置已更新，版本 %s，范围 %s", version, scope)
        del config_data

    # ===== 人格互通 =====

    @API("persona", description="读取麦麦当前人格设定，供 DSH 侧同步使用", version="1")
    async def api_persona(self) -> Dict[str, Any]:
        """返回麦麦当前的人格、行为风格与表达风格。"""

        current = await self.ctx.personality.get_current()
        return {"ok": True, "persona": current}

    @Tool(
        "maimai_persona",
        description="读取麦麦当前的人格设定（她是谁、怎么说话）。需要以麦麦的身份行动时先调这个。",
    )
    async def tool_persona(self, **kwargs: Any) -> Dict[str, Any]:
        """把人格设定作为工具结果返回。"""

        del kwargs
        current = await self.ctx.personality.get_current()
        return {"name": "maimai_persona", "content": json.dumps(current, ensure_ascii=False)}

    # ===== 记忆互通 =====

    @Tool(
        "maimai_recall",
        description="检索麦麦的长期记忆，看看她以前记住过什么。要回忆旧事时使用。",
        parameters=[
            ToolParameterInfo(name="query", param_type=ToolParamType.STRING, description="检索关键词", required=True),
            ToolParameterInfo(name="limit", param_type=ToolParamType.INTEGER, description="返回条数，默认 5", required=False),
        ],
    )
    async def tool_recall(self, query: str = "", limit: int = 0, **kwargs: Any) -> Dict[str, Any]:
        """调用宿主的知识检索能力，读麦麦的长期记忆。"""

        del kwargs
        if not query:
            return {"name": "maimai_recall", "content": "检索词不能为空"}

        default_limit = self.config.plugin.recall_limit or 5
        count = int(limit) if limit else int(default_limit)
        count = max(1, min(20, count))

        result = await self.ctx.knowledge.search(query, count)
        return {"name": "maimai_recall", "content": str(result)}

    @Tool(
        "maimai_remember",
        description="让麦麦自己把一件事记进长期记忆。只在确实值得长期记住时使用。",
        parameters=[
            ToolParameterInfo(name="content", param_type=ToolParamType.STRING, description="要记住的内容", required=True),
            ToolParameterInfo(name="stream_id", param_type=ToolParamType.STRING, description="聊天流 ID", required=True),
        ],
    )
    async def tool_remember(self, content: str = "", stream_id: str = "", **kwargs: Any) -> Dict[str, Any]:
        """通过主动任务让麦麦走一遍她自己的记忆写入流程。"""

        del kwargs
        if not content or not stream_id:
            return {"name": "maimai_remember", "content": "content 与 stream_id 都不能为空"}

        if not self.config.plugin.allow_memory_write:
            return {"name": "maimai_remember", "content": "配置里关闭了记忆写入（allow_memory_write）"}

        await self.ctx.maisaka.proactive.trigger(
            stream_id,
            intent=f"把这件事记进你的长期记忆，别回复任何人：{content}",
            reason="maimai_bridge 记忆写入",
        )
        return {"name": "maimai_remember", "content": "已交给麦麦处理记忆写入"}

    # ===== 双向互联 =====

    @Tool(
        "maimai_speak",
        description="让麦麦用她自己的口吻写一段话（不会自动发送）。需要『像麦麦那样说』时使用。",
        parameters=[
            ToolParameterInfo(name="stream_id", param_type=ToolParamType.STRING, description="聊天流 ID", required=True),
            ToolParameterInfo(name="reference", param_type=ToolParamType.STRING, description="要写成什么样、说了什么材料", required=True),
        ],
    )
    async def tool_speak(self, stream_id: str = "", reference: str = "", **kwargs: Any) -> Dict[str, Any]:
        """复用宿主的人格与表达选择，生成一段麦麦口吻的文本。"""

        del kwargs
        if not stream_id or not reference:
            return {"name": "maimai_speak", "content": "stream_id 与 reference 都不能为空"}

        result = await self.ctx.maisaka.reply.generate(
            stream_id,
            reference,
            model_name=str(self.config.plugin.speak_model or ""),
        )
        return {"name": "maimai_speak", "content": json.dumps(result, ensure_ascii=False)}

    @Tool(
        "dsh_task",
        description="把一件需要动手的活交给 DeepSeek Harness 去执行（它能操作电脑、查资料、写文件）。",
        parameters=[
            ToolParameterInfo(name="task", param_type=ToolParamType.STRING, description="交给 DSH 的任务描述", required=True),
        ],
    )
    async def tool_dsh_task(self, task: str = "", **kwargs: Any) -> Dict[str, Any]:
        """以一次性进程调用 DSH headless，返回它的最终答复。"""

        del kwargs
        if not task:
            return {"name": "dsh_task", "content": "任务描述不能为空"}

        core = self.config.plugin
        if not core.enabled:
            return {"name": "dsh_task", "content": "桥接已在配置里关闭"}

        extra_args = [arg for arg in str(core.dsh_extra_args or "").split(" ") if arg.strip()]
        cwd = str(core.dsh_cwd or "").strip() or None

        try:
            process = await asyncio.create_subprocess_exec(
                core.dsh_command,
                *extra_args,
                "--profile",
                core.dsh_profile,
                task,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return {"name": "dsh_task", "content": f"找不到 DSH 命令：{core.dsh_command}"}

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=core.dsh_timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "name": "dsh_task",
                "content": f"DSH 超过 {core.dsh_timeout_seconds} 秒还没做完，已经中断。",
            }

        answer = stdout.decode("utf-8", errors="replace").strip()
        diagnostics = stderr.decode("utf-8", errors="replace").strip()
        if not answer:
            answer = f"DSH 没有给出答复（退出码 {process.returncode}）。诊断：{diagnostics[-800:]}"
        return {"name": "dsh_task", "content": answer}


def create_plugin() -> MaiMaiBridgePlugin:
    """创建桥插件实例。"""

    return MaiMaiBridgePlugin()
