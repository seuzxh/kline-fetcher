# kline-fetcher 架构文档

> 适用版本：v3.0.x。本文档描述项目的整体架构、模块划分与数据流。
> 接口签名与参数明细见 [api-reference.md](api-reference.md)，实现层面的设计决策见 [design.md](design.md)。

## 1. 项目定位

kline-fetcher 是一个 **A 股行情数据获取与 Qlib 格式转换工具**，定位为量化回测框架（Qlib）的数据管道上游：

```
中焯行情 API（第三方数据源）
        │
        ▼
  kline-fetcher（本项目）
  ├─ 获取层：抓取日K/分钟K/分时/概念板块数据并统一单位
  ├─ 调度层：按股池批量下载、增量判断
  └─ 转换层：对齐交易日历，写入 qlib bin 格式
        │
        ▼
  qlib_data/ 目录（calendars + instruments + features）
        │
        ▼
  Qlib 回测/研究框架
```

设计目标：

1. **单一职责分层**：请求、解析、调度、存储各自独立，任一层可单独测试；
2. **数据正确性优先**：单位换算、复权因子、脏数据防御都有实测依据和单元测试；
3. **增量友好**：后复权存储 + 增量追加，历史数据不因除权而失效；
4. **向后兼容**：v2.1.0 前的旧导入路径通过垫片保留。

## 2. 模块划分

```
kline-fetcher/
├── pyproject.toml                # 包元数据、依赖、CLI 入口声明
├── README.md                     # 面向使用者的完整文档（含教程与示例）
├── AGENTS.md                     # AI 代理工作说明（仓库根目录，供工具读取）
├── docs/                         # 项目文档
│   ├── architecture.md           # 本文档：架构
│   ├── design.md                 # 技术方案：复权/存储/增量等设计决策
│   ├── api-reference.md          # 包 API 参考（类/方法/参数/返回值）
│   ├── concept_plate_api.md      # 概念板块接口深度文档（实测响应结构/分页/已知限制）
│   ├── CHANGELOG.md              # 版本变更记录
│   ├── REVIEW_ISSUES.md          # code review 待办跟踪
│   └── API/概念板块请求API.md      # 中焯概念板块接口原始抓包记录（上游参考）
├── tests/                        # 测试（单元测试默认运行，集成测试需 API）
└── kline_fetcher/                # Python 包
    ├── __init__.py               # 包入口：导出公共 API，__version__
    ├── _base.py                  # KLineFetcher 基类：共享底座 + 日K方法 + AdjustType
    ├── min_kline.py              # MinKLineFetcher(KLineFetcher)：分钟K方法
    ├── concept_plate.py          # ConceptPlateFetcher(KLineFetcher)：概念板块方法
    ├── trend.py                  # TrendFetcher(KLineFetcher)：分时数据方法
    ├── fetcher.py                # 兼容垫片：保留 v2.1.0 前的旧导入路径
    ├── converter.py              # KLineToQlib：日历管理 + bin 读写 + 增量追加
    ├── download.py               # 批量下载入口（函数 + kline-download CLI）
    ├── server.py                 # 在线调试服务（FastAPI Swagger UI + kline-server CLI，可选依赖）
    └── config/
        └── kline_config.yaml     # 默认配置（API 行为、K线参数、字段映射）
```

各模块职责边界：

| 模块 | 职责 | 不负责 |
|------|------|--------|
| `_base.py` | HTTP 请求/限流/重试、参数构造、单位换算、K线解析、日K与日历方法 | 分钟K翻页、板块、分时等特定接口逻辑 |
| `min_kline.py` | freq→klinetype 映射、locator 翻页、去重排序 | 请求与解析（继承基类） |
| `concept_plate.py` | 板块列表/板块K线/成份股/所属板块 4 个接口 | 个股行情 |
| `trend.py` | 分时参数构造（Action=10001）、盘前/盘中数据解析 | K线数据 |
| `converter.py` | 交易日历（日/分钟）、bin 文件读写、增量合并、覆盖检查 | 网络请求（除日历生成外） |
| `download.py` | 股池加载、批量调度、增量跳过、进度统计 | 数据格式细节（委托 converter） |
| `server.py` | 在线调试服务：获取类方法 → REST 端点，Swagger UI（可选依赖） | bin 写入（只读端点，防误写） |

## 3. 类继承结构

v3.0.0 将原 792 行单文件 `fetcher.py` 拆分为继承体系：

```
KLineFetcher (_base.py)                  ← 共享底座 + 日K方法
  ├── MinKLineFetcher (min_kline.py)     ← + 分钟K方法
  ├── ConceptPlateFetcher (concept_plate.py) ← + 概念板块方法
  └── TrendFetcher (trend.py)            ← + 分时数据方法

KLineToQlib (converter.py)               ← 独立类，不继承（转换层）
```

