#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""市场规则单一事实源：市场/指数代码表与市场推断纯函数。

被 tzt-api（行情客户端）与 kline-qlib（数据转换，经包依赖取用）共享——两侧
市场判断必须一致，故收敛到本模块。此前同一套规则有三份实现
（_base.infer_market / converter.code_to_qlib_dir / download.PREFIX_TO_MARKET），
靠人工同步。

本模块零第三方依赖，只含数据表与纯函数。
"""
from typing import Optional

__all__ = [
    "MARKET_CODE_MAP",
    "MARKET_TO_PREFIX",
    "INDEX_CODE_MAP",
    "INDEX_CODE_PREFIXES",
    "numeric_code",
    "is_index",
    "get_index_info",
    "infer_market",
]

# 市场 → 中焯市场代码（sh=沪 1, sz=深 0, bj=北 103）
MARKET_CODE_MAP = {
    "sh": 1,
    "sz": 0,
    "bj": 103,
}

# 反查表：市场代码 → qlib 目录前缀（kline_qlib.converter.code_to_qlib_dir 使用）
MARKET_TO_PREFIX = {1: "sh", 0: "sz", 103: "bj"}

# 常见指数代码表：{代码: (名称, 市场代码)}（2026-08 实测可获取日K/分钟K/分时/历史分时）。
#
# ⚠️ 代码歧义：000xxx 指数代码与深市个股代码段重叠——裸码 "000001" 既是上证指数
# （沪，market=1）也是平安银行（深，market=0）。本项目的市场推断规则是「指数优先」：
# 白名单内的裸码按指数处理；取深市个股请用显式前缀（"sz000001"）或显式传 market=0。
INDEX_CODE_MAP = {
    "000001": ("上证指数", 1),
    "000010": ("上证180", 1),
    "000015": ("上证红利", 1),
    "000016": ("上证50", 1),
    "000300": ("沪深300", 1),
    "000688": ("科创50", 1),
    "000698": ("科创100", 1),
    "000852": ("中证1000", 1),
    "000903": ("中证100", 1),
    "000905": ("中证500", 1),
    "000906": ("中证800", 1),
    "000922": ("中证红利", 1),
    "399001": ("深证成指", 0),
    "399004": ("深证100", 0),
    "399005": ("中小板指", 0),
    "399006": ("创业板指", 0),
    "399102": ("创业板综", 0),
    "399106": ("深证综指", 0),
    "399107": ("深证A指", 0),
    "399295": ("创业板50", 0),
    "399303": ("国证2000", 0),
    "399311": ("国证1000", 0),
    "399971": ("中证传媒", 0),
    "399997": ("中证白酒", 0),
    "399998": ("中证煤炭", 0),
    "899050": ("北证50", 103),
}

# 399 开头的代码均为深市指数（深证系列指数代码段），与个股无冲突
INDEX_CODE_PREFIXES = ("399",)


def numeric_code(code: str) -> str:
    """剥离 sh/sz/bj 显式前缀，返回纯数字代码。无前缀则原样返回。"""
    upper = code.upper()
    if upper[:2] in ("SH", "SZ", "BJ"):
        return code[2:]
    return code


def is_index(code: str) -> bool:
    """判断 code 是否按指数处理（请求行情前的优先判断）。

    规则（指数优先）：
      - 显式 sz/bj 前缀 → 按个股，返回 False
      - 白名单指数代码（INDEX_CODE_MAP）→ True
      - 399 开头（深证系列指数）→ True
      - 其余按个股，返回 False
    """
    upper = code.upper()
    if upper[:2] in ("SZ", "BJ"):
        return False
    numeric = numeric_code(code)
    return numeric in INDEX_CODE_MAP or numeric.startswith(INDEX_CODE_PREFIXES)


def get_index_info(code: str) -> Optional[tuple]:
    """若 code 按指数处理，返回 (名称, 市场代码)；否则返回 None。

    白名单外的 399 开头代码名称返回 None（市场仍为 0）。
    """
    if not is_index(code):
        return None
    numeric = numeric_code(code)
    info = INDEX_CODE_MAP.get(numeric)
    if info is not None:
        return info
    return (None, MARKET_CODE_MAP["sz"])  # 399 前缀的未知指数


def infer_market(code: str) -> int:
    """推断市场代码。请求行情前**优先判断指数，其次个股**。

    判断顺序：
      1. 显式前缀 sh/sz/bj → 直接按前缀市场（"sh000300" → 1）
      2. 指数优先：白名单指数（INDEX_CODE_MAP）按其所属市场，
         399 开头按深市指数（market=0）
      3. 个股规则：600/601/603/605/688/689 → 沪；000/001/002/003/300/301 → 深；
         8/4/920 → 北；其余默认深

    ⚠️ 歧义提示：裸码 "000001" 按指数优先返回沪市（上证指数）。
    取深市同名代码个股（如平安银行）请用 "sz000001" 或显式 market=0。
    """
    upper = code.upper()
    if upper.startswith("SH"):
        return MARKET_CODE_MAP["sh"]
    if upper.startswith("SZ"):
        return MARKET_CODE_MAP["sz"]
    if upper.startswith("BJ"):
        return MARKET_CODE_MAP["bj"]

    numeric = numeric_code(code)
    # 2) 指数优先判断（先于个股规则）
    info = INDEX_CODE_MAP.get(numeric)
    if info is not None:
        return info[1]
    if numeric.startswith(INDEX_CODE_PREFIXES):
        return MARKET_CODE_MAP["sz"]

    # 3) 个股规则
    if numeric.startswith(("600", "601", "603", "605", "688", "689")):
        return MARKET_CODE_MAP["sh"]
    if numeric.startswith(("000", "001", "002", "003", "300", "301")):
        return MARKET_CODE_MAP["sz"]
    if numeric.startswith(("8", "4", "920")):
        return MARKET_CODE_MAP["bj"]
    return MARKET_CODE_MAP["sz"]
