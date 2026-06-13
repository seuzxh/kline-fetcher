# kline-fetcher — A股K线数据获取与qlib格式转换工具

## 模块概述

`kline-fetcher` 是一个独立的 Python 包，基于中焯行情 API 获取 A 股 K 线数据，并转换为 qlib bin 格式存储。无需 Token 认证，支持 `pip install` 安装。

**安装**：

```bash
pip install -e /root/Projects/0.qlib_pro/data_v2
```

**快速开始**：

```python
from kline_fetcher import KLineFetcher, MinKLineFetcher, KLineToQlib

fetcher = KLineFetcher()           # 日K线
min_fetcher = MinKLineFetcher()    # 分钟K线
converter = KLineToQlib()

data = fetcher.fetch_day_kline("600519", count=10)
min_data = min_fetcher.fetch_min_kline("600519", freq="5min", count=10)
```

**核心能力**：
- 日 K 线数据获取（支持 `begindate`/`enddate` 日期范围查询，突破 1500 条限制）
- 高频 K 线数据获取（1min/5min/15min/30min/60min，支持 `locator` 自动翻页），见 `MinKLineFetcher`
- 自动转换为 qlib bin 格式（对齐交易日历，支持追加/覆盖写入）
- 增量更新（检查本地覆盖范围，仅下载缺失部分）
- 大范围日 K 自动分段下载（>1500 条自动拆分）

**限制**：
- 默认后复权（`cqtype=2`，v2.0.0 起），配合 `factor` 字段可还原原始价格
- API 单次请求最多返回 1500 条数据

**扩展功能**：
- 支持概念板块数据获取（详见「概念板块相关方法」）

## 目录结构

```
kline-fetcher/                    # 包项目根目录
├── pyproject.toml                # 包元数据和依赖声明
├── README.md                     # 本文档
├── AGENTS.md                     # 项目说明（给 AI 代理用）
├── tests/                        # 测试文件目录
│   ├── __init__.py               # 测试包文件
│   ├── test_append_bin.py        # _append_bin 单元测试
│   ├── test_concept_plates.py    # 概念板块集成测试（需 API）
│   └── test_split_interfaces.py  # 拆分后接口集成测试（需 API）
└── kline_fetcher/                # Python 包目录
    ├── __init__.py               # 导出公共 API（KLineFetcher/MinKLineFetcher/ConceptPlateFetcher/KLineToQlib/AdjustType）
    ├── _base.py                  # KLineFetcher 基类（共享底座 + 日K方法）
    ├── min_kline.py              # MinKLineFetcher(KLineFetcher) — 分钟K线方法
    ├── concept_plate.py          # ConceptPlateFetcher(KLineFetcher) — 概念板块方法
    ├── fetcher.py                # 兼容垫片（v2.1.0 前的单文件实现已拆分，保留旧导入路径）
    ├── converter.py              # KLineToQlib — 数据转换为 qlib bin 格式
    ├── download.py               # CLI 批量下载入口
    └── config/
        └── kline_config.yaml     # 默认配置
```

## 配置

### 配置文件

包内默认配置：`data_v2/config/kline_config.yaml`

项目级配置（优先）：`/root/Projects/0.qlib_pro/config/kline_config.yaml`

```yaml
api:
  # Do NOT set base_url here — use the KLINE_API_BASE_URL environment variable instead.
  base_url: ""
  timeout: 10
  max_retries: 3
  retry_delay: 1
  request_interval: 0.1

kline:
  cqtype: 1
  day_count: -1500
  min_count: -1500
  outtype: 1
  rights: 0
  route: 1
  props: "0|1|2|3|4|191|190|519"
```

### 环境变量

| 环境变量 | 用途 | 默认值 |
|---------|------|-------|
| `KLINE_API_BASE_URL` | **API 服务地址**（优先于配置文件） | 无（必须配置） |
| `KLINE_CONFIG_PATH` | KLineFetcher 配置文件路径 | 包内 `config/kline_config.yaml` |
| `QLIB_DATA_DIR` | KLineToQlib 数据目录 | `/root/Projects/0.qlib_pro/qlib_data` |

