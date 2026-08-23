# 使用示例

方法签名与参数明细见 [API 参考](../api-reference.md)。

## 场景1：获取单只股票日 K 并写入 qlib

```python
from tzt_api import KLineFetcher
from kline_qlib import KLineToQlib

fetcher = KLineFetcher()
converter = KLineToQlib()

data = fetcher.fetch_day_kline("600519", begindate="20240101", enddate="20260515")
if data:
    ok = converter.day_kline_to_qlib("600519", data, mode="append")
    print(f"写入{'成功' if ok else '失败'}")
```

## 场景2：获取高频数据并写入 qlib

```python
from tzt_api import MinKLineFetcher
from kline_qlib import KLineToQlib

fetcher = MinKLineFetcher()
converter = KLineToQlib()

# fetch_min_kline 返回数据自带 date/time 字段，客户端按需切片即可
data = fetcher.fetch_min_kline("600519", freq="5min", count=-500, market=1)
if data:
    ok = converter.min_kline_to_qlib("600519", data, freq="5min", mode="append")
    print(f"写入{'成功' if ok else '失败'}，共 {len(data)} 条")
```

## 场景3：增量更新检查

```python
from kline_qlib import KLineToQlib

converter = KLineToQlib()

start, end = converter.check_local_coverage("600519")
if start is not None:
    print(f"日K覆盖: {converter.dates[start]} ~ {converter.dates[end]}")

missing = converter.get_missing_range("600519", "2020-01-02", "2026-05-15")
if missing:
    print(f"需要下载: {missing[0]} ~ {missing[1]}")
```

## 场景4：批量下载

```python
from kline_qlib.download import download_day_kline, download_min_kline

status = download_day_kline("2020-01-02", "2026-05-15", "all", incremental=True)
downloaded = sum(1 for v in status.values() if v == "downloaded")
skipped = sum(1 for v in status.values() if v == "up_to_date")
print(f"下载={downloaded}, 跳过={skipped}")

status = download_min_kline("2026-01-02", "2026-05-15", "all", freq="5min")
```

更多细节见[批量下载](download.md)。

## 场景5：自定义数据目录

```python
from tzt_api import KLineFetcher
from kline_qlib import KLineToQlib

# 自定义配置文件
fetcher = KLineFetcher(config_path="/path/to/my_config.yaml")

# 自定义 qlib 数据目录
converter = KLineToQlib(qlib_data_dir="/path/to/qlib_data")
```

## 场景6：在 qlib 中读取数据

```python
import qlib
from qlib.data import D

qlib.init(provider_uri="/path/to/qlib_data", region="cn")

df = D.features(["SH600519"], ["$close"], start_time="2020-01-02", end_time="2026-05-15")
df = D.features(["SH600519"], ["$close"], start_time="2026-05-08", end_time="2026-05-15", freq="5min")
```
