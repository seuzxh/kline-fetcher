# kline-fetcher 优化计划：支持 qlib Factor 计算

## 一、背景分析

### 1.1 qlib Factor 计算机制

根据 qlib 官方文档，qlib 的因子计算具有以下特点：

#### 1.1.1 表达式引擎
- **声明式因子定义**: 通过表达式字符串定义因子，如 `MA($close, 20) - MA($close, 5)`
- **丰富的运算符**: 支持 MA, EMA, Ref, Mean, Std, Corr, Rank 等
- **嵌套表达式**: 支持复杂因子的组合计算
- **自动缓存**: 避免重复计算，提升性能

#### 1.1.2 数据格式要求
- **二进制格式**: 数据存储为 `.bin` 文件，列式存储
- **字段分离**: 每个字段一个文件 (close.day.bin, open.day.bin 等)
- **日历对齐**: 数据按交易日历对齐，非交易日填充 NaN
- **多频率支持**: day, 1min, 5min, 15min, 30min, 60min

#### 1.1.3 因子计算流程
```
原始数据 (OHLCV) 
  ↓
表达式引擎计算 (MA, EMA, Ref...)
  ↓
因子值 (factor values)
  ↓
因子评估 (IC, Rank IC)
```

### 1.2 当前 kline-fetcher 现状

#### 1.2.1 已实现功能
✅ K线数据获取 (日K、分钟K)
✅ 数据转换为 qlib 格式
✅ 交易日历管理
✅ 基础字段支持 (OHLCV, vwap)
✅ 增量更新机制

#### 1.2.2 存在的不足
❌ 缺少复权因子 ($factor) 字段
❌ 缺少换手率、涨跌幅等衍生字段
❌ 未支持因子计算辅助工具
❌ 缺少因子评估接口
❌ 未提供批量因子计算功能

---

## 二、优化目标

### 2.1 核心目标
1. **完善基础数据字段**，支持 qlib 标准因子计算
2. **提供因子计算工具**，简化因子开发流程
3. **支持因子评估**，验证因子有效性
4. **优化性能**，提升大规模因子计算效率

### 2.2 具体目标
- 支持复权因子 ($factor) 存储
- 支持换手率、涨跌幅等衍生字段
- 提供常用技术指标因子
- 提供因子 IC 评估接口
- 支持批量因子计算

---

## 三、优化方案

### 3.1 数据层优化

#### 3.1.1 扩展基础字段

**当前字段**:
```python
QLIB_DAY_FIELDS = ["open", "high", "low", "close", "volume", "amount", "vwap"]
```

**优化后字段**:
```python
QLIB_DAY_FIELDS = [
    # 价格字段
    "open", "high", "low", "close", "vwap",
    # 成交量字段
    "volume", "amount",
    # 复权因子 (重要!)
    "factor",
    # 衍生字段
    "turnover_rate",      # 换手率
    "change",             # 涨跌额
    "change_pct",         # 涨跌幅
    # 扩展字段
    "adj_open",           # 后复权开盘价
    "adj_high",           # 后复权最高价
    "adj_low",            # 后复权最低价
    "adj_close",          # 后复权收盘价
]
```

**实现方式**:
```python
# 在 fetcher.py 中添加
def _parse_kline_items(self, data_list: list, klinetype: str, stocks_per_h: int = 100) -> List[Dict]:
    result = []
    for item in data_list:
        # ... 现有代码 ...
        
        row = {
            # 基础字段
            "date": dt["date"],
            "open": self._convert_price(item.get("OpenPrice", 0)),
            "high": self._convert_price(item.get("HighPrice", 0)),
            "low": self._convert_price(item.get("LowPrice", 0)),
            "close": self._convert_price(item.get("ClosePrice", 0)),
            "volume": self._convert_volume(item.get("PeriodVolume", 0), stocks_per_h),
            "amount": self._convert_turnover(item.get("PeriodTurnover", 0)),
            
            # 新增字段
            "factor": self._calculate_factor(item),  # 复权因子
            "turnover_rate": self._calculate_turnover_rate(item),  # 换手率
            "change": self._calculate_change(item),  # 涨跌额
            "change_pct": self._calculate_change_pct(item),  # 涨跌幅
        }
        
        result.append(row)
    return result
```