> **安全说明**：API 地址（包含 IP/域名）不应硬编码在源代码或提交的配置文件中。
> 请通过 `KLINE_API_BASE_URL` 环境变量传入，具体方式见下方说明。

#### 本地开发（`.env` 文件）

项目 `.gitignore` 已忽略 `.env`，可在项目根目录创建 `.env` 文件：

```bash
# .env（不要提交到 Git）
KLINE_API_BASE_URL=http://<your-api-host>:<port>
```

使用 `python-dotenv` 等工具加载，或在启动脚本中手动导出：

```bash
export KLINE_API_BASE_URL=http://<your-api-host>:<port>
python your_script.py
```

#### GitHub Actions / GitHub Secrets & Variables

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加：

- **Secret**（推荐，值不可见）：名称 `KLINE_API_BASE_URL`
- 或 **Variable**（值可见，适合非敏感配置）：名称 `KLINE_API_BASE_URL`

然后在 workflow 中通过 `env` 字段注入：

```yaml
jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run kline fetcher
        env:
          KLINE_API_BASE_URL: ${{ secrets.KLINE_API_BASE_URL }}
          # 或使用 Variables: ${{ vars.KLINE_API_BASE_URL }}
        run: python your_script.py
```

如果 `KLINE_API_BASE_URL` 未配置，程序将以明确的错误信息退出，而不是静默失败：

```
EnvironmentError: API base URL is not configured.
Set the KLINE_API_BASE_URL environment variable (e.g. in .env or as a GitHub Secret/Variable),
or set api.base_url in your kline_config.yaml.
```

---

## 类：KLineFetcher（API 请求封装）

**用途**：封装中焯 K 线 API 的所有请求逻辑，包括数据获取、分页、单位转换。

### 构造函数

```python
KLineFetcher(config_path: Optional[str] = None)
```

- `config_path=None`：依次尝试环境变量 `KLINE_CONFIG_PATH`、包内默认配置
- `config_path="path/to/config.yaml"`：使用指定配置文件

### 静态方法

#### `infer_market(code: str) -> int`

根据股票代码前缀推断市场编号。

| 代码前缀 | 市场 | 返回值 |
|---------|------|-------|
| 600/601/603/605/688/689 | 上交所 | 1 |
| 000/001/002/003/300/301 | 深交所 | 0 |
| 8/4/920 开头 | 北交所 | 103 |
| 其他 | 默认深交所 | 0 |

```python
market = KLineFetcher.infer_market("600519")  # → 1
market = KLineFetcher.infer_market("000001")  # → 0
market = KLineFetcher.infer_market("830799")  # → 103
```

### 核心方法

#### `fetch_day_kline` — 获取日 K 线数据

```python
def fetch_day_kline(
    self,
    code: str,                              # 股票代码（纯数字，如 "600519"）
    count: Optional[int] = None,            # 请求数量（负数=由近及远），与 begindate/enddate 互斥
    market: Optional[int] = None,           # 市场编号，None 则自动推断
    begindate: Optional[str] = None,        # 起始日期（"YYYYMMDD" 格式，如 "20200101"）
    enddate: Optional[str] = None,          # 结束日期（"YYYYMMDD" 格式，如 "20260515"）
) -> Optional[List[Dict]]
```

**参数优先级**：
1. 若提供 `begindate` 或 `enddate` → 使用日期范围模式（删除 count 参数）
2. 若仅提供 `count` → 使用数量模式
3. 两者都不提供 → 使用配置文件默认值（-1500）

**日期范围模式注意**：
- API 单次请求仍最多返回 1500 条，超过 1500 条的日期范围会报错
- 大范围下载请使用 `download_day_kline` 的分段下载功能，或自行分段调用

**返回值**：K 线数据列表，每条记录格式：

```python
[
    {
        "date": "2026-05-15",
        "open": 1850.5,
        "high": 1862.3,
        "low": 1845.0,
        "close": 1858.2,
        "volume": 3500000.0,
        "amount": 6487000000.0,
    },
    ...
]
```

返回 `None` 表示请求失败。

**示例**：

