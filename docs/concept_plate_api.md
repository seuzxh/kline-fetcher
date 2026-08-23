# 概念板块接口文档

> 实现位置：`kline_fetcher/concept_plate.py`（`ConceptPlateFetcher`）
> 原始抓包参数：[docs/API/概念板块请求API.md](API/概念板块请求API.md)（iOS 客户端抓取，部分参数冗余）
> 本文所有结论基于 **2026-08-22 真实 API 实测**。

## 接口总览

| # | 方法 | Action | 用途 | 实测状态 |
|---|------|--------|------|---------|
| 1 | `get_all_concept_plates()` | 10007 | 概念板块列表 | ✅ 可用，**仅返回前 30 个**（共 390 个，需自行翻页，见 1.4） |
| 2 | `get_concept_plate_kline(plate_code, count, market)` | 10002 | 板块日K线 | ✅ 可用 |
| 3 | `get_concept_plate_stocks(plate_code, start, count)` | 10005 | 板块成份股 | ✅ 可用，**返回首项为板块自身**（见 3.3） |
| 4 | `get_stock_concept_plates(code, market)` | 10000 | 股票所属板块 | ⚠️ **实测不可用**：响应无板块字段，恒返回 `[]`（见 4.3） |

```python
from kline_fetcher import ConceptPlateFetcher

fetcher = ConceptPlateFetcher()
plates = fetcher.get_all_concept_plates()
```

**关键概念**：概念板块市场代码固定为 `market=44`，板块代码为 `99xxxx`（如 `994612` AI芯片）。

---

## 1. get_all_concept_plates — 概念板块列表

### 1.1 签名与请求参数

```python
fetcher.get_all_concept_plates() -> Optional[List[Dict]]
```

| 请求参数 | 值 | 说明 |
|---|---|---|
| `Action` | `10007` | 板块二级列表 |
| `market` | `44` | 概念板块市场 |
| `start` / `count` | `0` / `30` | **硬编码**，未暴露为方法参数（见 1.4） |
| `sort` | `514` | 按涨幅排序 |
| `direction` | `1` | 降序 |
| `groups` | `HQ_StockInfo\|HQ_StockProp` | 字段分组 |
| `subtype` | `1` | 概念板块类型 |

### 1.2 返回值结构（解析后）

```python
[
    {
        "code": "994662",        # 板块代码 (str)
        "name": "锂矿概念",       # 板块名称 (str)
        "market": 44,            # 市场代码 (int)
        "price": 1942300000,     # 最新点位（API 原始整数，÷1e6 = 1942.30）
        "change": 62010000,      # 涨跌（原始整数，÷1e6 = 62.01 点）
        "change_pct": 3297,      # 涨跌幅（原始整数，÷1000 = 3.297%，实测推断）
    },
    ...
]
```

请求失败返回 `None`。

### 1.3 关键原始响应字段（列式数组）

| 字段 | 含义 | 单位 |
|---|---|---|
| `StockCode` / `StockName` / `MarketSN` | 板块代码/名称/市场 | — |
| `QuoteLast` | 最新点位 | 万分之一点（÷1e6） |
| `PxChg` / `PxChgPct` | 涨跌 / 涨跌幅 | ÷1e6 / ÷1000（实测推断） |
| `TurnoverRate` | 换手率 | ÷1000 |
| `Volume` / `Turnover` | 成交量(股) / 成交额(万元) | — |
| `PxChgPct5TD/20TD/60TD/250TD` 等 | 多周期涨跌幅 | ÷1000 |
| `max` | **板块总数**（实测 390） | — |

### 1.4 ⚠️ 分页限制（重要）

方法硬编码 `start=0, count=30`，**只返回按涨幅排序的前 30 个板块**。实测确认：

- 板块总数 `max = 390`（以响应为准，可能随时间变化）
- `start` 翻页有效（start=30/360 均返回下一页，start=390 返回空）
- **单次 `count` 上限 100**（超过报 `ErrorNo=-2300 请求数量不能超过100`）

获取全部板块需自行分页请求（4 次 × 100）：

