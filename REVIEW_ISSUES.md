# kline-fetcher Code Review 待办清单

> 评审时间：2026-06-14
> 评审版本：v2.0.2（commit 3e9dcad）
> 数据源前提：**中焯行情 API**（实测确认单位换算正确：价格÷1e6、成交额÷1e4、成交量已是「股」）
> 状态图例：⬜ 待处理 / 🟡 已确认 / ✅ 已修复 / ⚠️ 待核实

---

## 🔴 严重（确定 bug，与数据源无关）

### #3 `_build_min_arrays` 静默丢数据 ⬜
- **位置**：`kline_fetcher/converter.py:282`
- **现象**：
  ```python
  ts = f"{item['date']} {item.get('time', '00:00:00')}"
  ```
  分钟 K 线数据缺 `time` 字段时，回退成 `00:00:00`。该时间戳不在交易日历里（A 股 9:30 才开盘），会被当成无效索引**静默跳过**，数据丢失且无任何告警。
- **修复建议**：缺 `time` 时直接 `continue` 或抛错，不要用回退值；或在循环里打 warning 统计跳过条数。
- **工作量**：小（~5 行）

### #2 `infer_market` 的 `lstrip` 误用 ⬜
- **位置**：`kline_fetcher/fetcher.py:97`
- **现象**：
  ```python
  numeric = code.lstrip("SHshSZszBJbj")
  ```
  `str.lstrip` 删的是**字符集合中的任意字符**，不是前缀。正常代码（如 `SH600519`）能工作纯属巧合，对 `SHSZ000001` 这类边界输入会产生错误结果。`code_to_qlib_dir`（converter.py:177）有同样写法。
- **修复建议**：改用 `re.sub(r'^(sh|sz|bj)', '', code, flags=re.I)`，或显式判断前缀后切片。
- **工作量**：小（~3 行，但两处）

---

## 🟠 中等（健壮性 / 一致性）

### #5 `download_min_kline` 停牌股重复下载 ⬜
- **位置**：`kline_fetcher/download.py:216-224`
- **现象**：
  ```python
  if last_ts.startswith(end_ts_prefix):  # 停牌当天无数据，永远不匹配
      status[code] = "up_to_date"
  ```
  停牌股本地永远缺 `end` 当天数据，导致**每只停牌股每次运行都重复全量下载**。
- **修复建议**：结合日历位置判断「已覆盖到日历末尾」即可，而非依赖具体时间戳匹配 `end`。
- **工作量**：小

### #6/#7 分段下载的重叠覆盖风险 ⬜
- **位置**：`kline_fetcher/download.py:123-137`（分段循环）+ `converter.py:_append_bin:339-364`（重叠合并）
- **现象**：下载范围 > 1500 个交易日时分段下载。增量模式下，后续段的重叠区会进入 `_append_bin` 的「新数据覆盖旧数据重叠区」分支：
  ```python
  # converter.py _append_bin 重叠分支
  merged = existing_data[:offset].copy()
  merged = np.hstack([merged, new_data[:overlap_offset].astype("<f")])  # 新数据整段覆盖
  ```
  即新数据**整段覆盖**旧数据的重叠区间，逐元素覆盖（包括新数据里的 NaN）。
- **真正的危害**：若某段 API 返回**不完整数据**（被截断、缺日期、部分失败），新数据在该段缺失处会是 NaN，覆盖时会把**原本已有的有效数据覆盖成 NaN**。下游 qlib 无法区分这个 NaN 是「停牌」还是「数据丢失」——**静默数据丢失**。
- **触发条件**（三者同时满足）：
  1. 下载范围 > 1500 个交易日（触发分段，约 6 年以上）
  2. 某段 API 返回数据不完整（被截断或缺日期）
  3. 该股票该区间原本已有数据（增量模式）
- **实际风险**：**较低**。`fetch_day_kline_with_factor` 用 `begindate/enddate` 精确请求，中焯一般不截断；多数下载 < 6 年不分段；整段失败（`has_error=True`）时不写入，不触发覆盖。但一旦触发后果严重（静默丢数据）。
- **与停牌的区别**：停牌本身不会出错（新旧数据都缺那天 → 都是 NaN → 合并仍是 NaN，正确）。问题只在「旧有新无」时才发生。
- **修复建议**（任选其一）：
  1. **保守覆盖**：`_append_bin` 重叠区改为「新数据非 NaN 才覆盖旧数据」，NaN 不覆盖（保护已有数据）
  2. **覆盖前校验**：合并前检测新数据是否会在重叠区引入新 NaN 覆盖有效值，有则 warning
  3. **分段策略调整**：`day_kline_to_qlib` 层做整段合并，避免分段 append 各自处理重叠