```python
from kline_fetcher import KLineFetcher
fetcher = KLineFetcher()

data = fetcher.fetch_day_kline("600519", count=200)
data = fetcher.fetch_day_kline("600519", begindate="20240101", enddate="20260515")
data = fetcher.fetch_day_kline("600519", enddate="20260515")
data = fetcher.fetch_day_kline("600519")
```

---

#### `fetch_min_kline` — 获取高频 K 线数据

> **v2.1.0 起归属 `MinKLineFetcher`**（从 `KLineFetcher` 剥离）。

```python
def fetch_min_kline(
    self,
    code: str,                              # 股票代码（纯数字，如 "600519"）
    freq: str = "1min",                     # 频率：1min / 5min / 15min / 30min / 60min
    count: Optional[int] = None,            # 请求数量（负数=由近及远）
    market: Optional[int] = None,           # 市场编号
    pages: int = 1,                         # 翻页次数（1=不翻页，>1 自动使用 locator 翻页）
) -> Optional[List[Dict]]
```

**分页机制**：
- `pages=1`：单次请求，最多 1500 条
- `pages>1`：使用 API 返回的 `locator` 值自动翻页，每页 1500 条
- 多页数据自动去重并按时间排序

**返回值**：K 线数据列表，高频数据额外包含 `"time"` 字段。

**每页覆盖交易日数参考**：

| 频率 | 每交易日条数 | 每页覆盖交易日 |
|------|-----------|-------------|
| 1min | 240 | ~6 天 |
| 5min | 48 | ~31 天 |
| 15min | 16 | ~93 天 |
| 30min | 8 | ~187 天 |
| 60min | 4 | ~375 天 |

---

#### `fetch_kline` — 分钟K线时间定位切片

> **v2.1.0 起归属 `MinKLineFetcher`**（名义通用，实际为分钟K专用：依赖每条数据的 `time` 字段定位，传入 `freq="day"` 会因日K无 `time` 字段而失败）。

```python
def fetch_kline(
    self,
    code: str,                              # 股票代码（纯数字）
    freq: str,                              # 分钟频率：1min / 5min / 15min / 30min / 60min
    starttime: str,                         # 起始时间（"yyyy-mm-dd HH:mm" 格式）
    count: int,                             # 数据条数（正数=向后，负数=向前）
    market: Optional[int] = None,           # 市场编号
) -> Optional[List[Dict]]
```

**语义说明**：
- `count > 0`：从 `starttime` 开始，向后取 `count` 条数据
- `count < 0`：从 `starttime` 开始，向前取 `|count|` 条数据
- 自动计算所需翻页次数，隐藏分页细节

**已知限制**：内部仅在最近 1500 根 K 线范围内做 `starttime` 切片定位，超出该范围返回 `None`（对 1min 频率约 6 个交易日）。详见 `REVIEW_ISSUES.md` #1。

**示例**：

```python
from kline_fetcher import MinKLineFetcher
fetcher = MinKLineFetcher()

data = fetcher.fetch_kline("600519", freq="1min", starttime="2026-05-08 09:30", count=240)
data = fetcher.fetch_kline("600519", freq="5min", starttime="2026-05-15 15:00", count=-48)
```

---

#### `get_stock_info` — 获取股票基本信息

```python
def get_stock_info(self, code: str, market: Optional[int] = None) -> Optional[Dict]
```

**返回值**：`{"code": "600519", "name": "贵州茅台", "market_sn": 1}`

---

### 概念板块相关方法

> **v2.1.0 起归属 `ConceptPlateFetcher`**（从 `KLineFetcher` 剥离）。以下方法需通过 `ConceptPlateFetcher` 实例调用。

#### `get_all_concept_plates` — 获取全部概念板块

```python
def get_all_concept_plates(self) -> Optional[List[Dict]]
```

**返回值**：概念板块列表，每条记录格式：

```python
[
    {
        "code": "994639",
        "name": "高带宽内存",
        "market": 44,
        "price": 2606820000,
        "change": 105870000,
        "change_pct": 4233
    },
    ...
]
```

**示例**：

```python
from kline_fetcher import ConceptPlateFetcher
fetcher = ConceptPlateFetcher()

plates = fetcher.get_all_concept_plates()
if plates:
    for plate in plates[:5]:
        print(f"概念板块: {plate['name']} ({plate['code']})")
```