#### 3.1.2 复权因子计算

**复权因子说明**:
- qlib 使用前复权数据，复权因子用于还原真实价格
- 公式: `原始价格 = 前复权价格 / factor`
- factor 会随分红、拆股等事件调整

**实现方案**:
```python
# 在 fetcher.py 中添加
class KLineFetcher:
    def _calculate_factor(self, item: dict, prev_factor: float = 1.0) -> float:
        """
        计算复权因子
        基于前复权价格和原始价格的比值
        """
        # 从 API 获取复权信息
        # 如果有分红/拆股事件，调整 factor
        # 否则保持不变
        return prev_factor
```

#### 3.1.3 换手率计算

```python
def _calculate_turnover_rate(self, item: dict, total_shares: float) -> float:
    """
    计算换手率
    换手率 = 成交量 / 流通股本
    """
    volume = item.get("PeriodVolume", 0)
    if total_shares > 0:
        return volume / total_shares
    return 0.0
```

---

### 3.2 因子计算工具层

#### 3.2.1 新增因子计算模块

创建新文件 `kline_fetcher/factors.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
因子计算工具模块
提供常用技术指标因子的计算函数
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union


class FactorCalculator:
    """因子计算器"""
    
    @staticmethod
    def MA(data: pd.Series, window: int) -> pd.Series:
        """移动平均"""
        return data.rolling(window=window).mean()
    
    @staticmethod
    def EMA(data: pd.Series, window: int) -> pd.Series:
        """指数移动平均"""
        return data.ewm(span=window, adjust=False).mean()
    
    @staticmethod
    def STD(data: pd.Series, window: int) -> pd.Series:
        """滚动标准差"""
        return data.rolling(window=window).std()
    
    @staticmethod
    def MACD(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """
        MACD 指标
        返回: {'dif': DIF, 'dea': DEA, 'macd': MACD}
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        return {'dif': dif, 'dea': dea, 'macd': macd}
    
    @staticmethod
    def RSI(close: pd.Series, window: int = 14) -> pd.Series:
        """相对强弱指标"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def BOLL(close: pd.Series, window: int = 20, num_std: int = 2) -> Dict[str, pd.Series]:
        """
        布林带
        返回: {'upper': 上轨, 'middle': 中轨, 'lower': 下轨}
        """
        middle = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    @staticmethod
    def KDJ(high: pd.Series, low: pd.Series, close: pd.Series, 
            n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, pd.Series]:
        """
        KDJ 指标
        返回: {'k': K值, 'd': D值, 'j': J值}
        """
        low_min = low.rolling(window=n).min()
        high_max = high.rolling(window=n).max()
        rsv = (close - low_min) / (high_max - low_min) * 100
        
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return {'k': k, 'd': d, 'j': j}
    
    @staticmethod
    def ATR(high: pd.Series, low: pd.Series, close: pd.Series, 
            window: int = 14) -> pd.Series:
        """平均真实波幅"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()
    
    @staticmethod
    def WILLR(high: pd.Series, low: pd.Series, close: pd.Series, 
              window: int = 14) -> pd.Series:
        """威廉指标"""
        high_max = high.rolling(window=window).max()
        low_min = low.rolling(window=window).min()
        return (high_max - close) / (high_max - low_min) * -100
    
    @staticmethod
    def CCI(high: pd.Series, low: pd.Series, close: pd.Series, 
            window: int = 20) -> pd.Series:
        """顺势指标"""
        tp = (high + low + close) / 3
        ma = tp.rolling(window=window).mean()
        md = tp.rolling(window=window).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - ma) / (0.015 * md)
    
    @staticmethod
    def OBV(close: pd.Series, volume: pd.Series) -> pd.Series:
        """能量潮指标"""
        direction = np.where(close > close.shift(), 1, np.where(close < close.shift(), -1, 0))
        return (volume * direction).cumsum()
    
    @staticmethod
    def VWAP(high: pd.Series, low: pd.Series, close: pd.Series, 
             volume: pd.Series) -> pd.Series:
        """成交量加权平均价"""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()
    
    @staticmethod
    def MOMENTUM(close: pd.Series, window: int = 10) -> pd.Series:
        """动量指标"""
        return close - close.shift(window)
    
    @staticmethod
    def ROC(close: pd.Series, window: int = 10) -> pd.Series:
        """变动率指标"""
        return (close - close.shift(window)) / close.shift(window) * 100
    
    @staticmethod
    def ALPHA(close: pd.Series, benchmark: pd.Series, window: int = 60) -> pd.Series:
        """
        Alpha 因子
        相对于基准的超额收益
        """
        stock_return = close.pct_change()
        bench_return = benchmark.pct_change()
        return stock_return.rolling(window=window).mean() - bench_return.rolling(window=window).mean()
    
    @staticmethod
    def BETA(close: pd.Series, benchmark: pd.Series, window: int = 60) -> pd.Series:
        """
        Beta 因子
        相对于基准的敏感度
        """
        stock_return = close.pct_change()
        bench_return = benchmark.pct_change()
        covariance = stock_return.rolling(window=window).cov(bench_return)
        variance = bench_return.rolling(window=window).var()
        return covariance / variance


class FactorEvaluator:
    """因子评估器"""
    
    @staticmethod
    def calculate_ic(factor: pd.Series, forward_return: pd.Series) -> float:
        """
        计算信息系数 (IC)
        IC = corr(factor, forward_return)
        """
        return factor.corr(forward_return)
    
    @staticmethod
    def calculate_rank_ic(factor: pd.Series, forward_return: pd.Series) -> float:
        """
        计算秩信息系数 (Rank IC)
        Rank IC = corr(rank(factor), rank(forward_return))
        """
        return factor.rank().corr(forward_return.rank())
    
    @staticmethod
    def calculate_ir(ic_series: pd.Series) -> float:
        """
        计算信息比率 (IR)
        IR = mean(IC) / std(IC)
        """
        return ic_series.mean() / ic_series.std()
    
    @staticmethod
    def evaluate_factor(factor: pd.Series, 
                       forward_return: pd.Series,
                       group_by_date: bool = True) -> Dict[str, float]:
        """
        综合评估因子
        返回: IC, Rank IC, IR 等指标
        """
        if group_by_date:
            # 按日期分组计算 IC
            ic_series = factor.groupby(level=0).apply(
                lambda x: x.corr(forward_return.loc[x.name])
            )
            rank_ic_series = factor.groupby(level=0).apply(
                lambda x: x.rank().corr(forward_return.loc[x.name].rank())
            )
            
            return {
                'IC_mean': ic_series.mean(),
                'IC_std': ic_series.std(),
                'ICIR': ic_series.mean() / ic_series.std() if ic_series.std() != 0 else 0,
                'Rank_IC_mean': rank_ic_series.mean(),
                'Rank_IC_std': rank_ic_series.std(),
                'Rank_ICIR': rank_ic_series.mean() / rank_ic_series.std() if rank_ic_series.std() != 0 else 0,
                'IC_positive_ratio': (ic_series > 0).sum() / len(ic_series),
            }
        else:
            return {
                'IC': factor.corr(forward_return),
                'Rank_IC': factor.rank().corr(forward_return.rank()),
            }
```

