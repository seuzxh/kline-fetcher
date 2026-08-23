# monorepo 双包拆分（tzt-api + kline-qlib + kline-fetcher 兼容壳）实施任务分解

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 [docs/refactor-plan-monorepo-split.md](../../../refactor-plan-monorepo-split.md) 将本仓库拆为 `tzt-api`（纯行情请求，零 numpy）+ `kline-qlib`（qlib 写入）两个发行包，旧 `kline-fetcher` 降为纯转发兼容壳（3.1.0 终版），旧导入路径全兼容、外部使用方零改动。

**Architecture:** monorepo 内三个包目录（`tzt-api/`、`kline-qlib/`、`compat-kline-fetcher/`），依赖单向：`kline-qlib → tzt-api`，`compat-kline-fetcher → 两者`。市场规则收敛到 `tzt_api.market` 单一事实源。每任务"搬迁 + 垫片"同 commit 完成，保证每个提交点全部测试绿。

**Tech Stack:** Python ≥3.9、requests/PyYAML（tzt-api）、numpy（kline-qlib）、pytest（`qlib` conda 环境）、setuptools 各包独立 pyproject、MkDocs（strict）。

## Global Constraints

- **行为不变**：converter/download 只改导入来源与查表方式，控制流/限流/增量逻辑不动。
- **旧路径全兼容**（兼容壳覆盖，任务全程不得破坏）：包入口 6 名（`KLineFetcher/MinKLineFetcher/ConceptPlateFetcher/TrendFetcher/KLineToQlib/AdjustType`）；`kline_fetcher.fetcher`（含 `MARKET_CODE_MAP`）；`kline_fetcher.converter`（`KLineToQlib/QLIB_DAY_FIELDS/QLIB_MIN_FIELDS`）；`kline_fetcher.download`（`POOL_MAP/load_stock_pool/download_day_kline/download_min_kline/main`）；`kline_fetcher.server`（`app/main`）；CLI `kline-download`/`kline-server`。
- **版本时间线**：tzt-api `1.0.0`（Task 1 起）、kline-qlib `1.0.0`（Task 2 起）、根 kline-fetcher `3.0.1`（Task 1-2 过渡期不变）→ 兼容壳 `3.1.0`（Task 3）。
- **测试一律** `conda run -n qlib python -m pytest -q`；Task 1 起有三套套件（根/各包），每任务结束三套（或当时存在的套数）全绿才 commit。
- **包内模块禁止 import 仓内其他包根之外的旧路径**：tzt_api 内只用 `tzt_api.*`；kline_qlib 内只用 `tzt_api.*` + `kline_qlib.*`；兼容壳内只用 `tzt_api.*` + `kline_qlib.*`（不 import 兼容壳自身以外的过渡物）。
- **提交信息**：中文 + conventional 前缀。
- **工作分支**：`refactor/monorepo-split`（Task 1 Step 1 创建）。

---

### Task 1: 拆出 `tzt-api` 包（market.py 单一事实源 + 4 个 Fetcher + 行情侧测试）

**Files:**
- Create: `tzt-api/pyproject.toml`、`tzt-api/tzt_api/__init__.py`、`tzt-api/tzt_api/market.py`
- Move: `kline_fetcher/{_base,min_kline,concept_plate,trend}.py` → `tzt-api/tzt_api/`；`kline_fetcher/config/` → `tzt-api/tzt_api/config/`
- Modify: `tzt-api/tzt_api/_base.py`（market 导入 + 静态方法委托）
- Modify: 根 `kline_fetcher/__init__.py`（垫片化）、根 `kline_fetcher/fetcher.py`（垫片化 + 补 TrendFetcher）、根 `kline_fetcher/converter.py:13`（改 `tzt_api.market`）
- Move+Modify: 行情侧测试 → `tzt-api/tests/`（`test_trend_unit.py`、`test_concept_plates_unit.py`、`test_factor_calc.py`、`test_indices_integration.py`、`test_trend_integration.py`、`test_concept_plates.py`、`test_split_interfaces.py`）
- Create: `tzt-api/tests/test_market.py`、`tzt-api/tests/test_structure_api.py`、`tzt-api/tests/__init__.py`
- Modify: 根 `tests/test_structure.py`（`_base` 相关断言指向 tzt_api）

**Interfaces:**
- Consumes: 无（第一块基石）。
- Produces（后续任务依赖）：`tzt_api` 包——`__init__` 导出 `KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher, AdjustType`，`__version__ == "1.0.0"`；`tzt_api.market` 导出 `MARKET_CODE_MAP, MARKET_TO_PREFIX, INDEX_CODE_MAP, INDEX_CODE_PREFIXES, numeric_code(code)->str, is_index(code)->bool, get_index_info(code)->Optional[tuple], infer_market(code)->int`；`tzt_api._base` 可再导出 `ADJUST_MAP/PRICE_SCALE/TURNOVER_SCALE/MARKET_CODE_MAP/KLINE_TYPE_MAP/KLINE_RESPONSE_KEY_MAP`（供旧 fetcher 垫片路径）。

- [x] **Step 1: 创建分支与目录，git mv 模块**

```bash
cd /home/zxh/quant_projects/kline-fetcher
git checkout -b refactor/monorepo-split
mkdir -p tzt-api/tzt_api tzt-api/tests
touch tzt-api/tests/__init__.py
git mv kline_fetcher/_base.py tzt-api/tzt_api/_base.py
git mv kline_fetcher/min_kline.py tzt-api/tzt_api/min_kline.py
git mv kline_fetcher/concept_plate.py tzt-api/tzt_api/concept_plate.py
git mv kline_fetcher/trend.py tzt-api/tzt_api/trend.py
git mv kline_fetcher/config/kline_config.yaml tzt-api/tzt_api/config/kline_config.yaml
```

（若 `kline_fetcher/config` 因此空目录则 `rmdir`；mv 前先 `mkdir -p tzt-api/tzt_api/config`。）