---

#### `get_concept_plate_kline` — 获取概念板块K线数据

```python
def get_concept_plate_kline(
    self,
    plate_code: str,                        # 概念板块代码（如 "994612"）
    count: int = -220,                      # 请求数量（负数=由近及远）
    market: int = 44,                       # 市场编号（概念板块默认44）
) -> Optional[List[Dict]]
```

**返回值**：K 线数据列表，格式与 `fetch_day_kline` 相同。

**示例**：

```python
from kline_fetcher import ConceptPlateFetcher
fetcher = ConceptPlateFetcher()

# 获取概念板块K线数据
kline_data = fetcher.get_concept_plate_kline("994612", count=-100)
if kline_data:
    print(f"获取到 {len(kline_data)} 条K线数据")
```

---

#### `get_concept_plate_stocks` — 获取概念板块成份股

```python
def get_concept_plate_stocks(
    self,
    plate_code: str,                        # 概念板块代码（如 "994612"）
    start: int = 0,                         # 起始索引
    count: int = 10,                        # 请求数量
) -> Optional[List[Dict]]
```

**返回值**：成份股列表，每条记录格式：

```python
[
    {
        "code": "688361",
        "name": "中科飞测",
        "market": 1,
        "price": 258940000,
        "change": 38440000,
        "change_pct": 17433,
        "high": 264600000,
        "low": 230000000
    },
    ...
]
```

**示例**：

```python
from kline_fetcher import ConceptPlateFetcher
fetcher = ConceptPlateFetcher()

# 获取概念板块成份股
stocks = fetcher.get_concept_plate_stocks("994612", count=20)
if stocks:
    print(f"概念板块包含 {len(stocks)} 只股票")
    for stock in stocks[:10]:
        print(f"  {stock['name']} ({stock['code']})")
```

---

#### `get_stock_concept_plates` — 获取股票所属概念板块

```python
def get_stock_concept_plates(
    self,
    code: str,                              # 股票代码（纯数字）
    market: int,                            # 市场编号
) -> Optional[List[Dict]]
```

**返回值**：概念板块列表，包含股票所属的所有概念板块信息。

**示例**：

```python
from kline_fetcher import ConceptPlateFetcher
fetcher = ConceptPlateFetcher()

# 获取股票所属概念板块
plates = fetcher.get_stock_concept_plates("600519", market=1)
if plates:
    print(f"股票所属概念板块: {[plate['name'] for plate in plates]}")
```

---

## 类：KLineToQlib（数据转换与写入）

**用途**：将 K 线数据转换为 qlib bin 格式，写入 `qlib_data/features/` 目录。自动对齐交易日历，支持追加和覆盖模式。

### 构造函数

```python
KLineToQlib(qlib_data_dir: Optional[str] = None)
```

- `qlib_data_dir=None`：使用环境变量 `QLIB_DATA_DIR`，默认 `/root/Projects/0.qlib_pro/qlib_data`
- `qlib_data_dir="/path/to/qlib_data"`：使用指定目录

自动加载交易日历和高频日历。若日历文件不存在，可调用 `ensure_calendar()` 从 API 自动生成。

### 交易日历管理

#### `ensure_calendar` — 自动生成交易日历

```python
def ensure_calendar(
    self,
    fetcher: Optional[KLineFetcher] = None,   # API 请求实例（None 则自动创建）
    start_year: int = 2000,                    # 起始年份
    end_year: int = 2030,                      # 结束年份
) -> bool
```

**用途**：当本地无交易日历文件时，从 API 获取上证指数日K数据，提取交易日并保存为 `day.txt`。

**逻辑**：
1. 若已有日历（`self.dates` 非空），直接返回 `True`
2. 按年份从 API 获取上证指数（000001）日K，提取日期
3. 保存为 `qlib_data/calendars/day.txt`
4. 重新加载日历到内存

```python
from kline_fetcher import KLineFetcher, KLineToQlib

converter = KLineToQlib(qlib_data_dir="/path/to/qlib_data")
converter.ensure_calendar()  # 自动从 API 获取交易日历

# 或指定 fetcher 和年份范围
fetcher = KLineFetcher()
converter.ensure_calendar(fetcher=fetcher, start_year=2020, end_year=2026)
```

