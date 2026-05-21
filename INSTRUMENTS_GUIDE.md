# qlib 股票列表（instruments）生成指南

## 问题解答

### Q: 如果今天有 5000 只股票，要下载数据到 2020 年，但有些股票是 2015 年才上市或者已经退市了，这种难道我要获取历史每天的市场股票吗？

**A: 不需要！** 这正是 qlib 设计的巧妙之处。

## 解决方案

### qlib 的工作原理

qlib 不需要您知道历史上每天的股票列表，只需要：

1. **下载所有股票的数据**（包括已退市和新上市的）
2. **自动记录每只股票的实际数据范围**（起始日期和结束日期）
3. **qlib 在使用时会自动过滤无效数据**

### 我们的工具实现

我们已经为您实现了完整的解决方案：

#### 1. 下载数据时自动生成 instruments 文件

```bash
# 下载日K数据，并自动生成 instruments 文件
python -m kline_fetcher.download \
    --start 2020-01-01 \
    --end 2024-12-31 \
    --pool all \
    --generate-instruments all
```

#### 2. 单独生成 instruments 文件

如果您已经下载了数据，可以单独生成：

```python
from kline_fetcher.converter import KLineToQlib

converter = KLineToQlib()

# 从已下载的数据中扫描股票列表
stock_list = converter.get_instruments_from_features()

# 生成 instruments 文件
file_path = converter.generate_instruments_file(stock_list, "all")
```

或者使用演示脚本：

```bash
python demo_generate_instruments.py
```

### instruments 文件格式

qlib 的 instruments 文件格式非常简单：

```
SH600000    2020-01-01    2024-12-31
SH600519    2015-06-01    2024-12-31  # 2015年上市的股票
SZ300001    2010-10-30    2022-03-15  # 2022年退市的股票
```

**格式：** `股票代码\t起始日期\t结束日期`

### 工作流程完整示例

#### 步骤 1: 准备股票列表

创建一个包含所有你想下载的股票的列表（例如从交易所官网或其他数据源获取）：

```
# my_stock_list.txt
600000    1    SH600000
600519    1    SH600519
000001    0    SZ000001
# ... 更多股票
```

#### 步骤 2: 下载数据

```bash
# 先把列表放到 qlib_data/instruments/ 目录下
# 然后下载
python -m kline_fetcher.download \
    --start 2020-01-01 \
    --end 2024-12-31 \
    --pool my_stock_list \
    --generate-instruments all
```

#### 步骤 3: 使用 qlib

在 qlib 中使用时，它会自动处理：

```python
import qlib
from qlib.data import D

qlib.init(provider_uri="your_qlib_data_dir")

# 动态股票池 - qlib 会根据 instruments 文件自动过滤
instruments = D.instruments("all")

# 获取数据时，只有在日期范围内有数据的股票才会被包含
data = D.features(
    instruments,
    ["$close", "$factor"],
    start_time="2020-01-01",
    end_time="2024-12-31"
)
```

## 新功能总览（v1.3.0）

### 1. `KLineToQlib` 新增方法

- `get_instruments_from_features()` - 从已下载的数据扫描股票列表
- `generate_instruments_file()` - 生成 qlib 格式的 instruments 文件

### 2. download.py 新增参数

- `--generate-instruments` - 下载完成后自动生成 instruments 文件

### 3. 新增示例文件

- `example_stock_list.txt` - 示例股票列表
- `demo_generate_instruments.py` - 演示脚本
- `INSTRUMENTS_GUIDE.md` - 本文档

## 总结

| 问题 | 答案 |
|------|------|
| 需要获取历史每天的市场股票吗？ | **不需要** |
| 需要知道股票的上市和退市日期吗？ | **不需要**，数据会告诉我们 |
| 需要分别处理新上市和退市股票吗？ | **不需要**，统一处理 |
| 怎么做？ | 1. 下载所有股票数据<br>2. 自动生成 instruments<br>3. qlib 自动处理剩下的事 |

## 版本历史

- v1.3.0 - 新增 instruments 文件自动生成功能
