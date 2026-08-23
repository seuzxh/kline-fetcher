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


@pytest.mark.parametrize("code", SAMPLES)
def test_qlib_dir_matches_infer_market(code):
    """code_to_qlib_dir ≡ MARKET_TO_PREFIX[infer_market(code)] + numeric_code(code)。"""
    assert KLineToQlib.code_to_qlib_dir(code) == MARKET_TO_PREFIX[infer_market(code)] + numeric_code(code)