#### `generate_min_calendar` — 生成高频交易日历

```python
def generate_min_calendar(self, freq: str = "1min") -> bool
```

**用途**：基于已有的日交易日历，生成高频时间戳日历文件。

**支持频率**：1min / 5min / 15min / 30min / 60min

**A 股交易时间**：
- 上午：9:30 - 11:30
- 下午：13:00 - 15:00

**每交易日 bar 数**：

| 频率 | bar 数 |
|------|-------|
| 1min | 240 |
| 5min | 48 |
| 15min | 16 |
| 30min | 8 |
| 60min | 4 |

```python
converter = KLineToQlib(qlib_data_dir="/path/to/qlib_data")
converter.ensure_calendar()           # 先确保有日K日历
converter.generate_min_calendar("1min")  # 生成 1min 日历
converter.generate_min_calendar("5min")  # 生成 5min 日历
```

### 静态方法

#### `code_to_qlib_dir(code: str) -> str`

将纯数字股票代码映射为 qlib 目录名。

```python
KLineToQlib.code_to_qlib_dir("600519")   # → "sh600519"
KLineToQlib.code_to_qlib_dir("000001")   # → "sz000001"
KLineToQlib.code_to_qlib_dir("830799")   # → "bj830799"
```

### 核心方法

#### `day_kline_to_qlib` — 写入日 K 数据

```python
def day_kline_to_qlib(
    self, code: str, kline_data: List[Dict],
    mode: str = "append", qlib_dir: Optional[str] = None,
) -> bool
```

**写入模式**：`append`（追加合并）/ `overwrite`（覆盖）
**写入字段**：`open`, `high`, `low`, `close`, `volume`, `amount`, `vwap`

#### `min_kline_to_qlib` — 写入高频 K 线数据

```python
def min_kline_to_qlib(
    self, code: str, kline_data: List[Dict], freq: str = "1min",
    mode: str = "append", qlib_dir: Optional[str] = None,
) -> bool
```

**前提条件**：对应频率的日历文件必须存在。

#### `check_local_coverage` — 检查本地数据覆盖范围

```python
def check_local_coverage(
    self, code: str, field: str = "close", freq: str = "day",
    qlib_dir: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int]]
```

返回 `(start_idx, end_idx)`，若不存在返回 `(None, None)`。

#### `get_missing_range` — 计算缺失数据范围

```python
def get_missing_range(self, code: str, start_date: str, end_date: str) -> Optional[Tuple[str, str]]
```

返回 `(fetch_start, fetch_end)` 或 `None`（已覆盖）。

---

## 批量下载入口（download.py）

### CLI 使用

```bash
# 使用 pip 安装后的命令行工具
kline-download --start 2020-01-02 --end 2026-05-15 --pool all

# 或通过 Python 模块运行
python -m kline_fetcher.download --start 2020-01-02 --end 2026-05-15 --pool all

# 日K全量下载
kline-download --start 2020-01-02 --end 2026-05-15 --pool all --full

# 5min 高频数据下载
kline-download --start 2026-01-02 --end 2026-05-15 --pool all --freq 5min

# 指定 qlib 数据目录
kline-download --start 2020-01-02 --end 2026-05-15 --pool all --qlib-data-dir /path/to/qlib_data
```

**CLI 参数**：

| 参数 | 必填 | 默认值 | 说明 |
|------|------|-------|------|
| `--start` | 是 | - | 开始日期（YYYY-MM-DD） |
| `--end` | 是 | - | 结束日期（YYYY-MM-DD） |
| `--pool` | 否 | all | 股池：all / csi300 / csi500 / csi800 / csi1000 / csiall |
| `--full` | 否 | False | 强制全量下载（默认增量） |
| `--freq` | 否 | day | 频率：day / 1min / 5min |
| `--pages` | 否 | 0 | 高频翻页次数（0=自动计算） |
| `--qlib-data-dir` | 否 | 环境变量 | qlib 数据目录路径 |

### Python API

