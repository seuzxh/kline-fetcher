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
| 4 | `get_stock_concept_plates(code, market, plate_type)` | 10000 | 股票所属板块 | ✅ **已修复可用**（官方属性 900/901/923，见 4.1） |

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

> **2026-08-23 修复**：旧实现（复刻 iOS 抓包的 10000 请求）实测恒返回 `[]`（17 组参数试探记录见 4.4）。
> 依据官方《行情3.0股票属性ID》文档改用**关联属性 900/901/923** 后实测可用。

### 4.1 修复方案（当前实现）

```python
fetcher.get_stock_concept_plates(code, market=None, plate_type=None) -> Optional[List[Dict]]
# 每项: {"code": "994612", "name": "AI芯片", "market": 44, "type": "concept"}
```

| 请求参数 | 值 | 说明 |
|---|---|---|
| `Action` | `10000` | 通用属性接口（基础数据-多股票） |
| `codes` | `"{code}\|{market}"` | 如 `"688802\|1"` |
| `props` | `900\|901\|923` | 关联属性：900=CoIndBlkIdx 隶属行业板块指数、901=CoBlkIdx 隶属版块指数（含行业/概念/地域/风格，可多条）、923=RegionBlkIdx 地域板块 |
| `{900,901,923}.props` | `0\|1\|2` | **关联属性必传**：声明关联证券的出参属性（0=代码 1=市场序号 2=名称）。缺省时属性生效但记录为空对象 |
| `count` | `1` | 单股票查询 |

响应结构（outtype=1）：

```json
{
  "CoIndBlkIdx": [{"StockCode": ["991334"], "MarketSN": [44], "StockName": ["半导体类"]}],
  "CoBlkIdx":    [{"StockCode": ["991334", "992023", "994612", "..."],
                   "MarketSN":  [44, 44, 44],
                   "StockName": ["半导体类", "上海", "AI芯片", "..."]}],
  "RegionBlkIdx":[{"StockCode": ["992023"], "MarketSN": [44], "StockName": ["上海"]}]
}
```

**type 标注逻辑**：901 返回全部隶属板块，其中出现在 900（行业）里的标 `industry`、出现在 923（地域）里的标 `region`、其余标 `concept`（概念+风格）。实测与板块代码段一致（991xxx=行业、992xxx=地域、993/994/995xxx=概念/风格）。

**plate_type 过滤**：`"concept"` / `"industry"` / `"region"`，默认 `None` 返回全部。

### 4.2 实测结果（2026-08-23）

| 股票 | 全部板块 | 行业 | 地域 | 概念（节选） |
|---|---|---|---|---|
| 688802 盛美上海 | 19 | 半导体类 | 上海 | AI芯片、国产芯片、算力概念、次新股、融资融券… |
| sz000001 平安银行 | 22 | 银行类 | 广东 | 互联网金融、区块链、沪深300、MSCI中国、深股通… |
| 600519 贵州茅台 | 22 | 酒类 | 贵州 | 白酒、茅指数、超级品牌、行业龙头、沪股通… |

### 4.3 注意事项

- `market` 可选（自动推断，000xxx 裸码按指数优先规则会推断为沪市指数，深市个股请用 `sz000001` 或显式 `market=0`）
- 923（地域）仅沪深京有效，港股等市场响应中可能缺失，实现已做兜底
- 板块代码 market 固定为 44；`name`/`market` 字段在极端缺失响应下可能不出现（防御性解析）

### 4.4 旧实现 17 组参数试探记录（2026-08-22，已废弃，留档）

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
| 18 | **抓包原文逐字重放**（codes=688802\|1 + 全部指纹参数 + ReqTag） | 49 键全量 dump：纯行情/财务字段（最新价 700 元、市值、PER/PB、IsNoProfit=1 等），键名/值/嵌套结构（Bond 空、HandicapAC 快照价量）**均无任何板块内容** |

**当时结论（已被 4.1 推翻）**：`HaveBlockFile=1` 表明板块数据以独立「板块文件」形式存在，10000 请求的已知参数组合都不返回板块列表。**正解**（2026-08-23）：板块归属需通过关联属性 `900|901|923` 显式请求——当时 17 组试探均未涉及关联属性，且缺 `{propID}.props` 时属性即使生效也只返回空对象。旧的「板块列表+成份股反向构建」方案不再需要，但仍适用于需要**全市场股→板块映射**的场景（一次反向构建优于逐股请求）。

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