- [x] **Step 2: 写失败测试 `tzt-api/tests/test_market.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tzt_api.market 单一事实源测试（纯函数，不依赖 numpy/qlib 侧）。"""
from tzt_api.market import (
    MARKET_CODE_MAP,
    MARKET_TO_PREFIX,
    INDEX_CODE_MAP,
    INDEX_CODE_PREFIXES,
    numeric_code,
    is_index,
    get_index_info,
    infer_market,
)


class TestMarketTables:
    def test_market_code_map(self):
        assert MARKET_CODE_MAP == {"sh": 1, "sz": 0, "bj": 103}

    def test_market_to_prefix_is_reverse(self):
        for prefix, code in MARKET_CODE_MAP.items():
            assert MARKET_TO_PREFIX[code] == prefix

    def test_index_code_map_entries(self):
        assert INDEX_CODE_MAP["000300"] == ("沪深300", 1)
        assert INDEX_CODE_MAP["399006"] == ("创业板指", 0)
        assert INDEX_CODE_MAP["899050"] == ("北证50", 103)
        assert len(INDEX_CODE_MAP) == 26
        assert INDEX_CODE_PREFIXES == ("399",)


class TestNumericCode:
    def test_strips_prefix(self):
        assert numeric_code("sh600519") == "600519"
        assert numeric_code("SZ000001") == "000001"
        assert numeric_code("bj830799") == "830799"

    def test_no_prefix_unchanged(self):
        assert numeric_code("600519") == "600519"


class TestIsIndex:
    def test_whitelist_and_prefix(self):
        for code in ["000001", "000300", "000688", "000852", "000905", "399001", "399006", "399999"]:
            assert is_index(code), f"{code} 应为指数"

    def test_stocks_not_index(self):
        for code in ["600519", "000002", "300750", "830799", "688981"]:
            assert not is_index(code), f"{code} 应为个股"

    def test_explicit_sz_bj_prefix_wins(self):
        assert not is_index("sz000001")
        assert not is_index("SZ000300")
        assert is_index("sh000300")


class TestInferMarket:
    def test_index_priority(self):
        assert infer_market("000001") == 1   # 上证指数（指数优先）
        assert infer_market("000300") == 1
        assert infer_market("399006") == 0
        assert infer_market("399999") == 0

    def test_stocks(self):
        assert infer_market("600519") == 1
        assert infer_market("000002") == 0
        assert infer_market("300750") == 0
        assert infer_market("sz000001") == 0
        assert infer_market("830799") == 103

    def test_get_index_info(self):
        assert get_index_info("000300") == ("沪深300", 1)
        assert get_index_info("399006") == ("创业板指", 0)
        assert get_index_info("600519") is None
        assert get_index_info("sz000001") is None


class TestFetcherDelegation:
    """KLineFetcher 静态方法委托 market 后行为不变。"""

    SAMPLES = ["600519", "SH600519", "sz000001", "000001", "000300",
               "399006", "399999", "830799", "000002", "899050"]

    def test_matches_kline_fetcher_statics(self):
        from tzt_api import KLineFetcher

        for c in self.SAMPLES:
            assert KLineFetcher.infer_market(c) == infer_market(c), c
            assert KLineFetcher.is_index(c) == is_index(c), c
```

- [x] **Step 3: 运行确认失败**

Run: `cd tzt-api && conda run -n qlib python -m pytest tests/test_market.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'tzt_api'`

- [x] **Step 4: 写 `tzt-api/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tzt-api"
version = "1.0.0"
description = "中焯行情 3.0 API 客户端（A股日K/分钟K/概念板块/分时）"
requires-python = ">=3.9"
dependencies = [
    "requests>=2.28",
    "PyYAML>=6.0",
]

[tool.setuptools.packages.find]
include = ["tzt_api*"]

[tool.setuptools.package-data]
tzt_api = ["config/*.yaml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: 需要真实 API 与网络的集成测试（默认不运行，手动用 -m integration 触发）",
]
addopts = "-m 'not integration'"
```

- [x] **Step 5: 写 `tzt-api/tzt_api/market.py`**（常量与函数**原样搬移**自原 `_base.py:75-235`，docstring 保留）

```python
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
```

- [x] **Step 6: 写 `tzt-api/tzt_api/__init__.py`**

```python
"""tzt-api：中焯行情 3.0 API 客户端（A股日K/分钟K/概念板块/分时）。

公开 API：
    KLineFetcher           — 基类（日K线 + 共享底座）
    MinKLineFetcher        — 分钟K线（继承 KLineFetcher）
    ConceptPlateFetcher    — 概念板块（继承 KLineFetcher）
    TrendFetcher           — 分时数据（继承 KLineFetcher）
    AdjustType             — 复权方式枚举

市场规则（与 kline-qlib 共享的单一事实源）见 tzt_api.market。
qlib 数据转换/下载见 kline-qlib 包。
"""
from tzt_api._base import KLineFetcher, AdjustType
from tzt_api.min_kline import MinKLineFetcher
from tzt_api.concept_plate import ConceptPlateFetcher
from tzt_api.trend import TrendFetcher

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "AdjustType",
]
__version__ = "1.0.0"
```

- [x] **Step 7: 修改 `tzt-api/tzt_api/_base.py`**

7a. 删除 `MARKET_CODE_MAP`、`INDEX_CODE_MAP`、`INDEX_CODE_PREFIXES` 的定义（约 L75-79、L103-138），import 区加：

```python
from tzt_api.market import (
    INDEX_CODE_MAP,
    INDEX_CODE_PREFIXES,
    MARKET_CODE_MAP,
    get_index_info,
    infer_market,
    is_index,
    numeric_code,
)
```

（模块 `__all__` 保持原样——这些名字经 import 后仍可从 `tzt_api._base` 导出，供旧 fetcher 垫片路径使用。）

7b. 4 个静态方法体替换为委托（签名与位置不动）：

```python
    @staticmethod
    def _numeric_code(code: str) -> str:
        """剥离 sh/sz/bj 显式前缀（委托 tzt_api.market.numeric_code）。"""
        return numeric_code(code)

    @staticmethod
    def is_index(code: str) -> bool:
        """是否按指数处理（指数优先规则见 tzt_api.market.is_index）。"""
        return is_index(code)

    @staticmethod
    def get_index_info(code: str) -> Optional[tuple]:
        """指数 (名称, 市场代码) 或 None（委托 tzt_api.market.get_index_info）。"""
        return get_index_info(code)

    @staticmethod
    def infer_market(code: str) -> int:
        """推断市场代码（指数优先；⚠️ 裸码 000001 按上证指数→沪市。
        规则全文见 tzt_api.market.infer_market）。"""
        return infer_market(code)
```

- [x] **Step 8: 三个子模块 import 各改 1 行**

- `tzt-api/tzt_api/min_kline.py`：`from kline_fetcher._base import KLineFetcher, KLINE_TYPE_MAP, KLINE_RESPONSE_KEY_MAP` → `from tzt_api._base import KLineFetcher, KLINE_TYPE_MAP, KLINE_RESPONSE_KEY_MAP`
- `tzt-api/tzt_api/concept_plate.py`：`from kline_fetcher._base import KLineFetcher, KLINE_RESPONSE_KEY_MAP` → `from tzt_api._base import KLineFetcher, KLINE_RESPONSE_KEY_MAP`
- `tzt-api/tzt_api/trend.py`：`from kline_fetcher._base import KLineFetcher, PRICE_SCALE, TURNOVER_SCALE` → `from tzt_api._base import KLineFetcher, PRICE_SCALE, TURNOVER_SCALE`