- **推荐**：方案 1（改动最小，~3 行，且语义清晰——已有数据不应被空值覆盖）
- **工作量**：小（方案 1）/ 中（方案 2、3）

### #8 `get_stock_concept_plates` 依赖字段顺序 ⬜
- **位置**：`kline_fetcher/fetcher.py:744-766`
- **现象**：
  ```python
  code_field = block_fields[0]  # 依赖字典字段顺序，API 顺序变化会把名称当代码
  ```
- **修复建议**：明确期望的字段名（如 `BlockCode`/`BlockName`），或对候选字段做类型/正则校验。
- **工作量**：中（需确认中焯实际字段名）

### #9 日历生成时刻集合不一致 ⬜
- **位置**：`kline_fetcher/converter.py:116-166`
- **现象**：`_generate_1min_timestamps` / `_generate_5min_timestamps` / `_generate_generic_min_timestamps` 三个函数生成的时刻集合规则不同（如 1min 跳过 11:30 后、generic 用 `<` 判断边界）。若与中焯实际返回的分钟时间戳对不上，会导致大量数据因索引 miss 被跳过。
- **修复建议**：拉一份中焯分钟 K 线实测，确认时间戳集合与日历生成函数一致。
- **工作量**：中（需实测）

---

## 🟡 轻微（清理项）

### #10 `_convert_volume` 的 `stocks_per_h` 死代码 ⬜
- **位置**：`kline_fetcher/fetcher.py:191`
- **现象**：参数保留但从未使用（已在 2026-06-14 注释中记录原因：实测确认单位是「股」）。
- **修复建议**：删除整个透传链路（涉及 ~6 处调用点）。本次未动以控制改动面。
- **工作量**：小

### #11 缺 `__all__` / 模块 docstring ⬜
- **位置**：`kline_fetcher/__init__.py` + 三个模块顶部
- **修复建议**：补 `__all__ = ["KLineFetcher", "KLineToQlib", "AdjustType"]` 和模块 docstring。
- **工作量**：小

### #12 `UNKNOWN.egg-info/` 残留 ⬜
- **位置**：仓库根目录（gitignored，但占用磁盘）
- **修复建议**：`rm -rf UNKNOWN.egg-info/`
- **工作量**：小

### #13 `csiall` 股池文档未列 ⬜
- **位置**：`AGENTS.md` 股池列表 + `download.py:14 POOL_MAP`
- **现象**：代码 `POOL_MAP` 含 `csiall`，AGENTS.md 股池说明里没列。
- **修复建议**：AGENTS.md 股池列表补 `csiall`。
- **工作量**：小

### #15 测试覆盖不足 ⬜
- **位置**：`tests/`
- **现象**：只有 `test_append_bin.py`（覆盖好）和 `test_concept_plates.py`。`fetch_day_kline_with_factor` 的 factor 计算、`download_day_kline` 的分段/增量逻辑都没有测试。
- **修复建议**：至少给 factor 计算补单测（纯函数逻辑，容易测，无需 API）。
- **工作量**：小（factor）/ 中（download）

---

## ⚠️ 待核实（依赖中焯 API 能力）

### #1 `fetch_kline` 可能失效 ⚠️
- **位置**：`kline_fetcher/fetcher.py:378-412`
- **现象**：方法内部只用最近 1500 根做切片，`starttime` 仅用于切片而非真正定位。对 1min 频率（约 6 个交易日）超出范围即返回 None。`pages` 计算也从未传入下游。
- **待核实**：需确认中焯 API 是否支持按 `starttime` 定位翻页。若支持，方法可修复；若不支持，应标记 deprecated。
- **工作量**：待定（取决于 API 能力）

---

## ✅ 已处理项

### ✅ 文档数据源描述错误（2026-06-14 修复）
- AGENTS.md 第 5、25 行：「东方财富 API」→「中焯行情 API」

### ✅ 字段单位换算注释（2026-06-14 补充）
- `fetcher.py` 顶部常量区 + `_convert_price`/`_convert_volume`/`_convert_turnover` 三个方法 docstring
- 实测依据：贵州茅台 600519 对照东财/新浪公开基准，中焯值/新浪值 = 1.0000

### ✅ `_append_bin` start_idx 损坏（PR #2 已修复）
- 增量追加的合并逻辑，6 种场景测试覆盖完整