#### 3.2.2 qlib 表达式集成

创建新文件 `kline_fetcher/qlib_integration.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qlib 集成模块
提供与 qlib 表达式引擎的集成接口
"""

from typing import List, Dict, Optional
import pandas as pd


class QlibFactorHelper:
    """qlib 因子辅助工具"""
    
    @staticmethod
    def build_data_handler_config(factor_expressions: List[str],
                                  factor_names: List[str],
                                  label_expression: str = "Ref($close, -2)/Ref($close, -1) - 1",
                                  label_name: str = "LABEL",
                                  instruments: str = "csi300",
                                  start_time: str = "2010-01-01",
                                  end_time: str = "2020-12-31") -> Dict:
        """
        构建 qlib DataHandler 配置
        
        参数:
            factor_expressions: 因子表达式列表 (如 ["MA($close, 20) - MA($close, 5)"])
            factor_names: 因子名称列表 (如 ["MA_DIFF"])
            label_expression: 标签表达式
            label_name: 标签名称
            instruments: 股票池
            start_time: 开始时间
            end_time: 结束时间
            
        返回:
            DataHandler 配置字典
        """
        return {
            "start_time": start_time,
            "end_time": end_time,
            "instruments": instruments,
            "data_loader": {
                "class": "QlibDataLoader",
                "kwargs": {
                    "config": {
                        "feature": [factor_expressions, factor_names],
                        "label": [[label_expression], [label_name]],
                    },
                    "freq": "day",
                },
            },
        }
    
    @staticmethod
    def build_dataset_config(data_handler_config: Dict,
                            train_start: str = "2010-01-01",
                            train_end: str = "2016-12-31",
                            valid_start: str = "2017-01-01",
                            valid_end: str = "2018-12-31",
                            test_start: str = "2019-01-01",
                            test_end: str = "2020-12-31") -> Dict:
        """
        构建 qlib Dataset 配置
        """
        return {
            "handler": data_handler_config,
            "segments": {
                "train": [train_start, train_end],
                "valid": [valid_start, valid_end],
                "test": [test_start, test_end],
            },
        }
    
    @staticmethod
    def load_factor_with_qlib(factor_expression: str,
                             factor_name: str,
                             instruments: str = "csi300",
                             start_time: str = "2010-01-01",
                             end_time: str = "2020-12-31") -> pd.DataFrame:
        """
        使用 qlib 加载因子数据
        
        示例:
            >>> df = QlibFactorHelper.load_factor_with_qlib(
            ...     "MA($close, 20) - MA($close, 5)",
            ...     "MA_DIFF",
            ...     instruments="csi300"
            ... )
        """
        try:
            from qlib.data.dataset.loader import QlibDataLoader
            
            config = {
                "feature": ([factor_expression], [factor_name]),
                "label": (["Ref($close, -2)/Ref($close, -1) - 1"], ["LABEL"]),
            }
            
            data_loader = QlibDataLoader(config=config)
            df = data_loader.load(instruments=instruments, 
                                 start_time=start_time, 
                                 end_time=end_time)
            return df
        except ImportError:
            raise ImportError("请先安装 qlib: pip install pyqlib")
    
    @staticmethod
    def evaluate_factor_ic(factor_expression: str,
                          factor_name: str = "FACTOR",
                          instruments: str = "csi300",
                          start_time: str = "2010-01-01",
                          end_time: str = "2020-12-31") -> Dict[str, float]:
        """
        评估因子 IC
        
        示例:
            >>> ic_metrics = QlibFactorHelper.evaluate_factor_ic(
            ...     "MA($close, 20) - MA($close, 5)",
            ...     instruments="csi300"
            ... )
            >>> print(f"IC Mean: {ic_metrics['IC_mean']}")
        """
        try:
            from qlib.data.dataset.handler import DataHandlerLP
            from qlib.data.dataset import DatasetH
            
            handler_config = QlibFactorHelper.build_data_handler_config(
                [factor_expression], [factor_name],
                instruments=instruments,
                start_time=start_time,
                end_time=end_time
            )
            
            segments = {
                "test": [start_time, end_time],
            }
            
            handler = DataHandlerLP(**handler_config)
            ds = DatasetH(handler=handler, segments=segments)
            df = ds.prepare("test")
            
            # 计算 IC
            ic_series = df.groupby("datetime").apply(
                lambda x: x[factor_name].corr(x["LABEL"])
            )
            
            return {
                'IC_mean': ic_series.mean(),
                'IC_std': ic_series.std(),
                'ICIR': ic_series.mean() / ic_series.std() if ic_series.std() != 0 else 0,
                'IC_positive_ratio': (ic_series > 0).sum() / len(ic_series),
            }
        except ImportError:
            raise ImportError("请先安装 qlib: pip install pyqlib")


class QlibExpressionBuilder:
    """qlib 表达式构建器"""
    
    @staticmethod
    def MA(field: str, window: int) -> str:
        """移动平均"""
        return f"Mean(${field}, {window})"
    
    @staticmethod
    def EMA(field: str, window: int) -> str:
        """指数移动平均"""
        return f"EWM(${field}, {window})"
    
    @staticmethod
    def MACD() -> Dict[str, str]:
        """MACD 因子表达式"""
        dif = "(EMA($close, 12) - EMA($close, 26))/$close"
        dea = f"EMA({dif}, 9)/$close"
        macd = f"2 * ({dif} - {dea})"
        return {
            'DIF': dif,
            'DEA': dea,
            'MACD': macd,
        }
    
    @staticmethod
    def RSI(window: int = 14) -> str:
        """RSI 因子表达式"""
        return f"RSI($close, {window})"
    
    @staticmethod
    def BOLL(window: int = 20, num_std: int = 2) -> Dict[str, str]:
        """布林带因子表达式"""
        middle = f"Mean($close, {window})"
        std = f"Std($close, {window})"
        upper = f"{middle} + {num_std} * {std}"
        lower = f"{middle} - {num_std} * {std}"
        return {
            'BOLL_UPPER': upper,
            'BOLL_MIDDLE': middle,
            'BOLL_LOWER': lower,
        }
    
    @staticmethod
    def MOMENTUM(window: int = 10) -> str:
        """动量因子"""
        return f"$close - Ref($close, {window})"
    
    @staticmethod
    def RETURN(window: int = 1) -> str:
        """收益率因子"""
        return f"Ref($close, -{window})/$close - 1"
    
    @staticmethod
    def VOLATILITY(window: int = 20) -> str:
        """波动率因子"""
        return f"Std($close/$close.shift(1) - 1, {window})"
    
    @staticmethod
    def TURNOVER_RATE() -> str:
        """换手率因子"""
        return "$volume / $circulating_shares"
    
    @staticmethod
    def AMOUNT_RATIO(window: int = 5) -> str:
        """量比因子"""
        return f"$volume / Mean($volume, {window})"
    
    @staticmethod
    def PRICE_POSITION(window: int = 20) -> str:
        """价格位置因子 (当前价格在过去N天的位置)"""
        return f"($close - Min($low, {window})) / (Max($high, {window}) - Min($low, {window}))"
```