```python
def get_all_plates_paged(fetcher):
    plates, start = [], 0
    while True:
        params = {
            "Action": 10007, "needtitle": 1, "subtype": 1, "rights": 0,
            "direction": 1, "906.props": "0|2|10|514",
            "start": start, "count": 100,
            "groups": "HQ_StockInfo|HQ_StockProp", "sort": 514,
            "props": "10|510|514|573|4|575|5|574|6|576|7|577|12|13|21|551|513|521|23|906|751|752|753|754|755|756|757|11",
            "market": 44, "Route": 1,
        }
        raw = fetcher._request(params)
        if not raw or not raw.get("StockCode"):
            break
        for i in range(len(raw["StockCode"])):
            plates.append({"code": raw["StockCode"][i], "name": raw["StockName"][i]})
        start += 100
    return plates  # ≈ 390 个
```

---

## 2. get_concept_plate_kline — 板块日K线

### 2.1 签名与请求参数

```python
fetcher.get_concept_plate_kline(plate_code, count=-220, market=44) -> Optional[List[Dict]]
```

| 参数 | 类型/默认 | 说明 |
|---|---|---|
| `plate_code` | `str` | 板块代码，如 `"994612"` |
| `count` | `int = -220` | K线条数，负数=从最新向前 |
| `market` | `int = 44` | 板块市场，保持默认 |

| 请求参数 | 值 | 说明 |
|---|---|---|
| `Action` | `10002` | K线接口（与股票日K同） |
| `klinetype` | `500` | 日K |
| `cqType` | `0` | **驼峰** `cqType`（注意与股票接口的小写 `cqtype` 不同），板块固定不复权 |
| `422.daycount` | `-220` | 硬编码 |
| `500.count` | 传入的 `count` | 实际控制条数 |

### 2.2 返回值结构（解析后，与股票日K一致）

```python
[
    {
        "date": "2026-08-21",
        "open": 1834.32,           # 点位（元）
        "high": 1860.04,
        "low": 1812.21,
        "close": 1843.79,
        "volume": 778229075.0,     # 成交量（股，板块内成份股合计）
        "amount": 40034267461.29,  # 成交额（元）
    },
    ...
]
```

### 2.3 关键原始响应字段（`DayKLine[0][i]`）

| 字段 | 含义 | 单位 |
|---|---|---|
| `HqDate` / `Time` | 日期 / 时间戳 | `20260819` / `20260819000000` |
| `OpenPrice` 等 | 开高低收 | 万分之一（÷1e6） |
| `PeriodVolume` | 成交量 | 股 |
| `PeriodTurnover` | 成交额 | 万元（÷1e4 → 元） |
| `PrevClosePrice` / `TurnoverRate` / `QuantityRelativeRatio` | 昨收 / 换手率 / 量比 | ÷1e6 / ÷1000 / ÷1000 |

---

## 3. get_concept_plate_stocks — 板块成份股

### 3.1 签名与请求参数

```python
fetcher.get_concept_plate_stocks(plate_code, start=0, count=10) -> Optional[List[Dict]]
```

| 参数 | 说明 |
|---|---|
| `plate_code` | 板块代码 |
| `start` | 分页起始（0 起） |
| `count` | 每页数量 |

| 请求参数 | 值 | 说明 |
|---|---|---|
| `Action` | `10005` | 板块成份股 |
| `block` | 传入的 `plate_code` | 板块代码 |
| `block.include` | `1` | **响应包含板块自身**（见 3.3） |
| `routemarkets` | `44` | |

### 3.2 返回值结构（解析后）

```python
[
    {
        "code": "994612",         # ⚠️ 第一项是板块自身（见 3.3）
        "name": "AI芯片",
        "market": 44,
        "price": 1843790000,      # 最新价（÷1e6）
        "change": 2550000,        # 涨跌（÷1e6）
        "change_pct": 138,        # 涨跌幅（÷1000 = 0.138%）
        "high": 1860040000,       # 最高（÷1e6）
        "low": 1812210000,        # 最低（÷1e6）
    },
    {"code": "300192", "name": "科德教育", "market": 0, ...},   # 真正的成份股
    ...
]
```

`market` 字段是各股票的真实市场（0=深 / 1=沪），可直接用于后续行情请求。

### 3.3 ⚠️ 返回首项为板块自身（重要）

因请求固定 `block.include=1`，**响应第一条是板块本身**（code=板块代码、market=44），其后才是成份股。实测 `count=5` 返回 6 条（1 板块 + 5 股票）。