```python
from kline_fetcher.download import load_stock_pool, download_day_kline, download_min_kline

# 加载股池
stocks = load_stock_pool("csi300")

# 批量下载日K
status = download_day_kline("2020-01-02", "2026-05-15", "all", incremental=True)

# 批量下载 5min 数据
status = download_min_kline("2026-01-02", "2026-05-15", "all", freq="5min")

# 指定 qlib 数据目录
status = download_day_kline("2020-01-02", "2026-05-15", "all", qlib_data_dir="/path/to/qlib_data")
```

---

## 数据格式

### API 原始数据单位转换

| 字段 | API 原始字段 | 原始单位 | 转换公式 | 目标单位 |
|------|------------|---------|---------|---------|
| 开盘价 | OpenPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 最高价 | HighPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 最低价 | LowPrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 收盘价 | ClosePrice | 万分之一元 | ÷ 1,000,000 | 元 |
| 成交量 | PeriodVolume | 股 | 直接使用 | 股 |
| 成交额 | PeriodTurnover | 万元 | ÷ 10,000 | 元 |
| 时间 | Time | 14 位整数 | 格式化 | YYYY-MM-DD [HH:MM:SS] |

### qlib bin 文件格式

- **编码**：float32 小端序（`<f`）
- **结构**：`[start_idx, data[0], data[1], ..., data[n-1]]`
- **start_idx**：数据在交易日历中的起始索引
- **对齐**：数据按交易日历对齐，非交易日留 NaN
- **VWAP**：由 `amount / volume` 计算，volume=0 时为 NaN

### 文件路径规则

| 数据类型 | 路径模板 | 示例 |
|---------|---------|------|
| 日K | `{qlib_data_dir}/features/{qlib_dir}/{field}.day.bin` | `qlib_data/features/sh600519/close.day.bin` |
| 1min | `{qlib_data_dir}/features/{qlib_dir}/{field}.1min.bin` | `qlib_data/features/sh600519/close.1min.bin` |
| 5min | `{qlib_data_dir}/features/{qlib_dir}/{field}.5min.bin` | `qlib_data/features/sh600519/close.5min.bin` |

### 写入字段

`open`, `high`, `low`, `close`, `volume`, `amount`, `vwap`

---

## 完整使用示例

### 场景1：获取单只股票日 K 并写入 qlib

```python
from kline_fetcher import KLineFetcher, KLineToQlib

fetcher = KLineFetcher()
converter = KLineToQlib()

data = fetcher.fetch_day_kline("600519", begindate="20240101", enddate="20260515")
if data:
    ok = converter.day_kline_to_qlib("600519", data, mode="append")
    print(f"写入{'成功' if ok else '失败'}")
```

### 场景2：获取高频数据并写入 qlib

```python
from kline_fetcher import MinKLineFetcher, KLineToQlib

fetcher = MinKLineFetcher()
converter = KLineToQlib()

data = fetcher.fetch_kline("600519", freq="5min", starttime="2026-05-08 09:30", count=240)
if data:
    ok = converter.min_kline_to_qlib("600519", data, freq="5min", mode="append")
    print(f"写入{'成功' if ok else '失败'}，共 {len(data)} 条")
```

### 场景3：增量更新检查

```python
from kline_fetcher import KLineToQlib

converter = KLineToQlib()

start, end = converter.check_local_coverage("600519")
if start is not None:
    print(f"日K覆盖: {converter.dates[start]} ~ {converter.dates[end]}")

missing = converter.get_missing_range("600519", "2020-01-02", "2026-05-15")
if missing:
    print(f"需要下载: {missing[0]} ~ {missing[1]}")
```

### 场景4：批量下载

```python
from kline_fetcher.download import download_day_kline, download_min_kline

status = download_day_kline("2020-01-02", "2026-05-15", "all", incremental=True)
downloaded = sum(1 for v in status.values() if v == "downloaded")
skipped = sum(1 for v in status.values() if v == "up_to_date")
print(f"下载={downloaded}, 跳过={skipped}")

status = download_min_kline("2026-01-02", "2026-05-15", "all", freq="5min")
```

### 场景5：自定义数据目录

