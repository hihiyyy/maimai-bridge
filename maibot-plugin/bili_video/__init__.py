# -*- coding: utf-8 -*-
"""看视频用的内置子包：B站接口客户端、目标解析、素材拼接、浏览记录、登录凭证、点赞收藏。

来源：``client`` / ``credential`` / ``digest`` / ``store`` / ``target`` 移植自
DomainDream/maibot-bilibili-browser（MIT），版权归原作者；
``reactions``（点赞、收藏）是这个插件新写的，没往移植来的文件里加东西。
"""

from __future__ import annotations

__all__ = [
    "client",
    "credential",
    "digest",
    "reactions",
    "store",
    "target",
]
