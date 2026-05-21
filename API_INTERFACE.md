# kline-fetcher 接口说明文档

## 项目概述

**项目名称**: kline-fetcher  
**版本**: 1.1.0  
**类型**: A股K线数据获取与qlib格式转换工具  
**测试状态**: ✅ 全部通过 (35/35 测试)

---

## 快速开始

### 安装
```python
# 进入项目目录
cd /workspace

# 安装依赖
pip install -e .
```

### 基础导入
```python
from kline_fetcher import KLineFetcher, KLineToQlib
```

---

## 一、KLineFetcher 类 - API 请求封装

### 1.1 初始化

```python
fetcher = KLineFetcher(config_path=None)
```

**参数**:
- `config_path` (可选): 配置文件路径，默认使用环境变量 `KLINE_CONFIG_PATH` 或包内默认配置

---

### 1.2 市场代码推断 - `infer_market()`

根据股票代码前缀自动推断市场编号

```python
market = KLineFetcher.infer_market(code)
```

**参数**:
- `code` (str): 股票代码 (如 "600519", "000001", "830799")

**返回值**:
- `1`: 上海证券交易所 (600/601/603/605/688/689开头)
- `0`: 深圳证券交易所 (000/001/002/003/300/301开头)
- `103`: 北京证券交易所 (8/4/920开头)

**示例**:
```python
KLineFetcher.infer_market("600519")   # 返回 1
KLineFetcher.infer_market("000001")   # 返回 0
KLineFetcher.infer_market("830799")   # 返回 103
```

---

### 1.3 获取日K线 - `fetch_day_kline()`

```python
data = fetcher.fetch_day_kline(code, count=None, market=None, begindate=None, enddate=None)
```

**参数**:
- `code` (str): 股票代码 (如 "600519")
- `count` (int, 可选): 获取数量，负数表示从最新数据往前获取
- `market` (int, 可选): 市场编号，默认自动推断
- `begindate` (str, 可选): 开始日期 (格式: "YYYYMMDD"，如 "20260101")
- `enddate` (str, 可选): 结束日期 (格式: "YYYYMMDD"，如 "20260515")

**返回值**:
- 成功返回 `List[Dict]`，每条数据包含:
  - `date`: 日期 (格式: "YYYY-MM-DD")
  - `open`: 开盘价 (float)
  - `high`: 最高价 (float)
  - `low`: 最低价 (float)
  - `close`: 收盘价 (float)
  - `volume`: 成交量 (float)
  - `amount`: 成交额 (float)
- 失败返回 `None`

**示例**:
```python
# 通过数量获取
data = fetcher.fetch_day_kline("600519", count=100)

# 通过日期范围获取
data = fetcher.fetch_day_kline("600519", begindate="20260101", enddate="20260515")

# 指定市场
data = fetcher.fetch_day_kline("600519", count=50, market=1)
```

---

### 1.4 获取分钟K线 - `fetch_min_kline()`

```python
data = fetcher.fetch_min_kline(code, freq="1min", count=None, market=None, pages=1)
```

**参数**:
- `code` (str): 股票代码 (如 "600519")
- `freq` (str): 频率 ("1min", "5min", "15min", "30min", "60min")
- `count` (int, 可选): 获取数量
- `market` (int, 可选): 市场编号
- `pages` (int): 分页次数 (默认1，不翻页)

**返回值**:
- 成功返回 `List[Dict]`，每条数据包含:
  - `date`: 日期 (格式: "YYYY-MM-DD")
  - `time`: 时间 (格式: "HH:MM:SS")
  - `open`, `high`, `low`, `close`, `volume`, `amount`: 同日K线
- 失败返回 `None`

**示例**:
```python
# 获取1分钟K线
data = fetcher.fetch_min_kline("600519", freq="1min", count=-240)

# 获取5分钟K线
data = fetcher.fetch_min_kline("600519", freq="5min", count=-48)

# 分页获取更多数据
data = fetcher.fetch_min_kline("600519", freq="1min", pages=2)
```

---

### 1.5 统一K线接口 - `fetch_kline()`