- [x] **Step 9: 根包垫片化**

9a. 根 `kline_fetcher/__init__.py` 整体替换为：

```python
"""（过渡兼容层）kline-fetcher 统一包已拆分为 tzt-api + kline-qlib。

本包在拆分期间保留旧导入路径：行情类来自 tzt_api，KLineToQlib 暂由根下
converter.py 提供（Task 2 后转发 kline_qlib）。
"""
from tzt_api import (
    AdjustType,
    ConceptPlateFetcher,
    KLineFetcher,
    MinKLineFetcher,
    TrendFetcher,
)
from kline_fetcher.converter import KLineToQlib

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "KLineToQlib",
    "AdjustType",
]
__version__ = "3.0.1"
```

9b. 根 `kline_fetcher/fetcher.py` 整体替换为（转发 tzt_api + 补 TrendFetcher）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""向后兼容垫片：保持 `from kline_fetcher.fetcher import ...` 可用。

行情实现已迁至 tzt-api 包（历史：v2.1.0 单文件拆分为多模块，本次拆包）。
本垫片同时补上 TrendFetcher（v2.1.0 拆分时的遗漏）。
新代码推荐：
    from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher
"""

from tzt_api._base import (
    KLineFetcher,
    AdjustType,
    ADJUST_MAP,
    _resolve_adjust,
    PRICE_SCALE,
    TURNOVER_SCALE,
    MARKET_CODE_MAP,
    KLINE_TYPE_MAP,
    KLINE_RESPONSE_KEY_MAP,
)
from tzt_api.min_kline import MinKLineFetcher
from tzt_api.concept_plate import ConceptPlateFetcher
from tzt_api.trend import TrendFetcher

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "AdjustType",
    "ADJUST_MAP",
    "_resolve_adjust",
    "PRICE_SCALE",
    "TURNOVER_SCALE",
    "MARKET_CODE_MAP",
    "KLINE_TYPE_MAP",
    "KLINE_RESPONSE_KEY_MAP",
]
```

9c. 根 `kline_fetcher/converter.py` L13：`from kline_fetcher._base import INDEX_CODE_MAP, INDEX_CODE_PREFIXES` → `from tzt_api.market import INDEX_CODE_MAP, INDEX_CODE_PREFIXES`（converter/download/server 本任务仍留在根包，Task 2 迁走）。

- [x] **Step 10: 行情侧测试迁入 `tzt-api/tests/` 并改导入**

```bash
git mv tests/test_trend_unit.py tests/test_concept_plates_unit.py tests/test_factor_calc.py tzt-api/tests/
git mv tests/test_indices_integration.py tests/test_trend_integration.py tests/test_concept_plates.py tests/test_split_interfaces.py tzt-api/tests/
```

对这 7 个文件执行导入替换（先 `grep -n kline_fetcher` 逐处确认）：

- `from kline_fetcher._base import PRICE_SCALE, TURNOVER_SCALE` / `from kline_fetcher._base import KLineFetcher` → `from tzt_api._base import ...`
- `from kline_fetcher._base import INDEX_CODE_MAP`（test_indices_integration.py:21）→ `from tzt_api.market import INDEX_CODE_MAP`
- 其余 `from kline_fetcher import X` / `import kline_fetcher` → `from tzt_api import X` / `import tzt_api`（如 prepare 侧脚本同款用法）

- [x] **Step 11: 新建 `tzt-api/tests/test_structure_api.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tzt-api 包结构静态测试。"""


class TestTztApiStructure:
    def test_exports(self):
        import tzt_api
        assert set(tzt_api.__all__) == {
            "KLineFetcher", "MinKLineFetcher", "ConceptPlateFetcher",
            "TrendFetcher", "AdjustType",
        }
        assert tzt_api.__version__ == "1.0.0"

    def test_module_location(self):
        from tzt_api import KLineFetcher
        assert KLineFetcher.__module__ == "tzt_api._base"

    def test_inheritance_chain(self):
        from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher
        for cls in (MinKLineFetcher, ConceptPlateFetcher, TrendFetcher):
            assert issubclass(cls, KLineFetcher)

    def test_method_attribution(self):
        from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher
        for m in ["fetch_day_kline", "fetch_day_kline_with_factor",
                  "fetch_trade_calendar", "get_stock_info", "infer_market"]:
            assert hasattr(KLineFetcher, m), f"KLineFetcher 缺 {m}"
        for m in ["fetch_min_kline", "get_all_concept_plates", "get_concept_plate_kline"]:
            assert not hasattr(KLineFetcher, m), f"KLineFetcher 不应有 {m}"
        assert hasattr(MinKLineFetcher, "fetch_min_kline")
        assert hasattr(ConceptPlateFetcher, "get_all_concept_plates")

    def test_module_all_declarations(self):
        from tzt_api import _base, min_kline, concept_plate, trend, market
        for mod in (_base, min_kline, concept_plate, trend, market):
            assert hasattr(mod, "__all__")
