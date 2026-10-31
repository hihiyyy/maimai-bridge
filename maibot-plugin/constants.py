"""内置默认值：会被配置覆盖的常量集中放这里。

为什么这些不在代码里写死调用点：

- UA、反爬拦截词、动作白名单都是「跟着网站改版走」的东西，放在配置里，
  改版时用户自己换掉就行，不用等我发版。
- 这里只提供**默认值**。运行时一律走 ``resolve_*`` 系列函数：配置里填了就用
  配置的，填了空就用这里的，两者都不影响插件正常工作。
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

#: 默认 UA。用桌面 Edge，绝大多数站点不会因为 UA 直接拦。
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)

#: 默认「被挡住了」的判据。页面正文里出现这些字样，就当反爬验证页处理，
#: 不硬看、不硬点，直接如实告诉她「这次没看成」。
DEFAULT_BLOCK_MARKERS: Tuple[str, ...] = (
    "百度安全验证",
    "请完成下方验证",
    "滑动验证",
    "安全验证",
    "验证码",
    "Just a moment",
    "Enable JavaScript and cookies",
    "异常流量",
)

#: 默认允许的动作顺序（也用来提示模型有哪些动作可用）。
DEFAULT_ACTION_ORDER: Tuple[str, ...] = ("read", "click", "type", "scroll", "press", "back")

#: 动作红线（默认）：和钱、账号有关的事，写死不给改——她可以看，但不能替主人做决定。
#: 配置项 ``actions.redlines`` 非空时会**整体覆盖**这份清单。
DEFAULT_ACTION_REDLINES: Tuple[str, ...] = (
    "付款",
    "支付",
    "购买",
    "下单",
    "结算",
    "充值",
    "退款",
    "转账",
    "钱包",
    "绑定银行卡",
    "实名认证",
    "改密码",
    "修改密码",
    "注销账号",
    "注销账户",
    "解除绑定",
    "解绑手机",
    "删除账号",
)

#: 「对外说话」红线（默认）：评论 / 弹幕 / 私信 / 投稿属于第 4 期「代发」范围，
#: 现在一律拦下。配置项 ``actions.social_block`` 非空时整体覆盖。
DEFAULT_ACTION_SOCIAL: Tuple[str, ...] = (
    "发送评论",
    "发表评论",
    "发评论",
    "发弹幕",
    "发送弹幕",
    "发私信",
    "发送私信",
    "发布视频",
    "发布动态",
    "投稿",
    "转发",
)

#: 代发红线：钱和账号的事，DSH 写得再好也不替她说。
DEFAULT_RELAY_REDLINES: Tuple[str, ...] = (
    "转账",
    "汇款",
    "收款码",
    "付款",
    "支付",
    "密码",
    "验证码",
    "银行卡",
    "身份证",
    "实名",
    "借钱",
    "扫码",
)

#: 代发红线：不能替她 @ 所有人。
RELAY_MENTIONS: Tuple[str, ...] = ("@所有人", "@全体成员", "@all", "@everyone")

#: DSH 想借她的嘴说话时，用这对标记把台词圈出来。
SPEAK_PATTERN = re.compile(r"\[\[\s*speak\s*\]\](.*?)\[\[\s*/\s*speak\s*\]\]", re.DOTALL)

#: 交给 DSH 的任务末尾附上这句，它才知道自己有「借嘴说话」这个通道。
RELAY_HINT = (
    "（备注：如果你有话想直接发到群里，用 [[speak]]这句话[[/speak]] 包起来，"
    "我会替你发出去；不想说就别写。）"
)

#: 默认「批准 / 拒绝」口头禅（配置里可以改）。
DEFAULT_APPROVE_WORDS: Tuple[str, ...] = (
    "可以",
    "去吧",
    "同意",
    "准了",
    "行",
    "好",
    "批准",
    "ok",
    "OK",
    "嗯",
    "去吧喵",
)

DEFAULT_DENY_WORDS: Tuple[str, ...] = (
    "不行",
    "不许",
    "别去",
    "不准",
    "拒绝",
    "不去",
    "no",
    "NO",
    "算了吧",
)

#: 默认「什么时候想起她」的时段。
DEFAULT_AUTO_WINDOWS = "12:00-14:00,18:00-23:00"


# ── 配置串 ⇄ 元组 ────────────────────────────────────────────────────────


_CSV_SPLIT = re.compile(r"[,，;；\n]+")


def parse_csv(raw: str) -> List[str]:
    """把「逗号 / 中文逗号 / 分号 / 换行」分隔的配置串拆成去空白的列表。"""

    return [part.strip() for part in _CSV_SPLIT.split(raw or "") if part.strip()]


def resolve_csv(raw: str, default: Sequence[str]) -> Tuple[str, ...]:
    """配置优先，留空回退默认值。"""

    items = parse_csv(raw)
    return tuple(items) if items else tuple(default)


def resolve_user_agent(raw: str) -> str:
    """UA 配置优先，留空用内置桌面 Edge UA。"""

    return (raw or "").strip() or DEFAULT_USER_AGENT


def resolve_block_markers(raw: str) -> Tuple[str, ...]:
    """反爬拦截词配置优先，留空用内置默认。"""

    return resolve_csv(raw, DEFAULT_BLOCK_MARKERS)


def resolve_action_redlines(raw: str) -> Tuple[str, ...]:
    """动作红线配置优先，留空用内置默认（钱 / 账号类）。"""

    return resolve_csv(raw, DEFAULT_ACTION_REDLINES)


def resolve_action_social(raw: str) -> Tuple[str, ...]:
    """对外说话红线配置优先，留空用内置默认（评论 / 弹幕 / 私信类）。"""

    return resolve_csv(raw, DEFAULT_ACTION_SOCIAL)


def resolve_approve_words(raw: str) -> Tuple[str, ...]:
    return resolve_csv(raw, DEFAULT_APPROVE_WORDS)


def resolve_deny_words(raw: str) -> Tuple[str, ...]:
    return resolve_csv(raw, DEFAULT_DENY_WORDS)


def contains_any(text: str, needles: Iterable[str]) -> str:
    """返回 ``text`` 里第一个命中的关键词；没命中返回空串。"""

    haystack = text or ""
    for needle in needles:
        if needle and needle in haystack:
            return needle
    return ""


def extract_speak(text: str) -> Tuple[List[str], str]:
    """从 DSH 答复里抽出要代发的台词，并把标记从正文里剥掉。

    返回 ``(台词列表, 剥干净的正文)``。为什么要把标记剥掉：这段正文会原样
    交给麦麦当上下文，留着 ``[[speak]]`` 她可能会照着念出来。
    """

    raw = text or ""
    lines = [m.strip() for m in SPEAK_PATTERN.findall(raw) if m.strip()]
    cleaned = SPEAK_PATTERN.sub("", raw)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return lines, cleaned


__all__ = [
    "DEFAULT_ACTION_ORDER",
    "DEFAULT_ACTION_REDLINES",
    "DEFAULT_ACTION_SOCIAL",
    "DEFAULT_APPROVE_WORDS",
    "DEFAULT_AUTO_WINDOWS",
    "DEFAULT_BLOCK_MARKERS",
    "DEFAULT_DENY_WORDS",
    "DEFAULT_RELAY_REDLINES",
    "DEFAULT_USER_AGENT",
    "RELAY_HINT",
    "RELAY_MENTIONS",
    "SPEAK_PATTERN",
    "contains_any",
    "extract_speak",
    "parse_csv",
    "resolve_action_redlines",
    "resolve_action_social",
    "resolve_approve_words",
    "resolve_block_markers",
    "resolve_deny_words",
    "resolve_user_agent",
]
