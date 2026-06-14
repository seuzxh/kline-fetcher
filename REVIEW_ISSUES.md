# kline-fetcher Code Review 待办清单

> 初次评审：2026-06-14（v2.0.2, commit 3e9dcad）
> 最近复核：2026-06-14（v2.1.0, commit 0a6c890，拆分后）
> 数据源前提：**中焯行情 API**（实测确认单位换算正确：价格÷1e6、成交额÷1e4、成交量已是「股」）
> 状态图例：⬜ 待处理 / 🟡 部分修复 / ✅ 已修复 / ⚠️ 待核实

> **v2.1.0 拆分影响**：原 `fetcher.py` 拆为 `_base.py` / `min_kline.py` / `concept_plate.py`。
> 下方所有行号已更新为 v2.1.0 位置。功能性 bug 全部为 v2.0.2 原有问题逐行搬迁，
> 拆分未修复也未恶化（仅 #11/#13/#15 因文档/测试工作有部分改善）。

---

## 🔴 严重（确定 bug，与数据源无关）

### #3 `_build_min_arrays` 静默丢数据 ✅
- **状态**：**已修复**（2026-06-14）。
- **修复内容**：`kline_fetcher/converter.py:280-296` 不再用 `'00:00:00'` 回退；缺 `time` 字段（含空字符串）的条目显式跳过，并打 warning 报告跳过比例（如 `3/100 条分钟K线数据缺少 time 字段，已跳过`）。
- **测试**：`tests/test_build_min_arrays.py` 3 个单测覆盖（缺 time 跳过+warning、全有 time 无 warning、空字符串 time 视为缺失）。
- **保留此条仅作历史记录，无需处理。**

### #2 `infer_market` / `code_to_qlib_dir` 的 `lstrip` 误用 ⬜
- **位置（v2.1.0 实际为 6 处，原 review 低估为 2 处）**：
  - `kline_fetcher/_base.py:118`（`infer_market` 内）
  - `kline_fetcher/_base.py:183`（`_build_params` 内）
  - `kline_fetcher/converter.py:172, 174, 176`（`code_to_qlib_dir` 前缀分支，分别 `lstrip('SHsh')`/`'SZsz'`/`'BJbj')`）
  - `kline_fetcher/converter.py:177`（`code_to_qlib_dir` 兜底分支）
- **现象**：`str.lstrip("SHshSZszBJbj")` 删的是**字符集合中的任意字符**，不是前缀。正常代码（如 `SH600519`）能工作纯属巧合，对 `SHSZ000001` 这类边界输入会产生错误结果。
- **修复建议**：改用 `re.sub(r'^(sh|sz|bj)', '', code, flags=re.I)`，或显式判断前缀后切片。**6 处需一并修**，否则同一坏写法在不同入口表现不一致。
- **工作量**：小（~3 行/处 × 6 处，建议提取为一个 `_strip_market_prefix` helper）

---

## 🟠 中等（健壮性 / 一致性）

### #5 `download_min_kline` 停牌股重复下载 ⬜
- **位置**：`kline_fetcher/download.py:219-224`（行号较 v2.0.2 的 216-224 下移 3 行，逻辑未变）
- **现象**：
  ```python
  if last_ts.startswith(end_ts_prefix):  # 停牌当天无数据，永远不匹配
      status[code] = "up_to_date"
  ```
  停牌股本地永远缺 `end` 当天数据，导致**每只停牌股每次运行都重复全量下载**。
  注：`download_min_kline` 现用 `MinKLineFetcher()`（download.py:168），但这段跳过逻辑是纯本地日历比较，与 fetcher 类型无关。
- **修复建议**：结合日历位置判断「已覆盖到日历末尾」即可，而非依赖具体时间戳匹配 `end`。
- **工作量**：小

### #6/#7 分段下载的重叠覆盖风险 ⬜
- **位置**：`kline_fetcher/download.py:93-137`（分段循环）+ `converter.py:339-364`（`_append_bin` 重叠合并，行号未变）
- **现象**：下载范围 > 1500 个交易日时分段下载。增量模式下，后续段的重叠区进入 `_append_bin` 的「新数据整段覆盖旧数据」分支（converter.py:357 `np.hstack([merged, new_data[:overlap_offset].astype("<f")])`）。若某段 API 返回不完整数据，新数据的 NaN 会覆盖旧的有效值，下游 qlib 无法区分这个 NaN 是「停牌」还是「数据丢失」。
- **补充**：`tests/test_append_bin.py` 的 `test_append_overlap` 刻意断言「新数据覆盖旧数据」（`[1,2,30,40,50]` 覆盖 `[3,4]`），说明该行为是有意设计——问题在于「新数据里的 NaN 不应覆盖旧有效值」这一更细的保护缺失。
- **触发条件**：① 范围 > 1500 个交易日；② 某段 API 返回不完整；③ 该区间原本已有数据。三者同时满足才触发。
- **实际风险**：较低。`fetch_day_kline_with_factor` 用 `begindate/enddate` 精确请求，中焯一般不截断；多数下载 < 6 年不分段。
- **修复建议**：`_append_bin` 重叠区改为「新数据非 NaN 才覆盖」，NaN 不覆盖（~3 行，语义清晰）。
- **工作量**：小