```

- [x] **Step 12: 更新根 `tests/test_structure.py`**

- L36 `from kline_fetcher import _base, min_kline, concept_plate` → `from tzt_api import _base, min_kline, concept_plate, trend`，函数体补 `assert hasattr(trend, "__all__")`
- L46 `assert KLineFetcher.__module__ == "kline_fetcher._base"` → `assert KLineFetcher.__module__ == "tzt_api._base"`
- 其余断言（`kline_fetcher.__version__ == "3.0.1"`、`test_backward_compat_shim`、TestDownloadLayer、TestConverterStatics、TestIndexDetection）**不动**——过渡期根包垫片仍要保它们绿。

- [x] **Step 13: 安装 + 三套验证 + 提交**

```bash
conda run -n qlib pip install -e ./tzt-api -q
cd tzt-api && conda run -n qlib python -m pytest -q && cd ..
conda run -n qlib python -m pytest -q   # 根套件（垫片回归）
git add -A
git commit -m "refactor: 行情客户端拆出 tzt-api 包（market.py 单一事实源），根包垫片化"
```

Expected: 两套全绿。

---

### Task 2: 拆出 `kline-qlib` 包（converter/download/server + CLI + 写入侧测试）

**Files:**
- Create: `kline-qlib/pyproject.toml`、`kline-qlib/kline_qlib/__init__.py`、`kline-qlib/tests/__init__.py`
- Move: `kline_fetcher/converter.py` → `kline-qlib/kline_qlib/converter.py`；`kline_fetcher/download.py` → `kline-qlib/kline_qlib/download.py`；`kline_fetcher/server.py` → `kline-qlib/kline_qlib/server.py`
- Modify: `kline-qlib/kline_qlib/converter.py`（导入 tzt_api.market、ensure_calendar 延迟导入）
- Modify: `kline-qlib/kline_qlib/download.py:15-16`（导入 tzt_api / kline_qlib.converter）
- Modify: `kline-qlib/kline_qlib/server.py:33-40`（导入 tzt_api + kline_qlib）
- Create（根垫片替换原实现）: 根 `kline_fetcher/converter.py`、`kline_fetcher/download.py`
- Modify: 根 `kline_fetcher/__init__.py`（KLineToQlib 改自 kline_qlib）
- Move+Modify: `tests/test_append_bin.py`、`tests/test_build_min_arrays.py`、`tests/test_calendar_generation.py`、`tests/test_server.py` → `kline-qlib/tests/`
- Create: `kline-qlib/tests/test_structure_qlib.py`
- Modify: 根 `tests/test_structure.py`（converter/download 断言指向 kline_qlib + 垫片同一性测试）

**Interfaces:**
- Consumes: Task 1 的 `tzt_api`（`KLineFetcher/MinKLineFetcher/...` + `tzt_api.market`）。
- Produces: `kline_qlib` 包——`__init__` 导出 `KLineToQlib, QLIB_DAY_FIELDS, QLIB_MIN_FIELDS, POOL_MAP, load_stock_pool, download_day_kline, download_min_kline`，`__version__ == "1.0.0"`；CLI 实际入口 `kline_qlib.download:main` / `kline_qlib.server:main`；`kline_qlib.converter` 模块含 `_DEFAULT_QLIB_DATA_DIR`（Task 4 使用）。

- [x] **Step 1: 目录与 git mv**

```bash
cd /home/zxh/quant_projects/kline-fetcher
mkdir -p kline-qlib/kline_qlib kline-qlib/tests
touch kline-qlib/tests/__init__.py
git mv kline_fetcher/converter.py kline-qlib/kline_qlib/converter.py
git mv kline_fetcher/download.py kline-qlib/kline_qlib/download.py
git mv kline_fetcher/server.py kline-qlib/kline_qlib/server.py
```

- [x] **Step 2: 写 `kline-qlib/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "kline-qlib"
version = "1.0.0"
description = "K线行情 → qlib bin 数据管道（下载编排 + 格式转换 + 调试服务），行情来自 tzt-api"
requires-python = ">=3.9"
dependencies = [
    "numpy>=1.24",
    "tzt-api>=1.0.0",
]

[project.optional-dependencies]
server = ["fastapi>=0.100", "uvicorn>=0.23"]

[project.scripts]
kline-download = "kline_qlib.download:main"
kline-server = "kline_qlib.server:main"

