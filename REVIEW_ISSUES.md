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

### #3 `_build_min_arrays` 静默丢数据 ⬜
- **位置**：`kline_fetcher/converter.py:282`（converter.py 未拆分，行号未变）
- **现象**：
  ```python
  ts = f"{item['date']} {item.get('time', '00:00:00')}"
  ```
  分钟 K 线数据缺 `time` 字段时，回退成 `00:00:00`。该时间戳不在交易日历里（A 股 9:30 才开盘），会被当成无效索引**静默跳过**，数据丢失且无任何告警。
- **修复建议**：缺 `time` 时直接 `continue` 或抛错，不要用回退值；或在循环里打 warning 统计跳过条数。
- **工作量**：小（~5 行）

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

### #8 `get_stock_concept_plates` 依赖字段顺序 ⬜
- **位置**：`kline_fetcher/concept_plate.py:232-233`（从 fetcher.py:744 迁来）
- **现象**：
  ```python
  code_field = block_fields[0]   # 依赖字典字段顺序，API 顺序变化会把名称当代码
  ```
  仅靠 `block_fields[0]` 与其他字段的 `!=` 比较区分 code/name，没有对字段名做显式匹配（如 `BlockCode`/`BlockName`）。
- **修复建议**：明确期望字段名，或对候选字段做类型/正则校验。需先确认中焯实际字段名。
- **工作量**：中

### #9 日历生成时刻集合不一致 ⬜
- **位置**：`kline_fetcher/converter.py:115-166`（行号未变）
- **现象**：`_generate_1min_timestamps`(116) / `_generate_5min_timestamps`(130) / `_generate_generic_min_timestamps`(147) 三函数边界规则不同：
  - 1min：上午 `range(9,12)` + 过滤，不生成 15:00
  - 5min：手写固定时刻，上午到 11:25，下午 13:00-14:55
  - generic：上午 `while t < morning_end`（不含 11:30），下午 `while t <= afternoon_end`（含 15:00）
- **风险**：若与中焯实际返回的分钟时间戳对不上，会导致数据因索引 miss 被跳过。
- **修复建议**：拉一份中焯分钟 K 线实测，确认时间戳集合与日历生成函数一致。
- **工作量**：中（需实测）

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

### #15 测试覆盖不足 🟡
- **v2.1.0 现状**：`tests/` 有 3 个文件：
  - `test_append_bin.py`：`_append_bin` 全场景（6 测试，覆盖好）
  - `test_concept_plates.py`：概念板块集成测试（unittest 风格，默认跳过）
  - `test_split_interfaces.py`：**v2.1.0 新增**，三类 fetcher 端到端集成测试（27 项，默认跳过）
- **仍未覆盖**：
  - `fetch_day_kline_with_factor` 的 factor **数值正确性**（现有测试只断言 `factor > 1`，未验证 `factor ≈ hfq_close/none_close`）
  - `download_day_kline` / `download_min_kline` 的分段、增量、停牌跳过逻辑（**完全无单测**）
- **修复建议**：给 factor 计算补纯函数单测（无需 API，mock 两份输入即可）；download 逻辑补单测较难（依赖文件系统），可后置。
- **工作量**：小（factor）/ 中（download）

---

## ⚠️ 待核实（依赖中焯 API 能力）

### #1 `fetch_kline` 失效 ⚠️
- **位置**：`kline_fetcher/min_kline.py:108-159`（从 fetcher.py:378 迁来，方法体逐行一致，仅新增 docstring）
- **现象**：`count=-1500` 写死，`starttime` 仅用于在最近 1500 根里切片定位（min_kline.py:138-150），**没有传给 API 定位翻页**。对 1min（约 6 个交易日）超出 1500 根即返回 None。`test_split_interfaces.py:107` 的 `test_fetch_kline_callable` 把「可能返回 None」当作预期固化了。
- **待核实**：需确认中焯 API 是否支持按 `starttime` 定位翻页。若支持，方法可修复；若不支持，应标记 deprecated 或删除。
- **v2.1.0 改善**：docstring 已明确标注「分钟K专用」，至少不再误导用户当通用入口用。
- **工作量**：待定（取决于 API 能力）

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
| **P0** | #3 静默丢数据 | 小 | 确定数据正确性 bug |
| **P0** | #2 lstrip 误用（6 处）| 小 | 确定逻辑 bug，建议提取 helper |
| P1 | #6/#7 重叠覆盖 | 小 | 改为「非 NaN 才覆盖」即可 |
| P1 | #5 停牌重复下载 | 小 | |
| P1 | #15 factor 数值单测 | 小 | 无需 API |
| P2 | #8 字段顺序 | 中 | 需确认 API 字段名 |
| P2 | #9 日历时刻一致性 | 中 | 需实测 |
| P2 | #1 fetch_kline | 待定 | 需确认 API 能力 |
| P3 | #10 死代码清理 | 小 | 涉及多文件 |
| P3 | #11 `__all__`/docstring | 小 | |
| P3 | #12 egg-info 删除 | 小 | |
| P3 | #16 垫片导出子类 | 小 | 可选，已有文档 |