### #8 `get_stock_concept_plates` 依赖字段顺序 ✅（无需修复）
- **位置**：`kline_fetcher/concept_plate.py:232-233`
- **状态**：**用户确认无需修复**。字段顺序与中焯 API 请求的字段次序一致，实际运行不会出现顺序错乱。
- **保留此条仅作历史记录，无需处理。**

### #9 日历生成时刻集合不一致 ✅（已修复）
- **状态**：**已修复**（2026-06-14）。实测中焯 API 时间语义 + 修正日历生成函数边界。
- **实测发现**：中焯用「K线周期结束时刻」标记每根K线，因此：
  - 含 11:30（上午收盘）、15:00（全天收盘）—— 原日历生成函数缺失这两点，导致数据丢失
  - 不含 09:30（开盘）、13:00（下午开盘）—— 开盘瞬间归到下一根
- **修复内容**（converter.py:118-159）：
  - `_generate_1min_timestamps`：上午含到 11:30（原 11:29），下午含到 15:00（原 14:59）
  - `_generate_5min_timestamps`：上午含到 11:30（原 11:25），下午加 15:00（原到 14:55）
  - `_generate_generic_min_timestamps`：本就含 15:00（`<=`），未改
- **修复效果**：覆盖率从 99.2%（1min）/95.8%（5min）提升到 **100%**，API 数据全部能写入，不再丢失上午收盘和全天收盘数据。
- **副作用**：日历每天多 2 个时刻（09:30、13:00 开盘瞬间），中焯不返回这些时刻的数据，该位置留 NaN，无害。
- **保留此条仅作历史记录，无需处理。**

---

## 🟡 轻微（清理项）

### #10 `_convert_volume` 的 `stocks_per_h` 死代码 ⬜
- **位置**：`kline_fetcher/_base.py:213-220`
- **现象**：参数保留但函数体 `return float(raw)` 完全不引用它（注释明说「当前不参与换算」）。
- **v2.1.0 变化**：拆分时新增了 `_extract_stocks_per_h` helper（_base.py:264-270），被 `_base.py:302`、`min_kline.py:54,80`、`concept_plate.py:133` 调用。该 helper 提取 `StocksPerH` 后透传给 `_parse_kline_items` → `_convert_volume`，**但提取出的值最终在 `_convert_volume` 里被丢弃**。死代码非但未消除，反而多了一个 helper 把无用值贯穿整条调用链（涉及 ~6 处透传）。
- **修复建议**：要么删除整个透传链路（`_extract_stocks_per_h` + `stocks_per_h` 参数 + 所有透传点），要么让 `_convert_volume` 真正使用它（若 API 返回的是「手」需要 ×100）。实测确认单位是「股」，倾向删除。
- **工作量**：小（但涉及多文件）

### #11 缺 `__all__` / 模块 docstring 🟡
- **v2.1.0 现状**：
  | 文件 | 模块 docstring | `__all__` |
  |------|---------------|-----------|
  | `_base.py` | ✅ 有 | ❌ 无 |
  | `min_kline.py` | ✅ 有 | ❌ 无 |
  | `concept_plate.py` | ✅ 有 | ❌ 无 |
  | `fetcher.py`（垫片）| ✅ 有 | ✅ 有（仅基类符号）|
  | `__init__.py` | ❌ 无 | ✅ 有 |
  | `converter.py` | ❌ 无 | ❌ 无 |
  | `download.py` | ❌ 无 | ❌ 无 |
- **修复建议**：三个拆分模块补 `__all__`；`__init__.py` 补模块 docstring。`converter.py`/`download.py` 可选。
- **工作量**：小

### #12 `UNKNOWN.egg-info/` 残留 ⬜
- **位置**：仓库根目录 `UNKNOWN.egg-info/`（4 文件，gitignored，但仍占磁盘）
- **修复建议**：`rm -rf UNKNOWN.egg-info/`
- **工作量**：小

### #13 `csiall` 股池文档未列 ✅
- **状态**：**已修复**。AGENTS.md:178 股池列表、AGENTS.md:261 CLI help 均已含 `csiall`。
- **保留此条仅作历史记录，无需处理。**

### #15 测试覆盖不足 🟡（部分改善）
- **v2.1.0 现状**：`tests/` 有 7 个文件，49 个单元测试（默认运行）+ 42 个集成测试（需 API）：
  - `test_append_bin.py`：`_append_bin` 全场景（9 测试，含 #6/#7 NaN 保护）
  - `test_build_min_arrays.py`：`_build_min_arrays` 缺 time 字段处理（3 测试，#3）
  - `test_factor_calc.py`：factor 数值正确性（6 测试，mock 输入无需 API）
  - `test_calendar_generation.py`：日历边界 11:30/15:00（13 测试，#9）
  - `test_structure.py`：包结构/导入/方法归属/静态方法（18 测试，无需 API）
  - `test_concept_plates.py`：概念板块集成测试（8 测试 + 15 subtests，默认跳过）
  - `test_split_interfaces.py`：三类 fetcher 端到端集成测试（34 测试，覆盖各复权方式、5 种频率、错误输入等，默认跳过）