**拆分动机**：

- 单类职责过重，四类接口（日K/分钟K/板块/分时）参数构造与解析逻辑差异大；
- 继承复用共享底座（`_request`/`_build_params`/`_parse_kline_items`/单位换算），子类只写差异部分；
- 用户按需导入所需子类，API 表面积更小。

**兼容垫片**：`fetcher.py` 重新导出全部符号，旧路径 `from kline_fetcher.fetcher import KLineFetcher` 仍可用。唯一破坏：分钟K/板块方法需改用对应子类调用。

## 4. 数据流

以「批量下载日K」为例（`download.py` 主流程）：

```
load_stock_pool(pool)                    # instruments/all.txt → [(code, market, qlib_dir)]
        │
        ▼
ensure_calendar(fetcher)                 # 无 day.txt 时从上证指数日K推导交易日历
        │
        ▼
按日期分段（>1500 交易日切段，规避 API 单次条数上限）
        │
        ▼
逐股票循环：
  ├─ check_local_coverage()              # 增量判断：本地已覆盖段则跳过
  ├─ fetch_day_kline_with_factor()       # 分别取 hfq + none，按日期对齐算 factor
  │      ├─ fetch_day_kline(adjust="hfq")
  │      └─ fetch_day_kline(adjust="none")
  │      → factor = hfq_close / none_close（校验失败整条置 NaN）
  ├─ 按 [start, end] 过滤
  └─ day_kline_to_qlib(mode="append")    # 对齐日历 → _append_bin 增量合并
        │
        ▼
{qlib_data_dir}/features/sh600519/*.day.bin
```

分钟K流程类似，差异点：需先生成分钟日历（`generate_min_calendar`）、翻页次数自动计算、增量跳过带停牌容差。

## 5. Qlib 数据目录结构

```
{qlib_data_dir}/
├── calendars/
│   ├── day.txt           # 交易日历，每行 "2024-01-02"（由上证指数日K推导）
│   ├── 1min.txt          # 每交易日 240 条，"2024-01-02 09:31:00" ~ "15:00:00"
│   └── 5min.txt          # 每交易日 48 条
├── instruments/
│   ├── all.txt           # 全市场股票，每行 "sh600519\t股票名"（股池文件同格式）
│   └── csi300.txt 等
└── features/
    └── sh600519/         # qlib_dir 命名：sh/sz/bj + 6 位代码
        ├── open.day.bin  # 7 个字段 × 每种频率各一个文件
        ├── high.day.bin
        ├── low.day.bin
        ├── close.day.bin
        ├── volume.day.bin
        ├── factor.day.bin
        └── vwap.day.bin
```

bin 文件格式（Qlib 标准）：float32 小端序；首元素为该股票数据在日历中的起始索引；其后为对齐日历的数据数组，非交易日/缺失/脏数据槽位为 NaN。

## 6. 配置体系

三级优先（高 → 低）：

1. **环境变量**：`KLINE_API_BASE_URL`（API 地址，必填）、`KLINE_CONFIG_PATH`（自定义配置路径）、`QLIB_DATA_DIR`（数据目录）；
2. **自定义配置文件**：构造 `KLineFetcher(config_path=...)` 传入；
3. **包内默认配置**：`kline_fetcher/config/kline_config.yaml`。

API 地址不进配置文件（避免敏感地址提交入库），只走环境变量或显式覆盖 `api.base_url`。

## 7. 测试结构

| 类型 | 触发方式 | 覆盖内容 |
|------|---------|---------|
| 单元测试（默认） | `pytest` | `_append_bin` 全场景、`_build_min_arrays` 缺 time 处理、factor 数值正确性（含脏数据置 NaN）、日历边界（11:30/15:00、240 条）、包结构与方法归属 |
| 集成测试 | `pytest -m integration` | 三类 fetcher 端到端（各复权/5 频率/错误输入）、概念板块 4 方法、TrendFetcher（需真实 API） |

单元测试全部 mock 网络层，不依赖 API 即可在 CI 运行。

## 8. 相关文档

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 使用教程、完整示例、常见问题 |
| [api-reference.md](api-reference.md) | 全部公开类/方法/参数/返回值参考 |
| [concept_plate_api.md](concept_plate_api.md) | 概念板块接口深度文档（实测） |
| [design.md](design.md) | 复权方案、bin 格式、增量追加、日历对齐等设计决策 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [API/概念板块请求API.md](API/概念板块请求API.md) | 上游接口原始抓包记录 |