推荐使用这个统一接口，支持前后向查询

```python
data = fetcher.fetch_kline(code, freq, starttime, count, market=None)
```

**参数**:
- `code` (str): 股票代码
- `freq` (str): 频率 ("1min", "5min", "15min", "30min", "60min")
- `starttime` (str): 起始时间 (格式: "YYYY-MM-DD HH:MM"，如 "2026-05-15 09:30")
- `count` (int): 获取数量，正数向后查询，负数向前查询
- `market` (int, 可选): 市场编号

**返回值**: 同 `fetch_min_kline()`

**示例**:
```python
# 向后获取 (从 starttime 往后取 count 条)
data = fetcher.fetch_kline("600519", freq="5min", 
                          starttime="2026-05-15 09:30", count=10)

# 向前获取 (从 starttime 往前取 count 条)
data = fetcher.fetch_kline("600519", freq="5min", 
                          starttime="2026-05-15 15:00", count=-10)
```

---

### 1.6 获取交易日历 - `fetch_trade_calendar()`

```python
dates = fetcher.fetch_trade_calendar(start_year=2000, end_year=2030, 
                                     index_code="000001", market=1)
```

**参数**:
- `start_year` (int): 起始年份
- `end_year` (int): 结束年份
- `index_code` (str): 指数代码 (默认 "000001")
- `market` (int): 市场编号 (默认 1)

**返回值**:
- 成功返回 `List[str]`，交易日日期列表 (格式: "YYYY-MM-DD")
- 失败返回 `None`

**示例**:
```python
dates = fetcher.fetch_trade_calendar(start_year=2026, end_year=2026)
```

---

### 1.7 获取股票基本信息 - `get_stock_info()`

```python
info = fetcher.get_stock_info(code, market=None)
```

**参数**:
- `code` (str): 股票代码
- `market` (int, 可选): 市场编号

**返回值**:
- 成功返回 `Dict`，包含:
  - `code`: 股票代码
  - `name`: 股票名称
  - `market_sn`: 市场编号
- 失败返回 `None`

**示例**:
```python
info = fetcher.get_stock_info("600519", market=1)
```

---

## 二、概念板块功能 API

### 2.1 获取所有概念板块 - `get_all_concept_plates()`

```python
plates = fetcher.get_all_concept_plates()
```

**返回值**:
- 成功返回 `List[Dict]`，每个板块包含:
  - `code`: 板块代码
  - `name`: 板块名称
  - `market`: 市场编号 (固定44)
  - `price` (可选): 最新价
  - `change` (可选): 涨跌额
  - `change_pct` (可选): 涨跌幅
- 失败返回 `None`

**示例**:
```python
plates = fetcher.get_all_concept_plates()
for plate in plates[:10]:
    print(plate["code"], plate["name"])
```

---

### 2.2 获取概念板块K线 - `get_concept_plate_kline()`

```python
kline_data = fetcher.get_concept_plate_kline(plate_code, count=-220, market=44)
```

**参数**:
- `plate_code` (str): 概念板块代码 (如 "994612")
- `count` (int): 获取数量
- `market` (int): 市场编号 (固定44)

**返回值**: 同 `fetch_day_kline()`

**示例**:
```python
kline_data = fetcher.get_concept_plate_kline("994612", count=-100)
```

---

### 2.3 获取概念板块成份股 - `get_concept_plate_stocks()`

```python
stocks = fetcher.get_concept_plate_stocks(plate_code, start=0, count=10)
```

**参数**:
- `plate_code` (str): 概念板块代码
- `start` (int): 分页起始位置
- `count` (int): 每页获取数量

**返回值**:
- 成功返回 `List[Dict]`，每只股票包含:
  - `code`: 股票代码
  - `name`: 股票名称
  - `market`: 市场编号
  - `price`, `change`, `change_pct`, `high`, `low` (可选): 行情数据
- 失败返回 `None`

**示例**:
```python
# 获取第一页
stocks = fetcher.get_concept_plate_stocks("994612", start=0, count=20)

# 获取第二页
stocks = fetcher.get_concept_plate_stocks("994612", start=20, count=20)
```