```python
from kline_fetcher import KLineFetcher, KLineToQlib

# 自定义配置文件
fetcher = KLineFetcher(config_path="/path/to/my_config.yaml")

# 自定义 qlib 数据目录
converter = KLineToQlib(qlib_data_dir="/path/to/qlib_data")
```

### 场景6：在 qlib 中读取数据

```python
import qlib
from qlib.data import D

qlib.init(provider_uri="/root/Projects/0.qlib_pro/qlib_data", region="cn")

df = D.features(["SH600519"], ["$close"], start_time="2020-01-02", end_time="2026-05-15")
df = D.features(["SH600519"], ["$close"], start_time="2026-05-08", end_time="2026-05-15", freq="5min")
```

---

## 测试

项目测试位于 `tests/` 目录，分两类：

### 单元测试（默认运行，无需 API）

```bash
pytest                      # 默认运行，跳过集成测试
```

- `test_append_bin.py`：`_append_bin` 增量合并逻辑（7 个场景：新建/相邻/间隙/重叠/子集/前插）

### 集成测试（需真实 API，默认跳过）

```bash
# 需先配置 API 地址
export KLINE_API_BASE_URL=http://<your-api-host>:<port>
pytest -m integration       # 显式启用集成测试
```

- `test_concept_plates.py`：概念板块 4 个方法（unittest 风格）
- `test_split_interfaces.py`：v2.1.0 拆分后三类（KLineFetcher/MinKLineFetcher/ConceptPlateFetcher）端到端验证（27 项，含字段完整性、继承关系、翻页等）

集成测试通过 `integration` marker 标记，默认 `addopts="-m 'not integration'"` 确保无 API 环境下 CI 不失败。

---

## 向后兼容

### v2.1.0 拆分兼容

v2.1.0 将原 `fetcher.py`（单文件单类）拆分为 `_base.py` / `min_kline.py` / `concept_plate.py`。旧导入路径仍可用（`fetcher.py` 为兼容垫片）：

```python
# 旧方式（v2.1.0 前的代码，仍然有效）
from kline_fetcher.fetcher import KLineFetcher

# 新方式（v2.1.0+ 推荐，按需导入）
from kline_fetcher import KLineFetcher, MinKLineFetcher, ConceptPlateFetcher
```

**唯一破坏**：`KLineFetcher` 基类不再直接含分钟K/概念板块方法，需改用对应子类：
- `fetch_min_kline` / `fetch_kline` → `MinKLineFetcher`
- `get_all_concept_plates` 等 → `ConceptPlateFetcher`

---

## 与 data/ 模块的区别

| 维度 | data/ (iFinD) | kline-fetcher (中焯 API) |
|------|--------------|------------------------|
| 数据源 | iFinD HTTP API | 中焯行情 API |
| 认证 | access_token + refresh_token | 无需认证 |
| 概念板块 | 支持 | 支持 |
| 批量查询 | 支持（多只股票一次请求） | 仅单只查询 |
| 额度限制 | 周额度/月额度（500万条/周） | 未知（暂无限制） |
| 复权方式 | 前复权/后复权可选 | 前复权（cqtype=1） |
| 高频分页 | 不支持 | locator 自动翻页 |
| 大范围日K | 支持 | 分段下载（每段 ≤1500 条） |
| 安装方式 | 项目内模块 | pip install -e . |

---

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 早期日期价格为负 | 前复权 + 多次分红导致 | 正常现象，不影响收益率计算 |
| `fetch_day_kline` 返回 None | 日期范围 >1500 条 | 使用分段下载或 `download_day_kline` |
| `min_kline_to_qlib` 返回 False | 缺少日历文件 | 先生成 `qlib_data/calendars/{freq}.txt` |
| `fetch_kline` 返回 None | starttime 格式错误 | 必须为 `"yyyy-mm-dd HH:mm"` 格式 |
| 北交所 920xxx 股票目录错误 | 旧版未支持 920 前缀 | 已修复，920 映射为 bj + market=103 |
| `ModuleNotFoundError: No module named 'kline_fetcher'` | 未安装包 | `pip install -e /root/Projects/0.qlib_pro/data_v2` |
