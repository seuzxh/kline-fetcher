# 如何获取 A 股历史股票列表

## 快速开始

### 方法一：使用 akshare（推荐）

akshare 是**免费**的 Python 库，可以获取完整的 A 股历史股票列表：

```bash
# 安装 akshare
pip install akshare pandas

# 运行脚本
python scripts/get_stock_list.py
```

**输出文件：**
- `stock_lists/all_stocks.csv` - 完整股票列表（CSV 格式）
- `stock_lists/all_stocks.txt` - qlib instruments 格式
- `stock_lists/stock_list_info.txt` - 统计信息

### 方法二：下载 qlib 官方数据

qlib 官方提供了预处理的完整数据：

```bash
# 下载 qlib 官方数据
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 这会自动下载 instruments 文件
```

---

## akshare 股票列表获取功能

### 核心接口

```python
import akshare as ak

# 1. 获取所有 A 股代码和名称
stock_info = ak.stock_info_a_code_name()
# 返回: code, name

# 2. 获取当前交易的 A 股实时行情
spot_data = ak.stock_zh_a_spot_em()
# 返回: 代码, 名称, 最新价, 涨跌幅, 成交量...

# 3. 获取退市股票列表
delisted = ak.stock_zh_a_stop_em()
# 返回: 退市日期, 代码, 名称, 退市原因...

# 4. 获取新股列表
new_stocks = ak.stock_zh_a_new_em()
# 返回: 代码, 名称, 上市日期...

# 5. 获取 ST 股票
st_stocks = ak.stock_zh_a_st_em()
```

### 完整示例

```python
import akshare as ak
import pandas as pd

def get_complete_stock_list():
    """获取完整的 A 股历史股票列表"""
    
    # 1. 当前所有 A 股
    current = ak.stock_info_a_code_name()
    current['status'] = 'active'
    current['delist_date'] = None
    
    # 2. 退市股票
    try:
        delisted = ak.stock_zh_a_stop_em()
        delisted['status'] = 'delisted'
        delisted['delist_date'] = delisted['退市日期']
    except:
        delisted = pd.DataFrame()
    
    # 3. 合并
    all_stocks = pd.concat([current, delisted], ignore_index=True)
    
    # 4. 添加市场信息
    def get_market(code):
        if str(code).startswith(('60', '68')):
            return 'SH'  # 上海
        elif str(code).startswith(('00', '30')):
            return 'SZ'  # 深圳
        elif str(code).startswith(('8', '4')):
            return 'BJ'  # 北交所
        return 'UNKNOWN'
    
    all_stocks['market'] = all_stocks['code'].apply(get_market)
    
    return all_stocks

# 使用
df = get_complete_stock_list()
print(f"共 {len(df)} 只股票")
print(f"当前交易: {len(df[df['status'] == 'active'])}")
print(f"已退市: {len(df[df['status'] == 'delisted'])}")
```

---

## 数据来源对比

| 数据源 | 价格 | 完整性 | 退市股票 | 上市日期 | 推荐度 |
|--------|------|--------|---------|---------|--------|
| **akshare** | 免费 | ⭐⭐⭐⭐⭐ | ✅ 支持 | ✅ 支持 | ⭐⭐⭐⭐⭐ |
| tushare | 免费/付费 | ⭐⭐⭐⭐ | ✅ 支持 | ✅ 支持 | ⭐⭐⭐⭐ |
| qlib 官方 | 免费 | ⭐⭐⭐⭐⭐ | ✅ 包含 | ✅ 包含 | ⭐⭐⭐⭐⭐ |
| 通联数据 | 付费 | ⭐⭐⭐⭐⭐ | ✅ 支持 | ✅ 支持 | ⭐⭐⭐ |
| 交易所官网 | 免费 | ⭐⭐⭐ | ❌ 不全 | ✅ 支持 | ⭐⭐ |

---

## qlib instruments 文件格式

### 格式说明

qlib 的 instruments 文件非常简单：

```
SH600000    2010-01-01    2026-05-21
SZ000001    2010-01-01    2026-05-21
SH600519    2015-06-01    2026-05-21
SZ300001    2010-10-30    2022-03-15    # 退市股票
```

**格式：** `股票代码\t上市日期\t退市日期（或留空）`

- 股票代码：qlib 格式（如 SH600000）
- 上市日期：该股票第一笔交易的日期
- 退市日期：退市日期，如果还在交易则留空

### 为什么 instruments 文件很重要？

1. **qlib 使用动态股票池** - 根据日期自动过滤股票
2. **不需要获取历史每天的股票列表** - 数据本身告诉我们
3. **自动处理新上市和退市** - qlib 会根据日期范围自动筛选

---

## 完整工作流程

### 步骤 1: 获取股票列表

```bash
# 使用 akshare
python scripts/get_stock_list.py

# 或手动
python -c "import akshare as ak; print(ak.stock_info_a_code_name())"
```

### 步骤 2: 下载数据

```bash
# 假设股票列表保存在 stock_lists/all_stocks.csv
# 下载数据（使用 --pool 参数指定列表文件）

python -m kline_fetcher.download \
    --start 2020-01-01 \
    --end 2024-12-31 \
    --pool all \
    --generate-instruments all
```

### 步骤 3: 生成 instruments

```python
from kline_fetcher.converter import KLineToQlib

converter = KLineToQlib()

# 从下载的数据中提取股票列表
stocks = converter.get_instruments_from_features()

# 生成 instruments 文件
converter.generate_instruments_file(stocks, "all")
```

---

## 常见问题

### Q: akshare 获取的数据准确吗？

**A:** akshare 数据来源于东方财富、新浪财经等权威平台，数据质量较高。但建议：
- 定期更新股票列表（每月一次）
- 对于关键研究，交叉验证重要数据

### Q: 如何获取特定时间段的股票列表？

**A:** instruments 文件天然支持动态查询：

```python
import qlib
from qlib.data import D

qlib.init(provider_uri="your_data_dir")

# 获取 2020年1月 在交易的股票
instruments_2020 = D.list_instruments(
    D.instruments("all"),
    start_time="2020-01-01",
    end_time="2020-01-31"
)
```

### Q: 退市股票的数据怎么处理？

**A:** 
1. 下载时包含退市股票（不会影响计算）
2. instruments 文件会记录退市日期
3. qlib 会自动根据时间范围过滤

### Q: 股票列表多久更新一次？

**A:** 建议：
- 日常使用：每月更新一次
- 重要研究：每周更新一次
- 实时策略：每日更新

---

## 数据文件保存位置建议

```
your_project/
├── stock_lists/              # 股票列表
│   ├── all_stocks.csv       # 完整列表
│   ├── all_stocks.txt       # qlib 格式
│   └── stock_list_info.txt  # 统计信息
│
├── qlib_data/               # qlib 数据
│   ├── calendars/          # 交易日历
│   ├── features/           # 股票数据
│   └── instruments/        # 股票池定义
│
└── scripts/                 # 工具脚本
    └── get_stock_list.py   # 获取股票列表
```

---

## 总结

| 步骤 | 操作 | 工具/方法 |
|------|------|----------|
| 1 | 获取股票列表 | akshare（免费完整） |
| 2 | 下载历史数据 | kline_fetcher |
| 3 | 生成 instruments | 自动从数据提取 |
| 4 | 使用 qlib | 动态股票池自动处理 |

**关键点：** 不需要手动获取历史每天的股票列表，qlib 的 instruments 机制会自动处理！
