"""maimai_bridge 的配置模型。

配置结构的唯一来源就是这里：Runner 会据此生成默认 ``config.toml``、向 WebUI
导出可渲染的表单，并在字段新增时自动补齐旧配置。

约定（MaiBot 插件规范）：

- 每个字段都必须有默认值，``list``/``dict``/嵌套模型用 ``default_factory``。
- ``[plugin]`` 节里的 ``enabled`` 是宿主保留键（顶部启停开关与 Runner 激活门禁
  共用），**不要在这里声明**；需要自己的开关就换个名字（本插件用 ``allow_dsh``）。
- 字段的 ``description`` 会直接渲染成人话标签，写用户能看懂的句子。
- 会随环境变化的值（UA、拦截词、站点）一律留成配置项，不在代码里写死。
"""

from __future__ import annotations

from maibot_sdk import Field, PluginConfigBase


class BridgeCoreConfig(PluginConfigBase):
    """桥接总开关与 DSH 调用参数。"""

    __ui_label__ = "桥接"
    __ui_icon__ = "link"
    __ui_order__ = 0

    config_version: str = Field(
        default="1.3.0",
        description="配置版本，由插件维护，请勿手动修改",
        json_schema_extra={"hidden": True, "disabled": True, "label": "配置版本"},
    )

    admin_qq: str = Field(
        default="",
        description="全局管理员 QQ 号，逗号分隔多个。填了之后，批准出门这类「得主人点头」的事只认这些人；留空就是谁发起申请等谁回",
        json_schema_extra={"label": "管理员 QQ"},
    )

    allow_dsh: bool = Field(
        default=True,
        description="是否允许麦麦把活交给 DSH 执行（关掉后 dsh_task 不可用）",
        json_schema_extra={"label": "允许调用 DSH"},
    )

    recall_limit: int = Field(default=5, description="maimai_recall 默认返回条数（1-20）", json_schema_extra={"label": "记忆检索条数"})
    allow_memory_write: bool = Field(
        default=True,
        description="是否允许通过 maimai_remember 让麦麦写入长期记忆",
        json_schema_extra={"label": "允许写入记忆"},
    )

    dsh_command: str = Field(default="dsh", description="DSH 可执行文件（或完整路径）", json_schema_extra={"label": "DSH 命令"})
    dsh_profile: str = Field(default="headless", description="调用 DSH 时使用的 profile", json_schema_extra={"label": "DSH profile"})
    dsh_timeout_seconds: int = Field(default=240, description="单次 DSH 任务最长等待秒数", json_schema_extra={"label": "DSH 超时（秒）"})
    dsh_cwd: str = Field(default="", description="DSH 子进程的工作目录（留空则继承 MaiBot 的）", json_schema_extra={"label": "DSH 工作目录"})
    dsh_extra_args: str = Field(
        default="",
        description="追加给 dsh 的参数，按空格拆开（例如 --session-id <id> 续用同一会话）",
        json_schema_extra={"label": "DSH 额外参数"},
    )

    speak_model: str = Field(default="", description="maimai_speak 使用的模型名（留空用宿主默认）", json_schema_extra={"label": "代发模型"})


