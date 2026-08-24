# kline-fetcher 项目说明

## 项目概述

kline-fetcher 仓库是 A 股行情 → Qlib 格式的数据管道：`kline-qlib`（qlib 写入 + CLI）+ `compat-kline-fetcher`（旧包名兼容壳）。行情客户端 `tzt-api`（`import tzt_api`）自 v3.1.0 后迁至**独立仓库 [GXQuotes](https://github.com/seuzxh/GXQuotes)**（本机 `~/quant_projects/GXQuotes`），本仓经 pip 依赖使用（`tzt-api>=1.0.0`），不做本地开发。

## 中焯官方接口文档（智能体必读）

**需要了解接口信息（Action 功能号、入出参、属性 ID、字段单位、市场代码等）时，优先阅读 [GXQuotes 仓库 docs/API/中焯官方文档/README.md](https://github.com/seuzxh/GXQuotes/blob/master/docs/API/%E4%B8%AD%E7%84%90%E5%AE%98%E6%96%B9%E6%96%87%E6%A1%A3/README.md)**（本机 `~/quant_projects/GXQuotes/docs/API/中焯官方文档/`）—— 该目录存放中焯行情 3.0 官方技术资料的解析版（6 份，可直接检索的 Markdown/文本）与原件（`originals/`），README 含「查什么 → 读哪份」导航和「文档 ↔ 代码」映射速查。中焯资料（官方文档归档、概念板块接口文档、tztapi-agent 指南）已随 tzt-api 包迁至 GXQuotes 仓库 `docs/`。

**接口工作派发规则**：凡是基于中焯行情 API 的接口需求——新建行情接口、校验现有接口用法、参数/响应解析问题——**必须调用子智能体 `tztapi-agent`**（ZCode：Skill `tztapi-agent`，位于 `~/.zcode/skills/tztapi-agent/`；Claude Code：subagent `tztapi-agent`）。该智能体的工作准则：一切结论以官方文档为据（注明出处）、以真实 API 实测定论，未经实测不得答复「确认可用」。

## 架构

```
本仓（tzt-api 迁出后）：
kline-qlib/               ← qlib 写入包（CLI: kline-download / kline-server；依赖外部 tzt-api）
├── pyproject.toml        #   name: kline-qlib；deps: numpy, tzt-api
└── kline_qlib/
    ├── converter.py      #   KLineToQlib：K线 → qlib bin
    ├── download.py       #   批量下载编排 + CLI
    └── server.py         #   kline-server 调试服务
compat-kline-fetcher/     ← 旧 kline-fetcher 兼容壳（3.1.0 终版，纯转发，deprecated）
└── kline_fetcher/        #   __init__ / fetcher / converter / download / server + _base/.min_kline/.concept_plate/.trend 子模块垫片

外部依赖：tzt-api（行情客户端，独立仓库 GXQuotes：github.com/seuzxh/GXQuotes，本机 ~/quant_projects/GXQuotes）
```

数据流：`API → tzt_api（GXQuotes，获取+单位转换）→ kline_qlib.download（批量调度）→ kline_qlib.converter（对齐日历+写入bin）`

**类继承结构**（位于 GXQuotes 仓库 tzt_api 包）：
```
KLineFetcher (tzt_api/_base.py)             ← 共享底座 + 日K方法
  ├── MinKLineFetcher (min_kline.py)            ← 继承，加分钟K方法
  ├── ConceptPlateFetcher (concept_plate.py)    ← 继承，加概念板块方法
  └── TrendFetcher (trend.py)                   ← 继承，加分时数据方法
```

## 核心类

### KLineFetcher (GXQuotes 仓库 tzt_api/_base.py) — 基类

中焯行情 API 客户端基类，提供共享底座（HTTP 请求、限流重试、参数构造、字段单位换算、K线解析）和日K线方法。自动推断市场代码、限流、重试。

**关键方法**（日K + 共享底座）：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `fetch_day_kline(code, count, market, begindate, enddate, adjust)` | 获取日K线 | `List[Dict]` 或 `None` |
| `fetch_day_kline_with_factor(code, count, market, begindate, enddate)` | 获取日K线（含factor计算） | `List[Dict]` 或 `None` |
| `fetch_trade_calendar(start_year, end_year)` | 获取交易日历 | `List[str]` 或 `None` |
| `get_stock_info(code, market)` | 获取股票基本信息 | `Dict` 或 `None` |
| `infer_market(code)` (静态) | 推断市场代码（**指数优先**，见下方「指数行情使用注意」） | `int` |
| `is_index(code)` / `get_index_info(code)` (静态) | 判断是否指数 / 取指数信息 | `bool` / `(name, market)` 或 `None` |
| `_request`, `_build_params`, `_parse_kline_items`, `_convert_*` (内部) | 共享底座 | — |

### 指数行情使用注意（重要）

指数与个股共用同一套请求方法，差异只在**市场推断**。请求行情前代码会**优先判断指数，其次个股**（`infer_market` / `code_to_qlib_dir` 均遵循此顺序）。

**支持的常见指数**（2026-08 实测：日K / 分钟K / 当日分时 / 历史分时 全部可获取，`INDEX_CODE_MAP` 共 26 个）：

| 沪市指数 (market=1) | 代码 | | 深市指数 (market=0) | 代码 |
|------|------|---|------|------|
| 上证指数 | 000001 | | 深证成指 | 399001 |
| 上证180 | 000010 | | 深证100 | 399004 |
| 上证红利 | 000015 | | 中小板指 | 399005 |
| 上证50 | 000016 | | 创业板指 | 399006 |
| 沪深300 | 000300 | | 创业板综 | 399102 |
| 科创50 | 000688 | | 深证综指 | 399106 |
| 科创100 | 000698 | | 深证A指 | 399107 |
| 中证1000 | 000852 | | 创业板50 | 399295 |
| 中证100 | 000903 | | 国证2000 | 399303 |
| 中证500 | 000905 | | 国证1000 | 399311 |
| 中证800 | 000906 | | 中证传媒 | 399971 |
| 中证红利 | 000922 | | 中证白酒 | 399997 |
| 北证50 (market=103) | 899050 | | 中证煤炭 | 399998 |

> 未列出的指数：399 开头自动按深市指数处理（`INDEX_CODE_PREFIXES` 规则）；
> 其他 000xxx 指数需向 `INDEX_CODE_MAP` 添加后使用。

**⚠️ 代码歧义（最易踩坑）**：`000xxx` 指数代码与深市个股代码段重叠，白名单内**每个 000xxx 指数裸码都会遮蔽同代码的深市个股**（如裸码 `"000001"` 按上证指数处理，对应遮蔽深市平安银行；`"000905"` 按中证500 处理，遮蔽深市厦门港务等）。本项目规则是**指数优先**：

```python
# 裸码 → 按指数（上证指数，market=1 自动推断）
fetcher.fetch_day_kline("000300")                    # ✅ 沪深300
tf.fetch_history_trend("000300", date="20260820")    # ✅ 指数历史分时

# 取深市个股（与指数代码重叠的）必须显式指定：
fetcher.fetch_day_kline("sz000001")                  # ✅ 平安银行（显式前缀）
fetcher.fetch_day_kline("000001", market=0)          # ✅ 平安银行（显式 market）

# 显式 sh/sz/bj 前缀优先于指数白名单：
fetcher.fetch_day_kline("sh000300")                  # ✅ 沪深300（前缀，无歧义）
```

**其他注意**：
- 指数无复权概念，`adjust` 参数对指数无意义（传 `"none"` 或默认均可，实测不影响返回）
- 指数写入 qlib 时目录按推断市场命名：`sh000300`（沪深300）、`sz399006`（创业板指）
- 新增指数支持：向 GXQuotes 仓库 `tzt_api/market.py` 的 `INDEX_CODE_MAP` 添加 `{代码: (名称, market)}`，`infer_market` / `code_to_qlib_dir` / `is_index` 自动生效

### MinKLineFetcher (GXQuotes 仓库 tzt_api/min_kline.py) — 分钟K线

继承 `KLineFetcher`，专注分钟K线特有的：freq→klinetype 映射、locator 翻页、starttime 定位。

**关键方法**：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `fetch_min_kline(code, freq, count, market, pages, adjust)` | 获取分钟K线（支持翻页） | `List[Dict]` 或 `None` |

> 返回数据自带 `date`/`time` 字段，客户端可自行按时间切片。

### ConceptPlateFetcher (GXQuotes 仓库 tzt_api/concept_plate.py) — 概念板块

继承 `KLineFetcher`，封装概念板块相关接口。**完整接口文档（含请求参数、响应字段、单位换算）见 [GXQuotes 仓库 docs/concept_plate_api.md](https://github.com/seuzxh/GXQuotes/blob/master/docs/concept_plate_api.md)**。

**关键方法**：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `get_all_concept_plates()` | 获取概念板块列表 | `List[Dict]` 或 `None` |
| `get_concept_plate_kline(plate_code, count, market)` | 获取板块K线 | `List[Dict]` 或 `None` |
| `get_concept_plate_stocks(plate_code, start, count)` | 获取板块成份股 | `List[Dict]` 或 `None` |
| `get_stock_concept_plates(code, market, plate_type)` | 获取股票所属板块 | `List[Dict]`，每项含 `type`（industry/region/concept） |

**⚠️ 使用注意（2026-08 实测）**：
- 概念板块市场代码固定 `market=44`，板块代码 `99xxxx`
- `get_all_concept_plates()` **只返回按涨幅排序的前 30 个**（总数 `max=390`，单次 count 上限 100，取全量需按 `start` 翻页，示例见接口文档 1.4）
- `get_concept_plate_stocks()` 返回**首项是板块自身**（`block.include=1` 所致，官方文档确认「包含板块指数则放行情列表首位」），成份股需过滤 `market != 44`；响应 `max` 字段为成份股总数
- `get_stock_concept_plates()` 旧实现（抓包复刻的 10000 请求）实测不可用；**已修复**：改用官方关联属性 `900|901|923`（CoIndBlkIdx=行业 / CoBlkIdx=全部隶属板块 / RegionBlkIdx=地域，出自《行情3.0股票属性ID》），一次请求返回全部板块并按 900/923 交叉标注 `type`；`plate_type="concept"/"industry"/"region"` 可过滤，默认返回全部。`market` 现为可选（自动推断，注意 000xxx 裸码指数优先歧义）

### TrendFetcher (GXQuotes 仓库 tzt_api/trend.py) — 分时数据

继承 `KLineFetcher`，专注分时数据获取：集合竞价（CallTrend，09:15-09:25）和盘中分时（TrendOp，09:30-15:00）。

**关键方法**：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `fetch_intraday_trend(code, market)` | 获取当日分时数据 | `Dict` 或 `None` |
| `fetch_history_trend(code, date, market)` | 获取历史分时数据 | `Dict` 或 `None` |
| `fetch_trend(code, date, market)` | 自动判断当日/历史 | `Dict` 或 `None` |

**分时数据返回结构**：
```python
{
    "market_date": "20260612",           # 市场日期
    "pre_market": [                      # 盘前集合竞价数据（09:15-09:25）
        {
            "date": "2026-06-12",
            "time": "09:25:00",
            "ref_price": 19.27,          # 参考价格（元）
            "matched_vol": 639300,       # 匹配成交量（股）
            "non_matched_vol_buy": 3800, # 未匹配买单量（股）
            "non_matched_vol_sell": 0,   # 未匹配卖单量（股）
            "phase": "pre-market"
        }
    ],
    "trading": [                         # 盘中数据（09:30-15:00）
        {
            "date": "2026-06-12",
            "time": "09:30:00",
            "last_price": 19.27,         # 最新价（元）
            "avg_price": 19.27,          # 均价（元）
            "volume": 639300,            # 成交量（股）
            "turnover": 123456789.0,     # 成交额（元）
            "phase": "trading"
        }
    ]
}
```

**分时数据获取规则**：

| 类型 | date参数 | daycount参数 | 说明 |
|------|----------|-------------|------|
| 当日分时 | 0 | 0 | 获取当日实时分时数据 |
| 历史分时 | YYYYMMDD | 1 | 获取指定日期历史分时 |

**API 参数**：`Action=10001`, `trendtypes=-1`（盘前/盘中/盘后整体分时）

### 导入方式

```python
# 推荐：按包导入
from tzt_api import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher, TrendFetcher
from kline_qlib import KLineToQlib, download_day_kline, download_min_kline, load_stock_pool

# 旧路径（compat-kline-fetcher 兼容壳，deprecated，迁移完成后撤）
from kline_fetcher import KLineFetcher, KLineToQlib          # 仍可用
from kline_fetcher.fetcher import KLineFetcher, MARKET_CODE_MAP  # 仍可用
```

**复权参数 adjust**：`"qfq"` (前复权=1), `"hfq"` (后复权=2), `"none"` (不复权=0), `None` (使用配置默认值，当前为后复权)

**AdjustType 枚举**：`AdjustType.qfq=1`, `AdjustType.hfq=2`, `AdjustType.none=0`

**fetch_day_kline_with_factor 逻辑**：
1. 分别获取后复权(hfq)和不复权(none)数据
2. 按日期对齐，计算 `factor = hfq_close / none_close`
3. 计算后复权成交量：`volume = none_volume / factor`
4. 不复权数据获取失败返回 None，close=0 时 factor=NaN

**数据单位转换**：

| API原始字段 | 原始单位 | 转换 | 目标单位 |
|------------|---------|------|---------|
| OpenPrice/HighPrice/LowPrice/ClosePrice | 万分之一元 | / 1,000,000 | 元 |
| PeriodVolume | 股 | 直接使用 | 股 |
| PeriodTurnover | 万元 | / 10,000 | 元 |

**K线数据字典结构**（fetch_day_kline 返回）：
```python
{
    "date": "2024-01-02",       # 日期
    "open": 10.5,               # 开盘价（元）
    "high": 10.8,               # 最高价（元）
    "low": 10.2,                # 最低价（元）
    "close": 10.6,              # 收盘价（元）
    "volume": 50000,            # 成交量（股）
    "amount": 530000000.0,      # 成交额（元）
    "time": "09:30:00",         # 时间（仅分钟K线）
    "factor": 1.05,             # 复权因子（仅 fetch_day_kline_with_factor）
}
```

**股票代码格式**：支持 `"600519"`, `"SH600519"`, `"sh600519"` 等格式，自动推断市场。

**市场代码**：`sh=1`, `sz=0`, `bj=103`

### KLineToQlib (kline-qlib/kline_qlib/converter.py)

将K线数据转换为 Qlib bin 格式。管理交易日历、bin 文件读写、增量追加。

**关键方法**：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `ensure_calendar(fetcher, start_year, end_year)` | 确保交易日历存在 | `bool` |
| `generate_min_calendar(freq)` | 生成分钟级日历 | `bool` |
| `day_kline_to_qlib(code, kline_data, mode, qlib_dir)` | 日K写入bin | `bool` |
| `min_kline_to_qlib(code, kline_data, freq, mode, qlib_dir)` | 分钟K写入bin | `bool` |
| `check_local_coverage(code, field, freq, qlib_dir)` | 检查本地数据覆盖范围 | `(start_idx, end_idx)` |
| `get_missing_range(code, start_date, end_date)` | 获取缺失日期范围 | `(start, end)` 或 `None` |
| `code_to_qlib_dir(code)` (静态) | 股票代码转qlib目录名 | `str` |

**写入字段**（`QLIB_DAY_FIELDS` / `QLIB_MIN_FIELDS`）：
```
["open", "high", "low", "close", "volume", "factor", "vwap"]
```

**Qlib bin 格式**：
- float32 小端序（`<f`）
- 首元素为交易日历起始索引
- 后续为对齐日历的数据数组，非交易日/缺失为 NaN
- 文件路径：`{qlib_data_dir}/features/{qlib_dir}/{field}.{freq}.bin`

**qlib_dir 命名规则**：`sh600519`, `sz000001`, `bj830799`

**写入模式**：
- `overwrite`：覆盖写入
- `append`：增量追加（`_append_bin` 处理重叠/间隙/延伸）

**vwap 计算**：`vwap = amount / volume`（volume > 0 时），amount 从 kline_data 的 `amount` 字段临时计算

**增量追加逻辑**（`_append_bin`）：
- 新数据完全在旧数据之后：NaN 填充间隙后拼接
- 新数据完全在旧数据之前：新数据在前
- 新旧重叠：按位置合并，新数据覆盖旧数据重叠部分

### download.py (kline-qlib/kline_qlib/download.py)

批量下载入口，提供 CLI 和函数调用两种方式。

**CLI**：`kline-download --start 2024-01-01 --end 2024-12-31 [options]`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--start` | 开始日期 (YYYY-MM-DD) | 必填 |
| `--end` | 结束日期 (YYYY-MM-DD) | 必填 |
| `--pool` | 股池名称 | `all` |
| `--full` | 强制全量下载 | False（增量） |
| `--freq` | 数据频率 (day/1min/5min) | `day` |
| `--pages` | 高频数据翻页次数 | 0（自动） |
| `--qlib-data-dir` | qlib 数据目录 | 环境变量 `QLIB_DATA_DIR` 或默认路径 |
| `--adjust` | 复权方式 (qfq/hfq/none) | 配置文件默认值 |

**股池**：`all`, `csi300`, `csi500`, `csi800`, `csi1000`, `csiall`（对应 `instruments/` 下的 txt 文件）

**日K下载流程**（`download_day_kline`）：
1. 加载股池 → 确保日历存在 → 按日期分段（>1500条分段下载）
2. 逐股票：检查本地覆盖 → `fetch_day_kline_with_factor` → `day_kline_to_qlib`
3. 增量模式下跳过已覆盖的股票/段落

**分钟K下载流程**（`download_min_kline`，使用 `MinKLineFetcher`）：
1. 加载股池 → 确保分钟日历存在 → 自动计算翻页次数
2. 逐股票：检查本地覆盖 → `fetch_min_kline` → `min_kline_to_qlib`

## Qlib 数据目录结构

```
{qlib_data_dir}/
├── calendars/
│   ├── day.txt           # 交易日历，每行一个日期 "2024-01-02"
│   ├── 1min.txt          # 分钟日历，每行一个时间戳 "2024-01-02 09:30:00"
│   └── 5min.txt
├── instruments/
│   ├── all.txt           # 全市场股票列表，每行 "sh600519\t股票名"
│   ├── csi300.txt
│   └── ...
└── features/
    ├── sh600519/
    │   ├── open.day.bin
    │   ├── high.day.bin
    │   ├── low.day.bin
    │   ├── close.day.bin
    │   ├── volume.day.bin
    │   ├── factor.day.bin
    │   └── vwap.day.bin
    └── sz000001/
        └── ...
```

## 复权与 factor 说明

v2.0.0 使用后复权作为默认复权方式：

- **存储价格** = 后复权价格（`cqtype=2`）
- **factor** = `后复权收盘价 / 不复权收盘价`
- **后复权成交量** = `不复权成交量 / factor`
- **还原原始价格**：`原始价 = 后复权价 / factor`
- **还原原始成交量**：`原始成交量 = 后复权成交量 × factor`

选择后复权的原因：历史价格不变，除权只影响后续数据，已存储数据不受影响，支持增量追加。

## 配置文件 (kline_config.yaml)

```yaml
api:
  # base_url 不在此配置，改用环境变量 KLINE_API_BASE_URL（避免提交敏感地址）
  base_url: ""
  max_retries: 3                         # 最大重试次数
  request_interval: 0.1                  # 请求间隔（秒）
  retry_delay: 1                         # 重试延迟（秒）
  timeout: 10                            # 请求超时（秒）
kline:
  cqtype: 2                              # 复权类型：0=不复权, 1=前复权, 2=后复权
  day_count: -1500                       # 日K默认获取条数（负数=从最新向前）
  min_count: -1500                       # 分钟K默认获取条数
  outtype: 1
  props: 0|1|2|3|4|191|190|519          # API 字段请求参数
  rights: 0
  route: 1
```

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `KLINE_API_BASE_URL` | **中焯行情 API 地址（必填）** | 无，未配置时报 EnvironmentError |
| `KLINE_CONFIG_PATH` | 自定义配置文件路径 | GXQuotes 仓库 tzt-api 包内 `config/kline_config.yaml` |
| `QLIB_DATA_DIR` | Qlib 数据目录 | `/root/Projects/0.qlib_pro/qlib_data` |

## 版本变更记录

完整变更历史见 [docs/CHANGELOG.md](docs/CHANGELOG.md)（单一事实来源，Keep a Changelog 格式）。

关键破坏性变更速记：

- **（未发布）tzt-api 迁出**：行情客户端整体迁至独立仓库 [GXQuotes](https://github.com/seuzxh/GXQuotes)；本仓保留 kline-qlib + 兼容壳，`import tzt_api` 用法不变（经 pip 依赖）
- **v3.1.0（拆分）**：monorepo 双包——tzt-api（行情请求）+ kline-qlib（qlib 写入）+ kline-fetcher 兼容壳；市场规则收敛 tzt_api.market 单一事实源
- **v3.0.0**：架构拆分——单文件 `fetcher.py` 拆分为 `_base/min_kline/concept_plate` 继承体系，概念板块/分钟K方法移入子类（旧导入路径保留兼容垫片）
- **v2.0.0**：默认后复权存储 + `factor` 字段（还原原始价：`后复权价/factor`），已有数据需全量替换