---

### 3.3 批量因子计算

#### 3.3.1 批量因子计算器

创建新文件 `kline_fetcher/batch_factors.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
批量因子计算模块
支持批量计算多个股票的因子
"""

from typing import List, Dict, Optional
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from kline_fetcher import KLineFetcher
from kline_fetcher.factors import FactorCalculator


class BatchFactorCalculator:
    """批量因子计算器"""
    
    def __init__(self, fetcher: Optional[KLineFetcher] = None):
        self.fetcher = fetcher or KLineFetcher()
        self.calculator = FactorCalculator()
    
    def calculate_factors_for_stock(self, 
                                   code: str,
                                   factors: List[str],
                                   start_date: str,
                                   end_date: str,
                                   market: Optional[int] = None) -> pd.DataFrame:
        """
        计算单只股票的多个因子
        
        参数:
            code: 股票代码
            factors: 因子名称列表 (如 ["MA5", "MA20", "MACD"])
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码
            
        返回:
            包含所有因子的 DataFrame
        """
        # 获取K线数据
        kline_data = self.fetcher.fetch_day_kline(
            code, 
            begindate=start_date.replace("-", ""),
            enddate=end_date.replace("-", ""),
            market=market
        )
        
        if not kline_data:
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(kline_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 计算因子
        result = pd.DataFrame(index=df.index)
        
        for factor_name in factors:
            if factor_name == "MA5":
                result[factor_name] = self.calculator.MA(df['close'], 5)
            elif factor_name == "MA10":
                result[factor_name] = self.calculator.MA(df['close'], 10)
            elif factor_name == "MA20":
                result[factor_name] = self.calculator.MA(df['close'], 20)
            elif factor_name == "MA60":
                result[factor_name] = self.calculator.MA(df['close'], 60)
            elif factor_name == "EMA12":
                result[factor_name] = self.calculator.EMA(df['close'], 12)
            elif factor_name == "EMA26":
                result[factor_name] = self.calculator.EMA(df['close'], 26)
            elif factor_name == "MACD":
                macd_dict = self.calculator.MACD(df['close'])
                result['MACD_DIF'] = macd_dict['dif']
                result['MACD_DEA'] = macd_dict['dea']
                result['MACD'] = macd_dict['macd']
            elif factor_name == "RSI":
                result[factor_name] = self.calculator.RSI(df['close'])
            elif factor_name == "BOLL":
                boll_dict = self.calculator.BOLL(df['close'])
                result['BOLL_UPPER'] = boll_dict['upper']
                result['BOLL_MIDDLE'] = boll_dict['middle']
                result['BOLL_LOWER'] = boll_dict['lower']
            elif factor_name == "KDJ":
                kdj_dict = self.calculator.KDJ(df['high'], df['low'], df['close'])
                result['KDJ_K'] = kdj_dict['k']
                result['KDJ_D'] = kdj_dict['d']
                result['KDJ_J'] = kdj_dict['j']
            elif factor_name == "ATR":
                result[factor_name] = self.calculator.ATR(df['high'], df['low'], df['close'])
            elif factor_name == "WILLR":
                result[factor_name] = self.calculator.WILLR(df['high'], df['low'], df['close'])
            elif factor_name == "CCI":
                result[factor_name] = self.calculator.CCI(df['high'], df['low'], df['close'])
            elif factor_name == "OBV":
                result[factor_name] = self.calculator.OBV(df['close'], df['volume'])
            elif factor_name == "VWAP":
                result[factor_name] = self.calculator.VWAP(df['high'], df['low'], df['close'], df['volume'])
            elif factor_name == "MOMENTUM":
                result[factor_name] = self.calculator.MOMENTUM(df['close'])
            elif factor_name == "ROC":
                result[factor_name] = self.calculator.ROC(df['close'])
        
        return result
    
    def calculate_factors_batch(self,
                               stock_list: List[str],
                               factors: List[str],
                               start_date: str,
                               end_date: str,
                               max_workers: int = 5) -> Dict[str, pd.DataFrame]:
        """
        批量计算多只股票的因子
        
        参数:
            stock_list: 股票代码列表
            factors: 因子名称列表
            start_date: 开始日期
            end_date: 结束日期
            max_workers: 最大并发数
            
        返回:
            {股票代码: 因子DataFrame} 字典
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {
                executor.submit(
                    self.calculate_factors_for_stock,
                    code, factors, start_date, end_date
                ): code for code in stock_list
            }
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    df = future.result()
                    if not df.empty:
                        results[code] = df
                except Exception as e:
                    print(f"Error calculating factors for {code}: {e}")
        
        return results
```