class BridgeBrowseConfig(PluginConfigBase):
    """「出去看看」：无头浏览器。"""

    __ui_label__ = "出去看看"
    __ui_icon__ = "compass"
    __ui_order__ = 10

    enabled: bool = Field(default=True, description="是否允许麦麦自己用浏览器出去看（关掉后 look_around 不可用）", json_schema_extra={"label": "启用浏览器"})
    browser_channel: str = Field(
        default="msedge",
        description="浏览器通道：msedge（系统 Edge）/ chrome / 留空改用 playwright 自带 chromium",
        json_schema_extra={"label": "浏览器通道"},
    )
    headless: bool = Field(default=True, description="是否无头运行（关掉会弹窗口，会占你的屏）", json_schema_extra={"label": "无头模式"})
    timeout_seconds: int = Field(default=45, description="打开页面最长等待秒数", json_schema_extra={"label": "超时（秒）"})
    max_chars: int = Field(default=1200, description="返回给麦麦的正文最多多少字", json_schema_extra={"label": "正文上限（字）"})
    wait_after_load_ms: int = Field(default=1200, description="页面加载后再等多久（毫秒），给动态内容一点时间", json_schema_extra={"label": "加载后等待（毫秒）"})
    cooldown_seconds: int = Field(default=20, description="两次 look_around 之间至少间隔多少秒（防止她连刷）", json_schema_extra={"label": "冷却（秒）"})
    max_per_hour: int = Field(default=12, description="每小时最多出去看几次（0 表示不限制）", json_schema_extra={"label": "每小时上限"})
    use_profile: bool = Field(
        default=True,
        description="是否用持久浏览器 profile（和扫码登录共用同一份 cookie，登录过的站进来就是登录态）",
        json_schema_extra={"label": "持久 profile"},
    )
    profile_dir: str = Field(
        default="",
        description="持久 profile 目录，留空用插件数据目录下的 browser-profile",
        json_schema_extra={"label": "profile 目录"},
    )
    user_agent: str = Field(
        default="",
        description="浏览时使用的 UA，留空用内置的桌面 Edge UA。站点改版导致被识别时可在这里换成别的",
        json_schema_extra={"label": "User-Agent"},
    )
    block_markers: str = Field(
        default="",
        description="页面出现哪些字样就判定为「被反爬挡住」，逗号分隔。留空用内置默认（百度安全验证/滑动验证/Just a moment 等）",
        json_schema_extra={"label": "反爬判定词"},
    )


class BridgeVideoConfig(PluginConfigBase):
    """「看视频」：走 B站 接口，读字幕 / 简介 / 弹幕 / 热评。"""

    __ui_label__ = "看视频"
    __ui_icon__ = "play-circle"
    __ui_order__ = 20

    enabled: bool = Field(default=True, description="是否允许看视频（关掉后 watch_video 不可用）", json_schema_extra={"label": "启用看视频"})
    sessdata: str = Field(
        default="",
        description="B站 SESSDATA（填了才读得到字幕；留空则读凭证文件 bili_credential.json）",
        json_schema_extra={"label": "SESSDATA"},
    )
    bili_jct: str = Field(default="", description="B站 bili_jct（可选，留空则读凭证文件）", json_schema_extra={"label": "bili_jct"})
    user_agent: str = Field(default="", description="自定义 UA（留空用内置的桌面 Edge UA）", json_schema_extra={"label": "User-Agent"})
    credential_file: str = Field(
        default="",
        description="凭证文件路径（绝对路径或相对插件数据目录），留空用数据目录下的 bili_credential.json",
        json_schema_extra={"label": "凭证文件"},
    )
    subtitle: bool = Field(default=True, description="是否读字幕（这是「真的看懂视频」的关键）", json_schema_extra={"label": "读字幕"})
    subtitle_max_chars: int = Field(default=3000, description="字幕最多取多少字", json_schema_extra={"label": "字幕上限（字）"})
    desc_max_chars: int = Field(default=500, description="简介最多取多少字", json_schema_extra={"label": "简介上限（字）"})
    comment_limit: int = Field(default=12, description="热门评论取几条", json_schema_extra={"label": "热评条数"})
    danmaku: bool = Field(default=True, description="是否抽样弹幕", json_schema_extra={"label": "抽样弹幕"})
    danmaku_limit: int = Field(default=40, description="弹幕抽样几条", json_schema_extra={"label": "弹幕条数"})
    related_limit: int = Field(default=4, description="相关推荐取几条", json_schema_extra={"label": "相关推荐条数"})
    proxy: str = Field(default="", description="代理地址，如 http://127.0.0.1:7890（留空直连）", json_schema_extra={"label": "代理地址"})
    timeout_seconds: int = Field(default=20, description="单次接口请求超时秒数", json_schema_extra={"label": "超时（秒）"})


