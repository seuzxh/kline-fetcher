#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨包一致性：kline_qlib 的目录命名必须由 tzt_api.market 单一事实源推出。"""
import pytest

from tzt_api.market import MARKET_TO_PREFIX, infer_market, numeric_code
from kline_qlib.converter import KLineToQlib

SAMPLES = [
    "600519", "SH600519", "sh600519", "sz000001", "000001", "000300",
    "sh000300", "000852", "399006", "399999", "830799", "000002",
    "300750", "899050", "000905",
]


def test_qlib_dir_matches_index_map():
    """全部白名单指数：code_to_qlib_dir 与市场前缀一致（自 tzt-api 迁入，保持 tzt-api 零依赖）。"""
    from tzt_api.market import INDEX_CODE_MAP
    prefix = {1: "sh", 0: "sz", 103: "bj"}
    for code, (_, market) in INDEX_CODE_MAP.items():
        assert KLineToQlib.code_to_qlib_dir(code) == prefix[market] + code, f"{code} qlib 目录不符"


@pytest.mark.parametrize("code", SAMPLES)
def test_qlib_dir_matches_infer_market(code):
    """code_to_qlib_dir ≡ MARKET_TO_PREFIX[infer_market(code)] + numeric_code(code)。"""
    assert KLineToQlib.code_to_qlib_dir(code) == MARKET_TO_PREFIX[infer_market(code)] + numeric_code(code)