---

### 3.4 数据转换优化

#### 3.4.1 扩展 converter.py

在 `converter.py` 中添加新方法:

```python
def day_kline_to_qlib_extended(self, 
                               code: str, 
                               kline_data: List[Dict],
                               mode: str = "append",
                               qlib_dir: Optional[str] = None,
                               include_extended_fields: bool = True) -> bool:
    """
    扩展的日K线转换，支持更多字段
    
    参数:
        code: 股票代码
        kline_data: K线数据
        mode: 写入模式
        qlib_dir: qlib 目录名
        include_extended_fields: 是否包含扩展字段
        
    返回:
        是否成功
    """
    if not kline_data:
        self.logger.warning(f"Empty kline data for {code}")
        return False
    
    # 构建基础字段数组
    field_arrays = self._build_day_arrays(kline_data)
    if field_arrays is None:
        return False
    
    # 添加扩展字段
    if include_extended_fields:
        extended_fields = self._build_extended_fields(kline_data, field_arrays)
        field_arrays.update(extended_fields)
    
    # 写入文件
    qlib_dir = qlib_dir or self.code_to_qlib_dir(code)
    stock_dir = os.path.join(self.features_dir, qlib_dir)
    os.makedirs(stock_dir, exist_ok=True)
    
    start_idx = field_arrays.pop("_start_idx")
    
    for field, arr in field_arrays.items():
        bin_path = os.path.join(stock_dir, f"{field}.day.bin")
        if mode == "overwrite" or not os.path.exists(bin_path):
            full_data = np.hstack([np.array([start_idx], dtype="<f"), arr.astype("<f")])
            full_data.tofile(str(bin_path))
        else:
            self._append_bin(bin_path, arr, start_idx)
    
    self.logger.info(f"Wrote extended day kline for {code}: {len(kline_data)} bars")
    return True

def _build_extended_fields(self, 
                          kline_data: List[Dict],
                          base_arrays: Dict) -> Dict:
    """
    构建扩展字段数组
    
    包括: factor, turnover_rate, change, change_pct 等
    """
    extended = {}
    
    # 计算涨跌幅
    close_arr = base_arrays['close']
    change_pct = np.full_like(close_arr, np.nan)
    change_pct[1:] = (close_arr[1:] - close_arr[:-1]) / close_arr[:-1] * 100
    extended['change_pct'] = change_pct
    
    # 计算涨跌额
    change = np.full_like(close_arr, np.nan)
    change[1:] = close_arr[1:] - close_arr[:-1]
    extended['change'] = change
    
    # 换手率 (如果有流通股本数据)
    # extended['turnover_rate'] = ...
    
    # 复权因子 (默认为1，后续可根据分红拆股调整)
    extended['factor'] = np.ones(len(close_arr), dtype=np.float32)
    
    return extended
```

