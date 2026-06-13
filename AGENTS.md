# kline-fetcher 项目说明

## 项目概述

kline-fetcher 是一个 A 股 K 线数据获取与 Qlib 格式转换工具（v2.0.0）。它从中焯行情 API 获取股票行情数据，转换为 Qlib 标准的 `.bin` 格式，供量化回测框架使用。

## 架构

```
kline_fetcher/
├── __init__.py          # 包入口，导出 KLineFetcher, KLineToQlib, AdjustType
├── fetcher.py           # API 请求层：获取K线数据、概念板块等
├── converter.py         # 转换层：K线数据 → qlib bin 格式
├── download.py          # 批量下载入口 + CLI
└── config/
    └── kline_config.yaml # 默认配置
```

数据流：`API → fetcher.py (获取+单位转换) → download.py (批量调度) → converter.py (对齐日历+写入bin)`

## 核心类

### KLineFetcher (fetcher.py)

从中焯行情 API 获取行情数据。自动推断市场代码、限流、重试。

**关键方法**：

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `fetch_day_kline(code, count, market, begindate, enddate, adjust)` | 获取日K线 | `List[Dict]` 或 `None` |
| `fetch_day_kline_with_factor(code, count, market, begindate, enddate)` | 获取日K线（含factor计算） | `List[Dict]` 或 `None` |
| `fetch_min_kline(code, freq, count, market, pages, adjust)` | 获取分钟K线 | `List[Dict]` 或 `None` |
| `fetch_kline(code, freq, starttime, count, market, adjust)` | 按时间范围获取K线 | `List[Dict]` 或 `None` |
| `fetch_trade_calendar(start_year, end_year)` | 获取交易日历 | `List[str]` 或 `None` |
| `get_all_concept_plates()` | 获取所有概念板块 | `List[Dict]` 或 `None` |
| `get_concept_plate_kline(plate_code, count, market)` | 获取板块K线 | `List[Dict]` 或 `None` |
| `get_concept_plate_stocks(plate_code, start, count)` | 获取板块成份股 | `List[Dict]` 或 `None` |
| `infer_market(code)` (静态) | 推断市场代码 | `int` |

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

### KLineToQlib (converter.py)

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

### download.py

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

**分钟K下载流程**（`download_min_kline`）：
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
  base_url: http://183.242.5.14:7778   # API 地址
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
kline_type_map:                          # 频率→API代码映射
  day: '500'
  1min: '501'
  5min: '502'
  15min: '565'
  30min: '566'
  60min: '567'
  week: '561'
  month: '562'
market_map:                              # 市场→代码映射
  sh: 1
  sz: 0
  bj: 103
qlib_fields:                             # 写入 qlib 的字段列表
  - open
  - high
  - low
  - close
  - volume
  - factor
  - vwap
```

## 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `KLINE_CONFIG_PATH` | 自定义配置文件路径 | 包内 `config/kline_config.yaml` |
| `QLIB_DATA_DIR` | Qlib 数据目录 | `/root/Projects/0.qlib_pro/qlib_data` |

## v2.0.0 不兼容变更

1. 默认复权方式从前复权(cqtype=1)改为后复权(cqtype=2)
2. 新增 `factor` 字段，移除 `amount` 字段
3. `volume` 改为后复权成交量（`不复权成交量 / factor`）
4. 已有数据需全量替换