---

### 2.4 获取股票所属概念板块 - `get_stock_concept_plates()`

```python
plates = fetcher.get_stock_concept_plates(code, market)
```

**参数**:
- `code` (str): 股票代码
- `market` (int): 市场编号

**返回值**:
- 成功返回 `List[Dict]`，概念板块列表
- 失败返回 `None`

**示例**:
```python
plates = fetcher.get_stock_concept_plates("600519", market=1)
```

---

## 三、KLineToQlib 类 - 数据转换

### 3.1 初始化

```python
converter = KLineToQlib(qlib_data_dir=None)
```

**参数**:
- `qlib_data_dir` (str, 可选): qlib数据目录路径，默认使用环境变量 `QLIB_DATA_DIR`

---

### 3.2 股票代码转换 - `code_to_qlib_dir()`

静态方法，将股票代码转换为 qlib 目录名

```python
qlib_dir = KLineToQlib.code_to_qlib_dir(code)
```

**参数**:
- `code` (str): 股票代码

**返回值**:
- `str`: qlib目录名 (如 "sh600519", "sz000001", "bj830799")

**示例**:
```python
KLineToQlib.code_to_qlib_dir("600519")   # 返回 "sh600519"
KLineToQlib.code_to_qlib_dir("000001")   # 返回 "sz000001"
```

---

### 3.3 确保交易日历 - `ensure_calendar()`

从API获取交易日历并保存到本地

```python
success = converter.ensure_calendar(fetcher=None, start_year=2000, end_year=2030)
```

**参数**:
- `fetcher` (KLineFetcher, 可选): 已初始化的 fetcher 实例
- `start_year` (int): 起始年份
- `end_year` (int): 结束年份

**返回值**:
- `bool`: 是否成功

---

### 3.4 生成分钟级交易日历 - `generate_min_calendar()`

基于日日历生成分钟级时间戳

```python
success = converter.generate_min_calendar(freq="1min")
```

**参数**:
- `freq` (str): 频率 ("1min", "5min")

**返回值**:
- `bool`: 是否成功

---

### 3.5 日K线转换为qlib - `day_kline_to_qlib()`

```python
success = converter.day_kline_to_qlib(code, kline_data, mode="append", qlib_dir=None)
```

**参数**:
- `code` (str): 股票代码
- `kline_data` (List[Dict]): K线数据
- `mode` (str): "append" 追加或 "overwrite" 覆盖
- `qlib_dir` (str, 可选): qlib目录名，默认自动计算

**返回值**:
- `bool`: 是否成功

---

### 3.6 分钟K线转换为qlib - `min_kline_to_qlib()`

```python
success = converter.min_kline_to_qlib(code, kline_data, freq="1min", 
                                      mode="append", qlib_dir=None)
```

**参数**: 同 `day_kline_to_qlib()`，多一个 `freq` 参数

**返回值**:
- `bool`: 是否成功

---

### 3.7 检查本地数据覆盖 - `check_local_coverage()`

```python
start_idx, end_idx = converter.check_local_coverage(code, field="close", 
                                                    freq="day", qlib_dir=None)
```

**参数**:
- `code` (str): 股票代码
- `field` (str): 字段名 (默认 "close")
- `freq` (str): 频率 (默认 "day")
- `qlib_dir` (str, 可选): qlib目录名

**返回值**:
- `Tuple[int, int]`: (起始索引, 结束索引)，不存在返回 `(None, None)`

---

### 3.8 获取缺失数据范围 - `get_missing_range()`

```python
missing_range = converter.get_missing_range(code, start_date, end_date)
```

**参数**:
- `code` (str): 股票代码
- `start_date` (str): 开始日期
- `end_date` (str): 结束日期

**返回值**:
- `Tuple[str, str]` 或 `None`: (需要获取的起始日期, 结束日期)，已覆盖返回 `None`

---

## 四、批量下载工具 - download.py

### 4.1 命令行使用