---

## 四、实施计划

### 4.1 阶段一：基础字段扩展 (优先级：高)

**时间**: 1-2 周

**任务**:
1. ✅ 扩展 `fetcher.py`，添加复权因子、换手率等字段
2. ✅ 扩展 `converter.py`，支持新字段的写入
3. ✅ 更新测试用例，验证新字段正确性
4. ✅ 更新文档，说明新字段用途

**验收标准**:
- 支持 factor, turnover_rate, change, change_pct 字段
- 所有测试通过
- 文档更新完整

### 4.2 阶段二：因子计算工具 (优先级：高)

**时间**: 2-3 周

**任务**:
1. ✅ 创建 `factors.py`，实现常用技术指标
2. ✅ 创建 `qlib_integration.py`，提供 qlib 集成接口
3. ✅ 创建 `batch_factors.py`，支持批量因子计算
4. ✅ 编写测试用例，验证因子计算正确性
5. ✅ 编写使用示例和文档

**验收标准**:
- 支持 20+ 常用技术指标
- 支持 qlib 表达式集成
- 支持批量因子计算
- 文档完整

### 4.3 阶段三：因子评估工具 (优先级：中)

**时间**: 1-2 周

**任务**:
1. ✅ 实现因子 IC 计算
2. ✅ 实现因子 Rank IC 计算
3. ✅ 实现因子 IR 计算
4. ✅ 实现因子分组回测
5. ✅ 编写测试和文档