class BridgeTasteConfig(PluginConfigBase):
    """「喜欢就自己动手」：看完一个东西觉得好，自己点赞 / 收藏。"""

    __ui_label__ = "喜欢就自己动手"
    __ui_icon__ = "heart"
    __ui_order__ = 30

    enabled: bool = Field(default=True, description="是否允许她自己点赞 / 收藏（关掉后只会嘴上说喜欢，不动手）", json_schema_extra={"label": "启用点赞收藏"})
    auto_like: bool = Field(default=True, description="遇到喜欢的能不能自己点赞", json_schema_extra={"label": "自动点赞"})
    auto_fav: bool = Field(default=True, description="遇到特别喜欢的能不能自己收藏", json_schema_extra={"label": "自动收藏"})
    fav_folder: str = Field(
        default="",
        description="收藏到哪个收藏夹（留空 = 默认收藏夹；填名字或 id 都行）",
        json_schema_extra={"label": "收藏夹"},
    )
    daily_limit: int = Field(default=10, description="每天最多自己动手几次（0 表示不限制）", json_schema_extra={"label": "每日上限"})
    cooldown_seconds: int = Field(default=300, description="两次动手之间至少隔多少秒（防止一激动连点一串）", json_schema_extra={"label": "冷却（秒）"})
    require_reason: bool = Field(
        default=True,
        description="是否必须说明「为什么喜欢」。开着能挡住没头没脑的乱点，她也更容易记住自己喜欢什么",
        json_schema_extra={"label": "必须说理由"},
    )
    dry_run: bool = Field(
        default=False,
        description="试运行：只在日志和返回里说「我本来想赞这个」，不真的发出去",
        json_schema_extra={"label": "试运行"},
    )


class BridgeActionsConfig(PluginConfigBase):
    """「动手」：允许她在页面上做哪些动作，做到哪一步为止。"""

    __ui_label__ = "动手"
    __ui_icon__ = "mouse-pointer-click"
    __ui_order__ = 15

    enabled: bool = Field(default=True, description="是否允许她在页面上动手（点、填、翻页、滚动）", json_schema_extra={"label": "启用页面动作"})
    allowed: str = Field(
        default="read,click,type,scroll,press,back",
        description="允许的动作，逗号分隔。可选：read / click / type / scroll / press / back。想收紧就删几个",
        json_schema_extra={"label": "允许的动作"},
    )
    max_steps: int = Field(default=6, description="一次请求最多做几步（防止她一路点下去停不下来）", json_schema_extra={"label": "最多步数"})
    step_wait_ms: int = Field(default=800, description="每步之后等多久（毫秒），给页面一点反应时间", json_schema_extra={"label": "每步等待（毫秒）"})
    timeout_seconds: int = Field(default=20, description="单步最长等待秒数", json_schema_extra={"label": "超时（秒）"})
    redlines: str = Field(
        default="",
        description="额外禁止的动作词（逗号分隔）。留空用内置的付款/购买/改密码等红线，填了就覆盖内置清单",
        json_schema_extra={"label": "额外红线词"},
    )
    social_block: str = Field(
        default="",
        description="额外禁止的「对外说话」动作词（逗号分隔）。留空用内置的评论/弹幕/私信/转发清单",
        json_schema_extra={"label": "禁言的词"},
    )