- **已覆盖**（本次新增）：
  - ✅ factor 数值正确性（factor = hfq_close/none_close、volume 调整、NaN 边界）
  - ✅ 日历生成边界（含 11:30/15:00、条数、连续性）
- **仍未覆盖**：
  - `download_day_kline` / `download_min_kline` 的分段、增量、停牌跳过逻辑（依赖文件系统，可后置）
- **工作量**：小（已完成部分）/ 中（download 测试，后置）

---

## ⚠️ 待核实（依赖中焯 API 能力）

### #1 `fetch_kline` 失效 ✅（已删除方法）
- **状态**：**已删除**（2026-06-14）。中焯返回数据自带 `date`/`time` 字段，客户端可自行按时间切片，无需专门的时间定位方法。
- **实测结论**（2026-06-14，5min 茅台 600519）：方法存在隐蔽 bug——`count >= 0`（向后取）+ 过早 starttime 时不返回 None，而是误定位到数据开头返回最近数据（用户会误以为拿到了目标时间段）；`count < 0` + 过早 starttime 返回 None。
- **处理**：直接删除 `fetch_kline` 方法（min_kline.py），同步清理 README/AGENTS.md 引用和 test_fetch_kline_callable 测试。引导用户用 `fetch_min_kline` + 客户端时间过滤。
- **保留此条仅作历史记录，无需处理。**

---

## 🆕 拆分相关（v2.1.0 新增）

### #16 `fetcher.py` 垫片未导出子类 ⬜
- **位置**：`kline_fetcher/fetcher.py:14-36`
- **现象**：垫片 `__all__` 只导出基类层符号（`KLineFetcher` + 常量），**未导出 `MinKLineFetcher` / `ConceptPlateFetcher`**。旧代码 `from kline_fetcher.fetcher import KLineFetcher; KLineFetcher().fetch_min_kline(...)` 会 `AttributeError`（基类已无分钟K方法）。
- **定性**：这是「已知且有文档的破坏」（AGENTS.md / README.md 均已标注），属于拆分的有意设计。但严格说垫片没做到「旧导入路径完全兼容」——只兼容了基类符号。
- **修复建议**：可选项——若想提升兼容性，可在垫片里 `from kline_fetcher.min_kline import MinKLineFetcher` 并加入 `__all__`，让旧路径也能拿到子类。或保持现状（强制用户迁移到新导入路径）。
- **工作量**：小
- **优先级**：低（已有文档说明，非阻塞）

---

## ✅ 已处理项（完整列表）

- **数据源描述错误**（2026-06-14 修复）：AGENTS.md「东方财富 API」→「中焯行情 API」
- **字段单位换算注释**（2026-06-14 补充）：`_base.py` 常量区 + `_convert_*` 方法 docstring（实测依据：贵州茅台 600519 对照东财/新浪公开基准）
- **`_append_bin` start_idx 损坏**（PR #2 已修复）：增量追加合并逻辑，6 种场景测试覆盖完整
- **#13 `csiall` 股池文档**（v2.1.0 已修复）：AGENTS.md 股池列表 + CLI help 均已含

---

## 修复优先级总览（v2.1.0 复核后）

| 优先级 | Bug | 工作量 | 备注 |
|---|---|---|---|
| **P0** | #2 lstrip 误用（6 处）| 小 | 确定逻辑 bug，建议提取 helper（用户评估：当前输入不会触发，暂不修）|
| ✅ 已修复 | #1 fetch_kline | — | 2026-06-14 删除（返回数据自带时间）|
| ✅ 已修复 | #9 日历时刻一致性 | — | 2026-06-14 修复，覆盖率 100% |
| ✅ 已修复 | #16 垫片导出子类 | — | 2026-06-14 补导出 |
| ✅ 已修复 | #3 静默丢数据 | — | 2026-06-14 修复 |
| ✅ 已修复 | #5 停牌重复下载 | — | 2026-06-14 修复 |
| ✅ 已修复 | #6/#7 重叠覆盖 | — | 2026-06-14 修复（非 NaN 才覆盖）|
| ✅ 已修复 | #10 死代码清理 | — | 2026-06-14 删除 stocks_per_h 链路 |
| ✅ 已修复 | #11 `__all__`/docstring | — | 2026-06-14 补全 |
| ✅ 已修复 | #12 egg-info 删除 | — | 2026-06-14 删除 |
| ✅ 部分修复 | #15 测试覆盖 | — | factor + 日历边界单测已补；download 测试后置 |
| ✅ 无需修复 | #8 字段顺序 | — | 用户确认：字段次序与 API 请求一致 |
| ✅ 已修复 | #13 csiall 文档 | — | v2.1.0 修复 |