**验收标准**:
- 支持 IC, Rank IC, IR 计算
- 支持因子分组回测
- 文档完整

### 4.4 阶段四：性能优化 (优先级：中)

**时间**: 1 周

**任务**:
1. ✅ 优化数据读取性能
2. ✅ 优化因子计算性能
3. ✅ 添加缓存机制
4. ✅ 性能测试和优化

**验收标准**:
- 数据读取速度提升 50%
- 因子计算速度提升 30%
- 内存占用优化

---

## 五、技术架构

### 5.1 模块依赖关系

```
kline_fetcher/
├── fetcher.py          # 数据获取 (核心)
├── converter.py        # 数据转换 (核心)
├── factors.py          # 因子计算 (新增)
├── qlib_integration.py # qlib 集成 (新增)
├── batch_factors.py    # 批量计算 (新增)
└── download.py         # 批量下载
```

### 5.2 数据流

```
API 数据
  ↓
KLineFetcher (获取原始数据)
  ↓
FactorCalculator (计算衍生字段)
  ↓
KLineToQlib (转换为 qlib 格式)
  ↓
QlibFactorHelper (qlib 集成)
  ↓
因子计算和评估
```

---

## 六、使用示例

### 6.1 基础使用

```python
from kline_fetcher import KLineFetcher, KLineToQlib

# 初始化
fetcher = KLineFetcher()
converter = KLineToQlib()

# 获取数据 (包含扩展字段)
data = fetcher.fetch_day_kline("600519", count=100)

# 转换为 qlib 格式
converter.day_kline_to_qlib_extended("600519", data)
```