class BridgeOutingConfig(PluginConfigBase):
    """「出门要打招呼」：她想去远处看看，先问一声，批了才去，到点回来。"""

    __ui_label__ = "出门要打招呼"
    __ui_icon__ = "key-round"
    __ui_order__ = 35

    enabled: bool = Field(default=True, description="是否启用「先申请再出去」这套流程", json_schema_extra={"label": "启用出门申请"})
    owner_ids: str = Field(
        default="",
        description="能批准的人（QQ 号，逗号分隔）。留空 = 谁发起申请就等谁回，也就是「问谁等谁」",
        json_schema_extra={"label": "批准人"},
    )
    default_minutes: int = Field(default=30, description="申请时不说话，默认批多少分钟", json_schema_extra={"label": "默认时长（分钟）"})
    max_minutes: int = Field(default=120, description="一次最多能批多少分钟（超过按这个算）", json_schema_extra={"label": "最长时长（分钟）"})
    daily_limit: int = Field(default=3, description="每天最多能出去几次（0 表示不限制）", json_schema_extra={"label": "每日上限"})
    approve_words: str = Field(
        default="可以,去吧,同意,准了,行,好,批准,ok,OK,嗯,去吧喵",
        description="主人回哪些词算批准（逗号分隔，含其中一个就算）",
        json_schema_extra={"label": "批准词"},
    )
    deny_words: str = Field(
        default="不行,不许,别去,不准,拒绝,不去,no,NO,算了吧",
        description="主人回哪些词算拒绝（先查拒绝再查批准）",
        json_schema_extra={"label": "拒绝词"},
    )
    report_on_end: bool = Field(default=True, description="回来时是否主动汇报一句她看到了什么", json_schema_extra={"label": "回来汇报"})
    report_max_chars: int = Field(default=600, description="回来汇报最多多少字", json_schema_extra={"label": "汇报字数上限"})

    # —— 自己想起来（第 3 期）——
    auto_enabled: bool = Field(
        default=False,
        description="是否让她自己想起来出去：定时叫醒她，由她决定要不要申请。默认关，开了才会动",
        json_schema_extra={"label": "自己想起来"},
    )
    auto_stream_id: str = Field(
        default="",
        description="在哪个群叫她。留空 = 用她自己记下的「最近说过话的群」（第一次在群里说话就自动记下来，不用填）",
        json_schema_extra={"label": "叫醒的群"},
    )
    auto_windows: str = Field(
        default="12:00-14:00,18:00-23:00",
        description="什么时段可以叫她（逗号分隔，跨夜写成 18:00-09:00 也行）",
        json_schema_extra={"label": "叫醒时段"},
    )
    auto_daily_limit: int = Field(default=2, description="每天最多叫醒几次（0 表示不限制）", json_schema_extra={"label": "每日叫醒次数"})
    auto_cooldown_minutes: int = Field(default=180, description="两次叫醒之间至少隔多少分钟", json_schema_extra={"label": "叫醒间隔（分钟）"})
    auto_intent: str = Field(default="", description="叫醒她时说的那句话，留空用默认文案", json_schema_extra={"label": "叫醒话术"})


class BridgeRelayConfig(PluginConfigBase):
    """「替她说一句」：DSH 没有发送权，只有写台词权。

    DSH 在答复里写 ``[[speak]]台词[[/speak]]``，这里负责把关——
    多长、说不说、发不发，都在这儿定；它自己没法直接往群里发东西。
    """

    __ui_label__ = "替她说一句"
    __ui_icon__ = "send"
    __ui_order__ = 40

    enabled: bool = Field(
        default=True,
        description="允许 DSH 用 [[speak]]…[[/speak]] 借她的嘴说话",
        json_schema_extra={"label": "启用代发"},
    )
    daily_limit: int = Field(default=5, description="每天最多替她说几句（0 = 不限制）", json_schema_extra={"label": "每日上限"})
    max_chars: int = Field(default=200, description="一句最多多少字", json_schema_extra={"label": "正文上限（字）"})


class MaiMaiBridgeConfig(PluginConfigBase):
    """桥插件配置。"""

    plugin: BridgeCoreConfig = Field(default_factory=BridgeCoreConfig)
    browse: BridgeBrowseConfig = Field(default_factory=BridgeBrowseConfig)
    actions: BridgeActionsConfig = Field(default_factory=BridgeActionsConfig)
    outing: BridgeOutingConfig = Field(default_factory=BridgeOutingConfig)
    video: BridgeVideoConfig = Field(default_factory=BridgeVideoConfig)
    taste: BridgeTasteConfig = Field(default_factory=BridgeTasteConfig)
    relay: BridgeRelayConfig = Field(default_factory=BridgeRelayConfig)


__all__ = [
    "BridgeActionsConfig",
    "BridgeBrowseConfig",
    "BridgeCoreConfig",
    "BridgeOutingConfig",
    "BridgeRelayConfig",
    "BridgeTasteConfig",
    "BridgeVideoConfig",
    "MaiMaiBridgeConfig",
]