[tool.setuptools.packages.find]
include = ["kline_qlib*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [x] **Step 3: 写 `kline-qlib/kline_qlib/__init__.py`**

```python
"""kline-qlib：K线行情 → qlib bin 数据管道。

依赖方向：→ tzt-api（行情获取与市场规则）。本包不含 HTTP 客户端实现。
"""
from kline_qlib.converter import KLineToQlib, QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
from kline_qlib.download import (
    POOL_MAP,
    download_day_kline,
    download_min_kline,
    load_stock_pool,
)

__all__ = [
    "KLineToQlib",
    "QLIB_DAY_FIELDS",
    "QLIB_MIN_FIELDS",
    "POOL_MAP",
    "load_stock_pool",
    "download_day_kline",
    "download_min_kline",
]
__version__ = "1.0.0"
```

- [x] **Step 4: 修改 `kline-qlib/kline_qlib/converter.py`**

- L13 已是 `from tzt_api.market import INDEX_CODE_MAP, INDEX_CODE_PREFIXES`（Task 1 Step 9c 改过，随文件迁移生效，确认即可）
- L64-66 `ensure_calendar` 延迟导入：`from kline_fetcher.fetcher import KLineFetcher` → `from tzt_api import KLineFetcher`
- 模块 docstring 首段补：「v1.0.0 起位于 kline_qlib.converter（拆分自 kline-fetcher），旧路径 kline_fetcher.converter 由兼容壳转发。」

- [x] **Step 5: 修改 `kline-qlib/kline_qlib/download.py` 导入**（L15-16；只改导入，去重留 Task 4）

```python
from tzt_api import KLineFetcher, MinKLineFetcher
from kline_qlib.converter import KLineToQlib
```

- [x] **Step 6: 修改 `kline-qlib/kline_qlib/server.py` 导入**（原 L33-40）

```python
from tzt_api import (
    ConceptPlateFetcher,
    KLineFetcher,
    MinKLineFetcher,
    TrendFetcher,
)
from kline_qlib import KLineToQlib, __version__
```

（`app = FastAPI(..., version=__version__)` 引用不变；惰性单例函数体内类引用不变。）

- [x] **Step 7: 根 `kline_fetcher/converter.py`、`kline_fetcher/download.py` 替换为垫片**

`kline_fetcher/converter.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（过渡兼容垫片）实现已迁至 kline_qlib.converter。新代码：from kline_qlib import KLineToQlib"""
from kline_qlib.converter import KLineToQlib, QLIB_DAY_FIELDS, QLIB_MIN_FIELDS

__all__ = ["KLineToQlib", "QLIB_DAY_FIELDS", "QLIB_MIN_FIELDS"]
```

`kline_fetcher/download.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（过渡兼容垫片）实现已迁至 kline_qlib.download。新代码：from kline_qlib import download_day_kline"""
from kline_qlib.download import (
    POOL_MAP,
    download_day_kline,
    download_min_kline,
    load_stock_pool,
    main,
)

__all__ = [
    "POOL_MAP",
    "load_stock_pool",
    "download_day_kline",
    "download_min_kline",
    "main",
]
```

- [x] **Step 8: 根 `kline_fetcher/__init__.py` 的 KLineToQlib 导入改源**

`from kline_fetcher.converter import KLineToQlib` → `from kline_qlib import KLineToQlib`

- [x] **Step 9: 写入侧测试迁入 `kline-qlib/tests/` 并改导入**

```bash
git mv tests/test_append_bin.py tests/test_build_min_arrays.py tests/test_calendar_generation.py tests/test_server.py kline-qlib/tests/
```

- `test_append_bin.py` / `test_build_min_arrays.py` / `test_calendar_generation.py`：`from kline_fetcher.converter import ...` → `from kline_qlib.converter import ...`
- `test_server.py`：`from kline_fetcher import server` → `from kline_qlib import server`；文件内所有 patch/引用字符串 `kline_fetcher.server` → `kline_qlib.server`（grep 逐处确认）

- [x] **Step 10: 新建 `kline-qlib/tests/test_structure_qlib.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kline-qlib 包结构静态测试。"""
import inspect


class TestKlineQlibStructure:
    def test_exports(self):
        import kline_qlib
        assert "KLineToQlib" in kline_qlib.__all__
        assert "download_day_kline" in kline_qlib.__all__
        assert kline_qlib.__version__ == "1.0.0"

    def test_download_uses_fetchers(self):
        from kline_qlib import download as dl
        src = inspect.getsource(dl.download_day_kline)
        assert "KLineFetcher()" in src
        assert "fetch_day_kline_with_factor" in src
        src_min = inspect.getsource(dl.download_min_kline)
        assert "MinKLineFetcher()" in src_min
        assert "fetch_min_kline" in src_min

    def test_pool_map_completeness(self):
        from kline_qlib.download import POOL_MAP
        for pool in ["all", "csi300", "csi500", "csi800", "csi1000", "csiall"]:
            assert pool in POOL_MAP, f"缺股池: {pool}"

    def test_code_to_qlib_dir(self):
        from kline_qlib.converter import KLineToQlib
        assert KLineToQlib.code_to_qlib_dir("600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("SH600519") == "sh600519"
        assert KLineToQlib.code_to_qlib_dir("000001") == "sh000001"    # 指数优先
        assert KLineToQlib.code_to_qlib_dir("sz000001") == "sz000001"  # 显式前缀
        assert KLineToQlib.code_to_qlib_dir("000300") == "sh000300"
        assert KLineToQlib.code_to_qlib_dir("399999") == "sz399999"
        assert KLineToQlib.code_to_qlib_dir("899050") == "bj899050"
        assert KLineToQlib.code_to_qlib_dir("000002") == "sz000002"

    def test_fields_constants(self):
        from kline_qlib.converter import QLIB_DAY_FIELDS, QLIB_MIN_FIELDS
        expected = ["open", "high", "low", "close", "volume", "factor", "vwap"]
        assert QLIB_DAY_FIELDS == expected
        assert QLIB_MIN_FIELDS == expected
```

- [x] **Step 11: 更新根 `tests/test_structure.py`**

- `TestDownloadLayer` 两处 `from kline_fetcher import download as dl` → `from kline_qlib import download as dl`
- `TestConverterStatics` 的 `from kline_fetcher.converter import ...` → `from kline_qlib.converter import ...`
- 文件末尾新增垫片同一性测试：

```python
class TestCompatShims:
    """拆分过渡期：旧路径与实现包指向同一对象。"""

    def test_root_shims_same_objects(self):
        import kline_fetcher.converter as c_shim
        import kline_fetcher.download as d_shim
        from kline_qlib.converter import KLineToQlib as real_c
        from kline_qlib.download import download_day_kline as real_d
        assert c_shim.KLineToQlib is real_c
        assert d_shim.download_day_kline is real_d

    def test_fetcher_shim_includes_trend(self):
        from kline_fetcher.fetcher import TrendFetcher
        from tzt_api import TrendFetcher as real
        assert TrendFetcher is real
```

- [x] **Step 12: 安装 + 三套验证 + 提交**

```bash
conda run -n qlib pip install -e ./kline-qlib -q
cd kline-qlib && conda run -n qlib python -m pytest -q && cd ..
cd tzt-api && conda run -n qlib python -m pytest -q && cd ..
conda run -n qlib python -m pytest -q
git add -A
git commit -m "refactor: qlib 写入拆出 kline-qlib 包（converter/download/server + CLI），根包垫片化"
```

Expected: 三套全绿（根套件只剩 `test_structure.py`，即垫片回归）。

---

### Task 3: 兼容壳独立成包 `compat-kline-fetcher`，monorepo 收拢

**Files:**
- Create: `compat-kline-fetcher/pyproject.toml`
- Move: `kline_fetcher/`（整个目录）→ `compat-kline-fetcher/kline_fetcher/`
- Create: `compat-kline-fetcher/kline_fetcher/server.py`（新垫片，保 `uvicorn kline_fetcher.server:app`）
- Modify: `compat-kline-fetcher/kline_fetcher/__init__.py`（版本 3.1.0 + deprecated 说明）
- Move+Rewrite: 根 `tests/test_structure.py` → `compat-kline-fetcher/tests/test_compat.py`
- Delete: 根 `pyproject.toml`；根 `tests/`（迁空后删除）；未跟踪残留 `kline_fetcher.egg-info/`、`build/`

**Interfaces:**
- Consumes: Task 1/2 的 `tzt_api`、`kline_qlib`。
- Produces: 独立兼容壳包 `kline-fetcher 3.1.0`（终版，deprecated）——覆盖「Global Constraints」列出的全部旧路径；仓库根不再有 Python 包。

- [x] **Step 1: 迁移根包为兼容壳目录**

```bash
cd /home/zxh/quant_projects/kline-fetcher
mkdir -p compat-kline-fetcher/tests
touch compat-kline-fetcher/tests/__init__.py
git mv kline_fetcher compat-kline-fetcher/kline_fetcher
git mv tests/test_structure.py compat-kline-fetcher/tests/test_compat.py
rmdir tests 2>/dev/null || true
git rm pyproject.toml
rm -rf kline_fetcher.egg-info build
```

- [x] **Step 2: 写 `compat-kline-fetcher/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "kline-fetcher"
version = "3.1.0"
description = "（deprecated 兼容壳）原统一包的过渡导入层：re-export tzt-api + kline-qlib"
requires-python = ">=3.9"
dependencies = [
    "tzt-api>=1.0.0",
    "kline-qlib>=1.0.0",
]

[tool.setuptools.packages.find]
include = ["kline_fetcher*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [x] **Step 3: 兼容壳 `__init__.py` 终版**（版本 3.1.0 + 去向说明）

```python
"""kline-fetcher（deprecated 兼容壳，3.1.0 终版）。

原统一包已拆分（2026-08）：
  - 行情请求 → tzt-api（tzt_api 包）
  - qlib 写入 → kline-qlib（kline_qlib 包）

本包仅为旧导入路径提供转发，不再演进；请逐步迁移：
    from kline_fetcher import KLineFetcher      →  from tzt_api import KLineFetcher
    from kline_fetcher import KLineToQlib       →  from kline_qlib import KLineToQlib
    from kline_fetcher.fetcher import ...       →  from tzt_api import ...（或 tzt_api._base）
    from kline_fetcher.converter import ...     →  from kline_qlib.converter import ...
    from kline_fetcher.download import ...      →  from kline_qlib.download import ...
    uvicorn kline_fetcher.server:app            →  uvicorn kline_qlib.server:app
"""
from tzt_api import (
    AdjustType,
    ConceptPlateFetcher,
    KLineFetcher,
    MinKLineFetcher,
    TrendFetcher,
)
from kline_qlib import KLineToQlib

__all__ = [
    "KLineFetcher",
    "MinKLineFetcher",
    "ConceptPlateFetcher",
    "TrendFetcher",
    "KLineToQlib",
    "AdjustType",
]
__version__ = "3.1.0"
```

- [x] **Step 4: 新建 `compat-kline-fetcher/kline_fetcher/server.py` 垫片**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""（兼容垫片）`uvicorn kline_fetcher.server:app` 仍可用，实现位于 kline_qlib.server。"""
from kline_qlib.server import app, main

__all__ = ["app", "main"]
```

- [x] **Step 5: 重写 `compat-kline-fetcher/tests/test_compat.py`**（旧 test_structure.py 全量旧路径回归 + 去向断言）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容壳回归：全部旧导入路径可用，且与实现包指向同一对象。"""


class TestCompatShell:
    def test_root_exports_and_version(self):
        import kline_fetcher
        assert set(kline_fetcher.__all__) == {
            "KLineFetcher", "MinKLineFetcher", "ConceptPlateFetcher",
            "TrendFetcher", "KLineToQlib", "AdjustType",
        }
        assert kline_fetcher.__version__ == "3.1.0"

    def test_root_same_objects(self):
        import kline_fetcher as kf
        import tzt_api
        import kline_qlib
        assert kf.KLineFetcher is tzt_api.KLineFetcher
        assert kf.TrendFetcher is tzt_api.TrendFetcher
        assert kf.KLineToQlib is kline_qlib.KLineToQlib

    def test_fetcher_shim(self):
        from kline_fetcher.fetcher import (
            KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher,
            AdjustType, MARKET_CODE_MAP, PRICE_SCALE, TURNOVER_SCALE,
        )
        from tzt_api import KLineFetcher as real
        assert KLineFetcher is real

    def test_converter_shim(self):
        import kline_fetcher.converter as shim
        from kline_qlib.converter import KLineToQlib as real, QLIB_DAY_FIELDS
        assert shim.KLineToQlib is real
        assert shim.QLIB_DAY_FIELDS == QLIB_DAY_FIELDS

    def test_download_shim(self):
        import kline_fetcher.download as shim
        from kline_qlib.download import download_day_kline as real, main
        assert shim.download_day_kline is real
        assert callable(shim.main)

    def test_server_shim(self):
        from kline_fetcher.server import app, main
        from kline_qlib.server import app as real_app
        assert app is real_app
        assert callable(main)

    def test_old_semantics_unchanged(self):
        """指数优先等行为经兼容壳不变（抽样）。"""
        from kline_fetcher import KLineFetcher
        assert KLineFetcher.infer_market("000001") == 1
        assert KLineFetcher.infer_market("sz000001") == 0
        assert not KLineFetcher.is_index("sz000300")
```

- [x] **Step 6: 重装三包 + 全量验证 + 提交**

```bash
conda run -n qlib pip install -e ./tzt-api -e ./kline-qlib -e ./compat-kline-fetcher -q
cd tzt-api && conda run -n qlib python -m pytest -q && cd ..
cd kline-qlib && conda run -n qlib python -m pytest -q && cd ..
cd compat-kline-fetcher && conda run -n qlib python -m pytest -q && cd ..
git add -A
git commit -m "refactor: 旧 kline-fetcher 收拢为 compat-kline-fetcher 兼容壳（3.1.0 终版），monorepo 成型"
```

Expected: 三套全绿；仓库根已无 Python 包与根 pyproject。

---

### Task 4: 市场推断去重收敛（code_to_qlib_dir 一行化等）

**Files:**
- Modify: `kline-qlib/kline_qlib/converter.py`（L13 导入、L187-212 code_to_qlib_dir）
- Modify: `kline-qlib/kline_qlib/download.py`（L34-38 删 PREFIX_TO_MARKET、L41-44 load_stock_pool、download_day_kline docstring）
- Create: `kline-qlib/tests/test_cross_consistency.py`

**Interfaces:**
- Consumes: `tzt_api.market` 的 `MARKET_TO_PREFIX, infer_market, numeric_code, MARKET_CODE_MAP`；`kline_qlib.converter._DEFAULT_QLIB_DATA_DIR`。
- Produces: 行为不变的 `KLineToQlib.code_to_qlib_dir(code: str) -> str`（一行委托）与 `load_stock_pool(pool_name: str, instruments_dir: Optional[str] = None) -> list`（不再实例化 KLineToQlib）。

- [x] **Step 1: 写跨包一致性测试 `kline-qlib/tests/test_cross_consistency.py`（先绿锁行为）**

```python
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
```

Run: `cd kline-qlib && conda run -n qlib python -m pytest tests/test_cross_consistency.py -q`
Expected: PASS（对现存量实现成立——等价性先锁死）

- [x] **Step 2: `converter.py` code_to_qlib_dir 一行化**

导入行改为：

```python
from tzt_api.market import MARKET_TO_PREFIX, infer_market, numeric_code
```

方法（原 L187-212 整体替换）：

```python
    @staticmethod
    def code_to_qlib_dir(code: str) -> str:
        """股票/指数代码 → qlib 目录名（如 "sh600519"）。

        统一委托市场推断单一事实源（tzt_api.market）：目录前缀 =
        MARKET_TO_PREFIX[infer_market(code)]，尾码 = numeric_code(code)。
        指数优先规则见 tzt_api.market.infer_market。
        """
        return MARKET_TO_PREFIX[infer_market(code)] + numeric_code(code)
```

- [x] **Step 3: `download.py` 三处修改**

3a. 删除 `PREFIX_TO_MARKET = {...}`（原 L34-38）；导入区补 `from tzt_api.market import MARKET_CODE_MAP`（与 Step 2 的 converter 导入互不影响）；`load_stock_pool` 内 `market = PREFIX_TO_MARKET.get(prefix)` → `market = MARKET_CODE_MAP.get(prefix)`。

3b. `load_stock_pool` 默认路径轻量化（原 L42-44 不再实例化 KLineToQlib），导入区改 `from kline_qlib.converter import KLineToQlib, _DEFAULT_QLIB_DATA_DIR`：

```python
def load_stock_pool(pool_name: str, instruments_dir: Optional[str] = None) -> list:
    if instruments_dir is None:
        qlib_data_dir = os.environ.get("QLIB_DATA_DIR", _DEFAULT_QLIB_DATA_DIR)
        instruments_dir = os.path.join(qlib_data_dir, "instruments")
```

（函数其余部分不动。）

3c. `download_day_kline` 补 docstring（死参数声明，签名保留兼容）：

```python
    """按股池下载日K并写入 qlib bin。

    注意：日K固定以 hfq+none 双请求计算 factor（fetch_day_kline_with_factor），
    adjust 参数仅为 CLI 兼容保留，此函数内忽略。
    """
```

- [x] **Step 4: 回归 + 提交**

```bash
cd kline-qlib && conda run -n qlib python -m pytest -q && cd ..
cd compat-kline-fetcher && conda run -n qlib python -m pytest -q && cd ..
git add -A
git commit -m "refactor: 市场推断三份重复收敛至 tzt_api.market（code_to_qlib_dir 一行化、PREFIX_TO_MARKET 删除、load_stock_pool 轻量化）"
```

Expected: 全绿（`test_cross_consistency` + `test_structure_qlib::test_code_to_qlib_dir` 证明行为不变）。

---

### Task 5: 配置死键删除 + 三包 CHANGELOG

**Files:**
- Modify: `tzt-api/tzt_api/config/kline_config.yaml`（删 `kline_type_map:` / `market_map:` / `qlib_fields:` 三键）
- Create: `tzt-api/CHANGELOG.md`、`kline-qlib/CHANGELOG.md`、`compat-kline-fetcher/CHANGELOG.md`

**Interfaces:**
- Consumes: 无。
- Produces: 仅含 `api:` 与 `kline:` 两节的配置；三包各自 CHANGELOG 起点。

- [x] **Step 1: 复核无代码读取死键**

```bash
grep -rn "kline_type_map\|market_map\|qlib_fields" --include="*.py" tzt-api/ kline-qlib/ compat-kline-fetcher/ || echo "NO_CODE_READS"
```

Expected: `NO_CODE_READS`（若出现引用则停下排查，勿删）

- [x] **Step 2: 删除 yaml 三键**（保留 `api:` 与 `kline:` 两节，其余逐字不动）

- [x] **Step 3: 三个 CHANGELOG**

`tzt-api/CHANGELOG.md`：

```markdown
# Changelog

本文件记录 tzt-api 的版本变更（Keep a Changelog 格式）。

## [1.0.0] - 2026-08-23

- 自 kline-fetcher v3.0.1 拆分建包：KLineFetcher/_base、MinKLineFetcher、ConceptPlateFetcher、TrendFetcher 及 config
- 新增 `tzt_api.market` 市场规则单一事实源（原 `_base` 常量与 infer_market/is_index/get_index_info 纯函数化；`KLineFetcher` 对应静态方法改为委托）
- 依赖仅 requests + PyYAML（不再连带 numpy）
```

`kline-qlib/CHANGELOG.md`：

```markdown
# Changelog

本文件记录 kline-qlib 的版本变更（Keep a Changelog 格式）。

## [1.0.0] - 2026-08-23

- 自 kline-fetcher v3.0.1 拆分建包：converter（KLineToQlib）、download（含 kline-download/kline-server CLI）、server（FastAPI 调试服务）
- `code_to_qlib_dir` 收敛为对 tzt_api.market 的一行委托；删除 `download.PREFIX_TO_MARKET` 重复映射；`load_stock_pool` 不再实例化 KLineToQlib 取路径
- 依赖 numpy + tzt-api
```

`compat-kline-fetcher/CHANGELOG.md`：

```markdown
# Changelog

## [3.1.0] - 2026-08-23

- **终版（deprecated）**：原 kline-fetcher 统一包拆分为 tzt-api + kline-qlib 后，本包仅保留旧导入路径转发（包入口 / fetcher / converter / download / server 垫片），不再演进
- `fetcher` 垫片补上 v2.1.0 遗漏的 `TrendFetcher` 导出
- 使用方迁移完成后本包可卸载删除
```

- [x] **Step 4: 回归 + 提交**

```bash
cd tzt-api && conda run -n qlib python -m pytest -q && cd ..
conda run -n qlib python -c "
from tzt_api import KLineFetcher
print(KLineFetcher._load_config(KLineFetcher(), 'tzt-api/tzt_api/config/kline_config.yaml').keys())
"
git add -A
git commit -m "chore: 删除配置死键，三包建立 CHANGELOG"
```

Expected: tzt-api 套件绿；打印 `dict_keys(['api', 'kline'])`。

---

### Task 6: 文档全站同步（monorepo 双包）

**Files:**
- Modify: `AGENTS.md`、`README.md`、`docs/architecture.md`、`docs/api-reference.md`、`docs/guide/usage.md`、`docs/guide/download.md`、`docs/guide/testing.md`、`docs/CHANGELOG.md`、`docs/index.md`

**Interfaces:**
- Consumes: Task 1-5 之后的实际布局。
- Produces: 与代码一致的文档；mkdocs strict 通过。

- [x] **Step 1: 重写 `AGENTS.md` 架构节**——「## 架构」树整体替换为：

```
monorepo（v3.1.0 拆分）：
tzt-api/                  ← 包①：纯行情请求（零 numpy）
├── pyproject.toml        #   name: tzt-api；deps: requests, PyYAML
└── tzt_api/
    ├── __init__.py       #   导出 KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher, AdjustType
    ├── market.py         #   市场规则单一事实源（INDEX_CODE_MAP/infer_market 等，两包共享）
    ├── _base.py          #   KLineFetcher 基类：共享底座 + 日K方法
    ├── min_kline.py / concept_plate.py / trend.py
    └── config/kline_config.yaml
kline-qlib/               ← 包②：qlib 写入（依赖 tzt-api，单向）
├── pyproject.toml        #   name: kline-qlib；CLI: kline-download / kline-server
└── kline_qlib/
    ├── converter.py      #   KLineToQlib：K线 → qlib bin
    ├── download.py       #   批量下载编排 + CLI
    └── server.py         #   kline-server 调试服务
compat-kline-fetcher/     ← 旧 kline-fetcher 兼容壳（3.1.0 终版，纯转发，deprecated）
└── kline_fetcher/        #   __init__ / fetcher / converter / download / server 垫片
```

数据流：`API → tzt_api（获取+单位转换）→ kline_qlib.download（批量调度）→ kline_qlib.converter（对齐日历+写入bin）`

- [x] **Step 2: `AGENTS.md` 其余三处**

- 「导入方式」节改为：

```python
# 推荐：按包导入
from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher
from kline_qlib import KLineToQlib, download_day_kline, download_min_kline, load_stock_pool

# 旧路径（compat-kline-fetcher 兼容壳，deprecated，迁移完成后撤）
from kline_fetcher import KLineFetcher, KLineToQlib          # 仍可用
from kline_fetcher.fetcher import KLineFetcher, MARKET_CODE_MAP  # 仍可用
```

- 「新增指数支持」：`向 _base.py 的 INDEX_CODE_MAP 添加` → `向 tzt-api/tzt_api/market.py 的 INDEX_CODE_MAP 添加，infer_market / code_to_qlib_dir / is_index 自动生效`
- 「版本变更记录」速记追加：`- **v3.1.0（拆分）**：monorepo 双包——tzt-api（行情请求）+ kline-qlib（qlib 写入）+ kline-fetcher 兼容壳；市场规则收敛 tzt_api.market 单一事实源`

- [x] **Step 3: README 与 docs 批量更新**

逐文件 `grep -n` 确认后替换（关键映射表）：

| 旧（grep 目标） | 新 |
|---|---|
| `from kline_fetcher import KLineFetcher, ...`（推荐用法处） | `from tzt_api import ...`；`KLineToQlib/download_*` 类改 `from kline_qlib import ...` |
| `from kline_fetcher.fetcher import ...` | 标注「兼容壳路径，仍可用；新代码 `from tzt_api import ...`」 |
| `from kline_fetcher.converter import` / `from kline_fetcher.download import` | `from kline_qlib.converter import` / `from kline_qlib.download import`（保留一处壳路径示例） |
| `uvicorn kline_fetcher.server:app` | `uvicorn kline_qlib.server:app`（注明壳路径仍可用） |
| 旧目录树 / kline_fetcher/ 模块清单 | Task 6 Step 1 新树 |
| `向 _base.py 的 INDEX_CODE_MAP` | `向 tzt-api/tzt_api/market.py 的 INDEX_CODE_MAP` |
| 安装说明 `pip install kline-fetcher` / `-e .` | `pip install -e ./tzt-api -e ./kline-qlib`（兼容壳可选 `-e ./compat-kline-fetcher`） |
| 测试命令 `pytest` | `cd tzt-api && pytest` / `cd kline-qlib && pytest` / `cd compat-kline-fetcher && pytest` |

- [x] **Step 4: `docs/CHANGELOG.md` 新增 3.1.0 条目**（`[Unreleased]` 升格为 `[3.1.0] - 2026-08-23`，既有 Unreleased 内容并入，追加「🔧 重构」小节：拆分为 tzt-api + kline-qlib + 兼容壳、market 单一事实源、死键清理、CLI 迁移至 kline-qlib、旧路径经兼容壳保持可用）

- [x] **Step 5: mkdocs strict 验证 + 提交**

```bash
conda run -n qlib mkdocs build --strict && rm -rf site
git add -A
git commit -m "docs: monorepo 双包架构同步至 AGENTS/README/docs 全站"
```

Expected: 构建成功（仅既有中焯文档 INFO 提示，无 WARNING）。

---

### Task 7: 全量验证收尾

**Files:**
- Modify: `docs/refactor-plan-monorepo-split.md`（状态改「已完成」）、`docs/superpowers/plans/2026-08-23-monorepo-split.md`（无需改，勾选即可）

**Interfaces:**
- Consumes: Task 1-6 全部成果。
- Produces: 验证通过的 v3.1.0 拆分终态。

- [x] **Step 1: 干净重装三包**

```bash
conda run -n qlib pip uninstall -y kline-fetcher tzt-api kline-qlib -q
conda run -n qlib pip install -e ./tzt-api -e ./kline-qlib -e ./compat-kline-fetcher -q
```

- [x] **Step 2: 三套测试 + 依赖隔离检查**

```bash
cd tzt-api && conda run -n qlib python -m pytest -q && cd ..
cd kline-qlib && conda run -n qlib python -m pytest -q && cd ..
cd compat-kline-fetcher && conda run -n qlib python -m pytest -q && cd ..
conda run -n qlib pip show tzt-api | grep -i requires   # Expected: Requests, PyYAML（无 numpy）
```

- [x] **Step 3: CLI smoke + 旧路径全量模拟**

```bash
conda run -n qlib kline-download --help >/dev/null && echo CLI_DOWNLOAD_OK
conda run -n qlib kline-server --help >/dev/null && echo CLI_SERVER_OK
conda run -n qlib python -c "
from kline_fetcher import KLineFetcher, KLineToQlib, TrendFetcher
from kline_fetcher.fetcher import KLineFetcher as F2, MARKET_CODE_MAP
from kline_fetcher.converter import KLineToQlib as C2
from kline_fetcher.download import download_day_kline, main
from kline_fetcher.server import app
import kline_fetcher, tzt_api, kline_qlib
assert F2 is tzt_api.KLineFetcher and C2 is kline_qlib.KLineToQlib
assert kline_fetcher.__version__ == '3.1.0'
print('COMPAT_ALL_OK')
"
```

Expected: `CLI_DOWNLOAD_OK` / `CLI_SERVER_OK` / `COMPAT_ALL_OK`

- [x] **Step 4:（可选，需网络）集成测试抽查**

```bash
cd tzt-api && KLINE_API_BASE_URL=http://183.242.5.14:7778 conda run -n qlib python -m pytest -m integration -k indices -q && cd ..
```

Expected: PASS（行情行为不变）。

- [x] **Step 5: 收尾提交与汇报**

- `docs/refactor-plan-monorepo-split.md` 状态行改：`- **状态**：已完成（2026-08-23，分支 refactor/monorepo-split）`
- 清理：`rm -rf build/`
- 提交：

```bash
git add -A
git commit -m "chore: 拆分重构全量验证收尾"
```

- 向用户汇报：三套测试结果、CLI/兼容路径验证输出、依赖隔离证据、提交清单与分支状态，等待合并/推送决定。**迁移 6 处外部使用方与撤兼容壳为后续独立任务，不在本次范围。**

---

## Self-Review 记录

- **Spec 覆盖**：方案文档「三、实施阶段」7 项 ↔ Task 1-7 一一对应；「二、目标结构」全部目录/文件在各任务落位；「四、兼容性保证」由 Task 2/3 垫片 + Task 3 test_compat.py + Task 7 Step 3 模拟覆盖；「五、验证」清单全部纳入 Task 7。
- **类型一致性**：`tzt_api.market` 导出名与 Task 1 Step 7、Task 2 Step 4/5、Task 4 导入逐一核对一致；`kline_qlib.__version__` 在 Task 2 Step 3 定义、Task 2 Step 6 server 引用一致；`_DEFAULT_QLIB_DATA_DIR` 在 Task 4 Step 3b 消费、Interfaces 已声明。
- **占位符扫描**：无 TBD/TODO；文档类任务（Task 6）用「grep 目标 → 新文案」映射表给定具体内容，均为可执行指令。
- **风险点提示**：Task 1 Step 9a 根 `__init__` 引用 `kline_fetcher.converter`（同包内模块）——Python 包内绝对导入合法，Task 2 Step 8 改为 `kline_qlib` 后删除该依赖；Task 3 Step 1 的 `rmdir tests` 依赖目录已迁空，若仍有残留文件应先确认内容再处理。