```bash
# 下载日K线数据
kline-download --start 2026-01-01 --end 2026-05-15 --pool all

# 下载分钟K线数据
kline-download --start 2026-01-01 --end 2026-05-15 --pool all --freq 5min

# 强制全量下载 (默认是增量)
kline-download --start 2026-01-01 --end 2026-05-15 --pool all --full
```

**CLI 参数**:
- `--start`: 开始日期 (YYYY-MM-DD)，必填
- `--end`: 结束日期 (YYYY-MM-DD)，必填
- `--pool`: 股池名称 (all, csi300, csi500, csi800, csi1000, csiall)
- `--full`: 强制全量下载
- `--freq`: 频率 (day, 1min, 5min)
- `--qlib-data-dir`: qlib数据目录路径

---

### 4.2 Python API 使用

```python
from kline_fetcher.download import load_stock_pool, download_day_kline, download_min_kline

# 加载股池
stocks = load_stock_pool("csi300")

# 下载日K线
status = download_day_kline("2026-01-01", "2026-05-15", "all", incremental=True)

# 下载分钟K线
status = download_min_kline("2026-01-01", "2026-05-15", "all", freq="5min")
```

---

## 五、完整使用示例

### 示例1: 获取日K线并转换

```python
from kline_fetcher import KLineFetcher, KLineToQlib

# 初始化
fetcher = KLineFetcher()
converter = KLineToQlib()

# 确保日历存在
converter.ensure_calendar(fetcher)

# 获取数据
data = fetcher.fetch_day_kline("600519", count=100)

# 转换并保存
if data:
    converter.day_kline_to_qlib("600519", data, mode="append")
```

### 示例2: 获取分钟K线

```python
# 获取5分钟K线
data = fetcher.fetch_kline("600519", freq="5min", 
                          starttime="2026-05-15 09:30", count=100)

# 转换
if data:
    converter.generate_min_calendar("5min")
    converter.min_kline_to_qlib("600519", data, freq="5min")
```

### 示例3: 概念板块数据获取

```python
# 获取所有概念板块
plates = fetcher.get_all_concept_plates()

# 获取某个板块的K线
kline_data = fetcher.get_concept_plate_kline(plates[0]["code"])

# 获取板块成份股
stocks = fetcher.get_concept_plate_stocks(plates[0]["code"])
```

---

## 六、项目文件位置

| 文件 | 路径 |
|------|------|
| **KLineFetcher 类** | [kline_fetcher/fetcher.py](file:///workspace/kline_fetcher/fetcher.py) |
| **KLineToQlib 类** | [kline_fetcher/converter.py](file:///workspace/kline_fetcher/converter.py) |
| **批量下载工具** | [kline_fetcher/download.py](file:///workspace/kline_fetcher/download.py) |
| **配置文件** | [kline_fetcher/config/kline_config.yaml](file:///workspace/kline_fetcher/config/kline_config.yaml) |
| **完整测试** | [tests/test_all_features.py](file:///workspace/tests/test_all_features.py) |
| **测试报告** | [tests/TEST_REPORT.md](file:///workspace/tests/TEST_REPORT.md) |
| **原文档** | [README.md](file:///workspace/README.md) |

---

## 七、注意事项

1. **API 限流**: 内置请求间隔控制，避免请求过快
2. **数据量限制**: 单次API请求最多返回1500条，超过需分页或分段
3. **日期格式**: 
   - API接口: "YYYYMMDD" (如 "20260101")
   - fetch_kline: "YYYY-MM-DD HH:MM" (如 "2026-05-15 09:30")
   - 返回数据: "YYYY-MM-DD" (如 "2026-05-15")
4. **前复权**: 默认返回前复权数据，早期日期可能出现负价格 (正常现象)
5. **单位转换**:
   - 价格: API原始数据 / 1,000,000
   - 成交额: API原始数据 / 10,000
   - 成交量: 直接使用

---

## 八、测试状态

✅ **所有功能已测试通过**
- 35个测试，50个子测试，100%通过率
- 详细测试报告: [tests/TEST_REPORT.md](file:///workspace/tests/TEST_REPORT.md)

---

*文档生成时间: 2026-05-21*
