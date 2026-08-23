# 批量下载

`download.py` 提供按股池批量下载的 CLI 与 Python API，自动增量更新（检查本地覆盖，仅补缺失部分）。

## CLI 使用

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

## Python API

```python
from kline_fetcher.download import load_stock_pool, download_day_kline, download_min_kline

# 加载股池
stocks = load_stock_pool("csi300")

# 批量下载日K（固定 hfq+factor 口径）
status = download_day_kline("2020-01-02", "2026-05-15", "all", incremental=True)

# 批量下载 5min 数据
status = download_min_kline("2026-01-02", "2026-05-15", "all", freq="5min")

# 指定 qlib 数据目录
status = download_day_kline("2020-01-02", "2026-05-15", "all", qlib_data_dir="/path/to/qlib_data")
```

返回 `{股票代码: 状态}` 字典，状态取值：

| 状态 | 含义 |
|------|------|
| `downloaded` | 本次下载并写入成功 |
| `up_to_date` | 本地已覆盖，跳过 |
| `download_failed` | 获取失败（原因见日志） |
| `write_failed` | 获取成功但写入 bin 失败 |
| `no_data_in_range` | 该股在日期范围内无数据 |

## 下载策略

- **日K**：日期范围 >1500 交易日自动分段（规避 API 单次上限），每段独立增量判断
- **分钟K**：翻页次数自动按日期范围计算；增量跳过带停牌容差（覆盖到 end 前一天即视为最新）
- 增量判断基于 `check_local_coverage`，详见[技术方案](../design.md#7-增量下载策略downloadpy)