```python
stocks = fetcher.get_concept_plate_stocks("994612", start=0, count=50)
real_stocks = [s for s in stocks if s["market"] != 44]        # 过滤掉板块自身
```

### 3.4 分页与总数

- 响应 `max` 字段 = **成份股总数**（实测 AI芯片 板块 max=40，与 UpQty+DownQty+EqualQty=39+1 吻合）
- `start`/`count` 分页，取全量需循环翻页（过滤板块自身后约 max-1 条）

---

## 4. get_stock_concept_plates — 股票所属板块

### 4.1 签名与请求参数

```python
fetcher.get_stock_concept_plates(code, market) -> Optional[List[Dict]]
```

| 请求参数 | 值 | 说明 |
|---|---|---|
| `Action` | `10000` | 上盘口快照 |
| `codes` | `"{code}\|{market}"` | 如 `"600519\|1"` |
| `groups` | `HQ_StockInfo` | |
| `props` | 长串编号 | 原始抓包参数 |

### 4.2 ⚠️ 实测不可用

实测（600519 贵州茅台）响应中**不含任何 Block/Concept 类字段**，仅有行情与财务字段（`QuoteLast`、`MarketCap`、`PB`、`DynamicPER` 等）。当前实现的双策略解析（字段名匹配 / HQ_StockInfo 分组）均落空，**恒返回 `[]`**（空列表，非 None）。

### 4.3 参数组合测试记录（2026-08-22，共 17 组）

| # | 变体 | 结果 |
|---|------|------|
| 1 | 基线（当前实现参数） | 49 键，无板块字段 |
| 2 | + iOS 客户端指纹参数（TFrom/CFrom/clientversion/uniqueid 等） | 49 键，无变化 |
| 3 | `groups=HQ_StockInfo\|HQ_StockProp` | 87 键，仅多 `HaveBlockFile`（"是否有板块文件"标志位） |
| 4 | groups 变体 + 指纹 | 同 3 |
| 5 | `props` 换 10005 板块类（`710\|560\|514\|...`） | 31 键，无板块字段 |
| 6 | props 变体 + 指纹 | 同 5 |
| 7 | groups + props 双换 | 78 键，仅 `HaveBlockFile` |
| 8-10 | `outtype=0` / `count=100` / `reqlinktype=1` | 均无变化 |
| 11 | StockProp 组 + `needtitle=1` 取 78 个字段中文名 | **TITLE 全量对照无任何板块/概念字段**（仅"是否有板块文件"） |
| 12 | `HandicapAC`（上盘口）内部 14 字段全 dump | 全是快照价量（开高低收/量额），无板块数据 |
| 13-17 | 相邻 Action 试探（10003/10004/10006/10008/10009/10010/10011） | 全部请求失败，无可用替代接口 |

**结论**：`HaveBlockFile=1` 表明板块数据以独立「板块文件」形式存在，但 10000 号请求的任何已知参数组合都不返回板块列表——板块文件应需另外的下载接口（未抓到）。原始抓包文档标注「所属板块从上盘口获取」，与实测不符（上盘口 `HandicapAC` 内无板块数据）。

**建议**：需要股票→板块映射时，改用反向方案——遍历板块列表（1.4）+ 各板块成份股（第 3 节）在客户端构建映射缓存。

---

## 5. 单位换算速查

| 字段类别 | 原始单位 | 换算 | 目标 |
|---|---|---|---|
| 价格/点位（`QuoteLast`、`OpenPrice` 等） | 万分之一 | ÷ 1,000,000 | 元 / 点 |
| 成交额（`Turnover`、`PeriodTurnover`） | 万元 | ÷ 10,000 | 元 |
| 成交量（`Volume`、`PeriodVolume`） | 股 | 直接使用 | 股 |
| 比率类（`PxChgPct`、`TurnoverRate`、`QuantityRelativeRatio`） | 千分之一 | ÷ 1,000 | % |

> 比率类单位为实测推断（PxChgPct=3297 ↔ 实际涨幅 3.297%）；价格/成交额/成交量单位与股票接口一致（见 `_base.py` 注释）。

## 6. 相关测试

- `tests/test_concept_plates.py`：4 方法的集成测试（integration marker，需 API）
- `tests/test_split_interfaces.py::TestConceptPlateFetcher`：字段完整性、分页、market=44 校验