### 6.2 因子计算

```python
from kline_fetcher.factors import FactorCalculator
import pandas as pd

# 获取数据
fetcher = KLineFetcher()
data = fetcher.fetch_day_kline("600519", count=100)
df = pd.DataFrame(data)

# 计算因子
calculator = FactorCalculator()

# MACD
macd = calculator.MACD(df['close'])

# RSI
rsi = calculator.RSI(df['close'])

# 布林带
boll = calculator.BOLL(df['close'])
```

### 6.3 qlib 集成

```python
from kline_fetcher.qlib_integration import QlibFactorHelper

# 构建因子表达式
macd_expr = QlibFactorHelper.build_macd_expression()

# 加载因子
df = QlibFactorHelper.load_factor_with_qlib(
    macd_expr['MACD'],
    "MACD",
    instruments="csi300"
)

# 评估因子
ic_metrics = QlibFactorHelper.evaluate_factor_ic(
    macd_expr['MACD'],
    instruments="csi300"
)
print(f"IC Mean: {ic_metrics['IC_mean']}")
```

### 6.4 批量因子计算

```python
from kline_fetcher.batch_factors import BatchFactorCalculator

# 初始化
calculator = BatchFactorCalculator()

# 批量计算
results = calculator.calculate_factors_batch(
    stock_list=["600519", "000001", "000002"],
    factors=["MA5", "MA20", "MACD", "RSI", "BOLL"],
    start_date="2020-01-01",
    end_date="2020-12-31"
)

# 查看结果
for code, df in results.items():
    print(f"{code}: {df.shape}")
```

---

## 七、预期收益

### 7.1 功能收益

1. **完善数据字段**: 支持复权因子、换手率等关键字段
2. **简化因子开发**: 提供 20+ 常用技术指标
3. **提升开发效率**: 无需手写因子计算代码
4. **支持因子评估**: 快速验证因子有效性
5. **qlib 无缝集成**: 直接使用 qlib 表达式引擎

### 7.2 性能收益

1. **数据读取**: 提升 50% 速度
2. **因子计算**: 提升 30% 速度
3. **内存占用**: 优化 20%

### 7.3 用户收益

1. **降低学习成本**: 提供完整文档和示例
2. **提升开发效率**: 减少重复代码
3. **提高因子质量**: 提供评估工具

---

## 八、风险与挑战

### 8.1 技术风险

1. **复权因子计算**: 需要准确的分红拆股数据
2. **性能优化**: 大规模因子计算可能较慢
3. **qlib 版本兼容**: qlib 更新可能导致接口变化

### 8.2 解决方案

1. **复权因子**: 从 API 获取准确的复权数据
2. **性能优化**: 使用多进程、缓存等技术
3. **版本兼容**: 定期更新，保持兼容性

---

## 九、总结

本优化计划通过扩展数据字段、提供因子计算工具、支持 qlib 集成等方式，将 kline-fetcher 打造成一个完整的量化因子开发平台。优化后的 kline-fetcher 将：

1. ✅ 支持完整的 qlib 因子计算需求
2. ✅ 提供丰富的技术指标因子
3. ✅ 支持因子评估和验证
4. ✅ 提升开发和计算效率
5. ✅ 降低量化研究门槛

**建议优先实施阶段一和阶段二**，这两个阶段是支持 qlib factor 计算的核心功能。

---

*文档生成时间: 2026-05-21*
