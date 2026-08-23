# kline-fetcher API 参考

> 适用版本：v3.1.0（monorepo 双包：`tzt-api` + `kline-qlib`）。所有公开类与方法的参数、返回值说明。
> 设计决策背景见 [design.md](design.md)。方法默认返回 `None` 表示请求失败（不抛异常），日志含失败原因。

## 目录

- [导入方式](#导入方式)
- [AdjustType 复权枚举](#adjusttype-复权枚举)
- [KLineFetcher 基类](#klinefetcher-基类)
- [MinKLineFetcher 分钟K线](#minklinefetcher-分钟k线)
- [ConceptPlateFetcher 概念板块](#conceptplatefetcher-概念板块)
- [TrendFetcher 分时数据](#trendfetcher-分时数据)
- [KLineToQlib 数据转换](#klinetoqlib-数据转换)
- [download 批量下载与 CLI](#download-批量下载与-cli)
- [server 在线调试服务](#server-在线调试服务)
- [配置与环境变量](#配置与环境变量)
- [返回数据结构速查](#返回数据结构速查)

## 导入方式

```python
# 推荐（v3.1.0+）：按包导入
from tzt_api import (
    KLineFetcher,          # 基类（日K + 共享底座）
    MinKLineFetcher,       # 分钟K线
    ConceptPlateFetcher,   # 概念板块
    TrendFetcher,          # 分时数据
    AdjustType,            # 复权方式枚举
)
from kline_qlib import KLineToQlib          # K线 → qlib bin 转换

# 兼容（compat-kline-fetcher 兼容壳，deprecated，迁移完成后撤）
from kline_fetcher.fetcher import KLineFetcher  # 仍可用
```

## AdjustType 复权枚举

`IntEnum`：`AdjustType.none = 0`、`AdjustType.qfq = 1`（前复权）、`AdjustType.hfq = 2`（后复权）。

各方法 `adjust` 参数统一接受字符串 `"qfq"` / `"hfq"` / `"none"`（不区分大小写）、数字，或 `None`（使用配置文件默认值 `kline.cqtype`，当前为后复权）。非法值抛 `ValueError`。

## KLineFetcher 基类

```python
KLineFetcher(config_path: Optional[str] = None)
```

构造时加载配置（优先级：`config_path` 参数 > `KLINE_CONFIG_PATH` 环境变量 > 包内默认配置）。请求前必须设置 `KLINE_API_BASE_URL` 环境变量，否则抛 `EnvironmentError`。

### 静态方法

#### `infer_market(code: str) -> int`

推断市场代码（`sh=1, sz=0, bj=103`）。判断顺序：显式 sh/sz/bj 前缀 → 指数白名单（`INDEX_CODE_MAP`）→ 399 前缀深市指数 → 个股号段（600/601/603/605/688/689 沪，000/001/002/003/300/301 深，8/4/920 北，默认深）。

⚠️ 裸码 `"000001"` 按指数优先返回沪市（上证指数）。取深市个股请用 `"sz000001"` 或显式 `market=0`。

#### `is_index(code: str) -> bool`

code 是否按指数处理（显式 sz/bj 前缀按个股返回 False）。

#### `get_index_info(code: str) -> Optional[tuple]`

按指数处理时返回 `(名称, 市场代码)`，否则返回 `None`。

### `fetch_day_kline`

```python
fetch_day_kline(code, count=None, market=None, begindate=None,
                enddate=None, adjust=None) -> Optional[List[Dict]]
```

| 参数 | 说明 |
|------|------|
| `code` | 股票/指数代码，`"600519"` / `"SH600519"` 等 |
| `count` | 条数（取最新 N 条），与日期参数二选一 |
| `market` | 市场代码，`None` 时自动推断 |
| `begindate` / `enddate` | 日期范围，格式 `"YYYYMMDD"`；任一非空时 count 失效 |
| `adjust` | 复权方式，见 [AdjustType](#adjusttype-复权枚举) |

返回 K 线字典列表（结构见文末速查），失败/无数据返回 `None`。

### `fetch_day_kline_with_factor`

```python
fetch_day_kline_with_factor(code, count=None, market=None, begindate=None,
                            enddate=None) -> Optional[List[Dict]]
```

获取**后复权**日K并计算复权因子（批量下载日K的标准入口）。内部发起两次请求（hfq + none），按日期对齐：

```
factor = hfq_close / none_close      # 后复权价/不复权价，恒 >= 1
volume = none_volume / factor        # 后复权成交量
```

脏数据防御：hfq 四价任一 ≤ 0/缺失、none_close 为 0/缺失、factor < 1 时，整条记录 OHLCV+factor 置 NaN 并打 warning（数据源 bug 场景，如实测 600180 复权错乱数据）。hfq 或 none 任一请求失败返回 `None`。

### `fetch_trade_calendar`

```python
fetch_trade_calendar(start_year=2000, end_year=2030,
                     index_code="000001", market=1) -> Optional[List[str]]
```

以上证指数日K推导交易日历，返回升序日期列表 `["2024-01-02", ...]`。

### `get_stock_info`

```python
get_stock_info(code, market=None) -> Optional[Dict]
```

返回 `{"code", "name", "market_sn"}`，失败返回 `None`。

## MinKLineFetcher 分钟K线

继承 `KLineFetcher` 全部方法，新增：

### `fetch_min_kline`

```python
fetch_min_kline(code, freq="1min", count=None, market=None,
                pages=1, adjust=None) -> Optional[List[Dict]]
```

| 参数 | 说明 |
|------|------|
| `freq` | `"1min" / "5min" / "15min" / "30min" / "60min"`（对应 klinetype 501/502/565/566/567） |
| `count` | 单页条数（负数 = 从最新向前） |
| `pages` | 翻页次数。`<=1` 单页请求；`>1` 用响应中的 `{klinetype}.locator` 逐页向前翻，自动按 `date time` 去重排序 |

返回数据自带 `date`/`time` 字段，客户端自行按时间切片。注意 1min 时间戳为周期结束时刻（09:31~11:30、13:01~15:00）。

## ConceptPlateFetcher 概念板块

继承 `KLineFetcher` 全部方法，新增（板块市场代码固定 `market=44`）。**完整接口文档（实测响应结构、分页、已知限制）见 [concept_plate_api.md](concept_plate_api.md)**，已知限制摘要：

- `get_all_concept_plates()` **只返回按涨幅排序的前 30 个**（总数约 390，取全量需按 `start` 翻页，示例见深度文档 1.4）；
- `get_concept_plate_stocks()` 返回**首项是板块自身**（`block.include=1` 所致），成份股需过滤 `market != 44`；
- `get_stock_concept_plates()` 基于**官方关联属性 900/901/923**（CoIndBlkIdx/CoBlkIdx/RegionBlkIdx），实测可用，返回带 `type` 标注（industry/region/concept）。

| 方法 | 签名 | 返回 |
|------|------|------|
| `get_all_concept_plates` | `() -> Optional[List[Dict]]` | 概念板块（前 30）：`{code, name, market, price?, change?, change_pct?}`（行情字段为 API 原始整数格式） |
| `get_concept_plate_kline` | `(plate_code, count=-220, market=44) -> Optional[List[Dict]]` | 板块日K（不复权 `cqType=0`），结构同股票日K |
| `get_concept_plate_stocks` | `(plate_code, start=0, count=10) -> Optional[List[Dict]]` | 成份股分页（首项为板块自身）：`{code, name, market, price?, change?, change_pct?, high?, low?}` |
| `get_stock_concept_plates` | `(code, market=None, plate_type=None) -> Optional[List[Dict]]` | 股票所属板块：`{code, name, market, type}`；`market` 自动推断，`plate_type` 可选 `"concept"/"industry"/"region"` 过滤 |

## TrendFetcher 分时数据

继承 `KLineFetcher` 全部方法，新增：

| 方法 | 签名 | 说明 |
|------|------|------|
| `fetch_intraday_trend` | `(code, market=None) -> Optional[Dict]` | 当日分时（`date=0, daycount=0`） |
| `fetch_history_trend` | `(code, date, market=None) -> Optional[Dict]` | 历史分时，`date` 格式 `"YYYYMMDD"` |
| `fetch_trend` | `(code, date=None, market=None) -> Optional[Dict]` | 自动判断：`date` 为 `None`/`"0"` 取当日，否则取历史 |

返回结构：

```python
{
    "market_date": "20260612",   # 市场日期
    "pre_market": [              # 集合竞价（09:15-09:25，Action=10001 CallTrend）
        {"date", "time", "ref_price",          # 参考价（元）
         "matched_vol", "non_matched_vol_buy", "non_matched_vol_sell",  # 匹配/未匹配量（股）
         "phase": "pre-market"}
    ],
    "trading": [                 # 盘中分时（09:30-15:00，TrendOp）
        {"date", "time", "last_price", "avg_price",   # 最新价/均价（元）
         "volume", "turnover", "phase": "trading"}    # 成交量（股）/成交额（元）
    ],
}
```

## KLineToQlib 数据转换

```python
KLineToQlib(qlib_data_dir: Optional[str] = None)
```

构造时加载 `QLIB_DATA_DIR`（或参数指定目录）下的日历与分钟日历到内存索引。写入字段固定为 `["open", "high", "low", "close", "volume", "factor", "vwap"]`。

### 日历方法

| 方法 | 说明 |
|------|------|
| `ensure_calendar(fetcher=None, start_year=2000, end_year=2030) -> bool` | 本地已有 `day.txt` 则跳过；否则用 fetcher（默认新建 `KLineFetcher`）拉取并落盘 |
| `generate_min_calendar(freq="1min") -> bool` | 由日日历生成分钟日历。1min=240 条/日（09:31~11:30、13:01~15:00），5min=48 条/日；需先 `ensure_calendar` |

### 写入方法

| 方法 | 说明 |
|------|------|
| `day_kline_to_qlib(code, kline_data, mode="append", qlib_dir=None) -> bool` | 日K写入 bin；`mode`：`overwrite` 覆盖 / `append` 增量合并 |
| `min_kline_to_qlib(code, kline_data, freq="1min", mode="append", qlib_dir=None) -> bool` | 分钟K写入 bin；需先加载对应 freq 的分钟日历 |

`kline_data` 为 fetcher 返回的字典列表；数据按日历索引对位，缺失槽 NaN；vwap 由 `amount/volume` 临时计算。

### 查询方法

| 方法 | 说明 |
|------|------|
| `check_local_coverage(code, field="close", freq="day", qlib_dir=None, nan_aware=False) -> (start_idx, end_idx)` | 本地 bin 覆盖的日历索引区间；无文件/损坏返回 `(None, None)`。`nan_aware=True` 时 end 取最后一个非 NaN 槽（检测伪覆盖），全 NaN 返回 `(None, None)` |
| `get_missing_range(code, start_date, end_date) -> Optional[(str, str)]` | 结合本地覆盖计算需补拉的日期范围；已覆盖返回 `None` |
| `code_to_qlib_dir(code) -> str`（静态） | 代码 → qlib 目录名（`sh600519`/`sz000001`/`bj830799`；指数白名单按指数市场） |

## download 批量下载与 CLI

### 函数

```python
load_stock_pool(pool_name, instruments_dir=None) -> list
# 读取 instruments/{pool}.txt → [(code, market, qlib_dir)]
# 股池：all / csi300 / csi500 / csi800 / csi1000 / csiall，或直接给 "xxx.txt"

download_day_kline(start, end, pool, incremental=True,
                   qlib_data_dir=None, adjust=None) -> dict
# 日K批量下载（固定 hfq+factor 口径，adjust 参数当前不影响日K）。
# 日期范围 >1500 交易日自动分段；incremental=True 时按本地覆盖跳过。
# 返回 {code: "downloaded"/"up_to_date"/"download_failed"/"write_failed"}

download_min_kline(start, end, pool, freq="1min", incremental=True,
                   pages=1, qlib_data_dir=None, adjust=None) -> dict
# 分钟K批量下载；pages<=1 时按日期范围自动计算翻页次数；
# 增量跳过带停牌容差（覆盖到 end 前一天即视为最新）
```

### CLI

```bash
kline-download --start 2024-01-01 --end 2024-12-31 [options]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--start` / `--end` | 必填 | 日期范围（YYYY-MM-DD） |
| `--pool` | `all` | 股池名称 |
| `--full` | 关 | 强制全量下载（默认增量） |
| `--freq` | `day` | `day` / `1min` / `5min` |
| `--pages` | `0`（自动） | 高频翻页次数 |
| `--qlib-data-dir` | `QLIB_DATA_DIR` | qlib 数据目录 |
| `--adjust` | 配置默认 | `qfq` / `hfq` / `none`（仅对分钟K生效） |

## server 在线调试服务

`kline_qlib/server.py`：FastAPI 薄包装，把获取类方法映射为 REST 端点，自带 Swagger UI（`/docs`）与 ReDoc（`/redoc`）。可选依赖：`pip install 'kline-qlib[server]'`。

```bash
kline-server [--host 127.0.0.1] [--port 8000] [--reload]
uvicorn kline_qlib.server:app           # 等效启动方式（兼容壳 kline_fetcher.server 仍可用）
```

| 分组 | 端点 | 对应方法 |
|------|------|---------|
| 日K线 | `GET /api/day-kline` | `fetch_day_kline` |
| | `GET /api/day-kline-with-factor` | `fetch_day_kline_with_factor` |
| | `GET /api/trade-calendar` | `fetch_trade_calendar` |
| | `GET /api/stock-info` | `get_stock_info` |
| 分钟K线 | `GET /api/min-kline` | `fetch_min_kline` |
| 分时数据 | `GET /api/trend` | `fetch_trend`（date 缺省取当日） |
| | `GET /api/trend/intraday` | `fetch_intraday_trend` |
| | `GET /api/trend/history` | `fetch_history_trend` |
| 概念板块 | `GET /api/concept/plates` | `get_all_concept_plates` |
| | `GET /api/concept/plate-kline` | `get_concept_plate_kline` |
| | `GET /api/concept/plate-stocks` | `get_concept_plate_stocks` |
| | `GET /api/concept/stock-plates` | `get_stock_concept_plates` |
| 本地数据查询 | `GET /api/coverage` | `check_local_coverage`（只读，额外返回起止日期） |

**行为约定**：

- 查询参数与 Python API 同名同义；日期 `YYYYMMDD`、freq/adjust 枚举有表单校验（不合法返回 422）；
- 方法返回 `None` → HTTP 502，`detail` 附说明，具体原因在服务端日志；
- 记录中的 NaN/Inf 序列化为 `null`（JSON 不支持 NaN）；
- 各 Fetcher 以惰性单例共享实例，限流（`request_interval`）全局生效；
- 只暴露读操作（获取/查询），不提供 bin 写入端点；服务无鉴权，默认仅绑定 `127.0.0.1`，勿暴露公网。

## 配置与环境变量

| 环境变量 | 用途 | 默认 |
|----------|------|------|
| `KLINE_API_BASE_URL` | 中焯行情 API 地址（**必填**） | 无，缺失抛 `EnvironmentError` |
| `KLINE_CONFIG_PATH` | 自定义配置文件路径 | 包内 `config/kline_config.yaml` |
| `QLIB_DATA_DIR` | qlib 数据目录 | `/root/Projects/0.qlib_pro/qlib_data` |

`kline_config.yaml` 关键项：`api.request_interval=0.1`（限流）、`api.max_retries=3`、`api.retry_delay=1`、`api.timeout=10`、`kline.cqtype=2`（默认后复权）、`kline.day_count=-1500`、`kline.min_count=-1500`。

## 返回数据结构速查

**日K/分钟K字典**（`fetch_day_kline` / `fetch_min_kline` / 板块K线）：

```python
{
    "date": "2024-01-02",     # 日期
    "time": "09:31:00",       # 时间（仅分钟K；周期结束时刻）
    "open": 10.5,             # 开盘价（元）
    "high": 10.8, "low": 10.2, "close": 10.6,
    "volume": 50000,          # 成交量（股）
    "amount": 530000000.0,    # 成交额（元）
    "factor": 1.05,           # 复权因子（仅 fetch_day_kline_with_factor；
}                             #   脏数据时 OHLCV+factor 整条为 NaN）
```

**bin 文件**：`features/{qlib_dir}/{field}.{freq}.bin`，float32 小端序，首元素为日历起始索引，其余按日历对齐（缺失槽 NaN）。
