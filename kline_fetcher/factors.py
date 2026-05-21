#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
因子计算工具模块
提供与 qlib 兼容的技术指标计算，支持 Alpha158/Alpha360 因子
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional


class FactorCalculator:
    """
    因子计算器 - 与 qlib 表达式引擎兼容
    支持 Alpha158/Alpha360 所需的所有基础因子
    """
    
    # === K线基础因子 ===
    @staticmethod
    def KMID(open_: pd.Series, close: pd.Series) -> pd.Series:
        """(close - open) / open"""
        return (close - open_) / open_
    
    @staticmethod
    def KLEN(high: pd.Series, low: pd.Series, open_: pd.Series) -> pd.Series:
        """(high - low) / open"""
        return (high - low) / open_
    
    @staticmethod
    def KMID2(open_: pd.Series, close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
        """(close - open) / (high - low)"""
        return (close - open_) / (high - low)
    
    @staticmethod
    def KUP(high: pd.Series, open_: pd.Series, close: pd.Series) -> pd.Series:
        """(high - Max(open, close)) / open"""
        return (high - pd.concat([open_, close], axis=1).max(axis=1)) / open_
    
    @staticmethod
    def KUP2(high: pd.Series, open_: pd.Series, close: pd.Series, low: pd.Series) -> pd.Series:
        """(high - Max(open, close)) / (high - low)"""
        return (high - pd.concat([open_, close], axis=1).max(axis=1)) / (high - low)
    
    @staticmethod
    def KLOW(open_: pd.Series, close: pd.Series, low: pd.Series) -> pd.Series:
        """(Min(open, close) - low) / open"""
        return (pd.concat([open_, close], axis=1).min(axis=1) - low) / open_
    
    @staticmethod
    def KLOW2(open_: pd.Series, close: pd.Series, low: pd.Series, high: pd.Series) -> pd.Series:
        """(Min(open, close) - low) / (high - low)"""
        return (pd.concat([open_, close], axis=1).min(axis=1) - low) / (high - low)
    
    @staticmethod
    def KSFT(close: pd.Series, high: pd.Series, low: pd.Series, open_: pd.Series) -> pd.Series:
        """(2 * close - high - low) / open"""
        return (2 * close - high - low) / open_
    
    @staticmethod
    def KSFT2(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
        """(2 * close - high - low) / (high - low)"""
        return (2 * close - high - low) / (high - low)
    
    # === 趋势类因子 ===
    @staticmethod
    def ROC(close: pd.Series, window: int) -> pd.Series:
        """close / Ref(close, window)"""
        return close / close.shift(window)
    
    @staticmethod
    def MA(close: pd.Series, window: int) -> pd.Series:
        """Mean(close, window) / close"""
        return close.rolling(window=window).mean() / close
    
    @staticmethod
    def BETA(close: pd.Series, window: int) -> pd.Series:
        """Slope(close, window) / close"""
        def slope(x):
            if len(x) < 2:
                return np.nan
            return np.polyfit(range(len(x)), x, 1)[0]
        return close.rolling(window=window).apply(slope) / close
    
    @staticmethod
    def RSQR(close: pd.Series, window: int) -> pd.Series:
        """Rsquare(close, window)"""
        def rsquare(x):
            if len(x) < 2:
                return np.nan
            slope, intercept = np.polyfit(range(len(x)), x, 1)
            predicted = intercept + slope * np.arange(len(x))
            ss_tot = np.sum((x - x.mean()) ** 2)
            ss_res = np.sum((x - predicted) ** 2)
            return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        return close.rolling(window=window).apply(rsquare)
    
    @staticmethod
    def RESI(close: pd.Series, window: int) -> pd.Series:
        """Resi(close, window) / close"""
        def resi(x):
            if len(x) < 2:
                return np.nan
            slope, intercept = np.polyfit(range(len(x)), x, 1)
            predicted = intercept + slope * np.arange(len(x))
            residuals = x - predicted
            return residuals[-1] if len(residuals) > 0 else np.nan
        return close.rolling(window=window).apply(resi) / close
    
    # === 波动类因子 ===
    @staticmethod
    def STD(close: pd.Series, window: int) -> pd.Series:
        """Std(close, window) / close"""
        return close.rolling(window=window).std() / close
    
    @staticmethod
    def MAX(high: pd.Series, window: int) -> pd.Series:
        """Max(high, window) / close"""
        return high.rolling(window=window).max() / high
    
    @staticmethod
    def MIN(low: pd.Series, window: int) -> pd.Series:
        """Min(low, window) / close"""
        return low.rolling(window=window).min() / low
    
    @staticmethod
    def QTLU(close: pd.Series, window: int, quantile: float = 0.8) -> pd.Series:
        """Quantile(close, window, 0.8) / close"""
        return close.rolling(window=window).quantile(quantile) / close
    
    @staticmethod
    def QTLD(close: pd.Series, window: int, quantile: float = 0.2) -> pd.Series:
        """Quantile(close, window, 0.2) / close"""
        return close.rolling(window=window).quantile(quantile) / close
    
    @staticmethod
    def RSV(close: pd.Series, high: pd.Series, low: pd.Series, window: int) -> pd.Series:
        """(close - Min(low, window)) / (Max(high, window) - Min(low, window))"""
        min_low = low.rolling(window=window).min()
        max_high = high.rolling(window=window).max()
        return (close - min_low) / (max_high - min_low)
    
    # === 极值位置类因子 ===
    @staticmethod
    def IMAX(high: pd.Series, window: int) -> pd.Series:
        """IdxMax(high, window) / window"""
        def idxmax(x):
            if len(x) < window:
                return np.nan
            return float(np.argmax(x)) / window
        return high.rolling(window=window).apply(idxmax)
    
    @staticmethod
    def IMIN(low: pd.Series, window: int) -> pd.Series:
        """IdxMin(low, window) / window"""
        def idxmin(x):
            if len(x) < window:
                return np.nan
            return float(np.argmin(x)) / window
        return low.rolling(window=window).apply(idxmin)
    
    @staticmethod
    def IMXD(high: pd.Series, low: pd.Series, window: int) -> pd.Series:
        """(IdxMax(high, window) - IdxMin(low, window)) / window"""
        max_idx = high.rolling(window=window).apply(lambda x: float(np.argmax(x)))
        min_idx = low.rolling(window=window).apply(lambda x: float(np.argmin(x)))
        return (max_idx - min_idx) / window
    
    # === 价量统计类因子 ===
    @staticmethod
    def CORR(close: pd.Series, volume: pd.Series, window: int) -> pd.Series:
        """Corr(close, Log(volume+1), window)"""
        log_volume = np.log(volume + 1)
        return close.rolling(window=window).corr(log_volume)
    
    @staticmethod
    def CORD(close: pd.Series, volume: pd.Series, window: int) -> pd.Series:
        """Corr(close/Ref(close,1), Log(volume/Ref(volume,1)+1), window)"""
        close_ret = close / close.shift(1)
        vol_ratio = volume / volume.shift(1)
        log_vol_ratio = np.log(vol_ratio + 1)
        return close_ret.rolling(window=window).corr(log_vol_ratio)
    
    @staticmethod
    def CNTP(close: pd.Series, window: int) -> pd.Series:
        """Mean(close > Ref(close, 1), window)"""
        return (close > close.shift(1)).rolling(window=window).mean()
    
    @staticmethod
    def CNTN(close: pd.Series, window: int) -> pd.Series:
        """Mean(close < Ref(close, 1), window)"""
        return (close < close.shift(1)).rolling(window=window).mean()
    
    @staticmethod
    def CNTD(close: pd.Series, window: int) -> pd.Series:
        """Mean(close > Ref(close, 1), window) - Mean(close < Ref(close, 1), window)"""
        up = (close > close.shift(1)).rolling(window=window).mean()
        down = (close < close.shift(1)).rolling(window=window).mean()
        return up - down
    
    @staticmethod
    def COVP(close: pd.Series, volume: pd.Series, window: int) -> pd.Series:
        """Cov(close, volume, window)"""
        return close.rolling(window=window).cov(volume)
    
    @staticmethod
    def AMCN(volume: pd.Series, window: int) -> pd.Series:
        """Mean((volume - Mean(volume, window))^2, window)"""
        mean_vol = volume.rolling(window=window).mean()
        return ((volume - mean_vol) ** 2).rolling(window=window).mean()
    
    @staticmethod
    def MAAM(amount: pd.Series, window: int) -> pd.Series:
        """Mean(amount, window) / amount"""
        return amount.rolling(window=window).mean() / amount
    
    @staticmethod
    def CVOL(volume: pd.Series, window: int) -> pd.Series:
        """Std(volume, window) / Mean(volume, window)"""
        std = volume.rolling(window=window).std()
        mean = volume.rolling(window=window).mean()
        return std / mean
    
    # === 常用技术指标 ===
    @staticmethod
    def MACD(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD 指标"""
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = (ema_fast - ema_slow) / close
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = 2 * (dif - dea)
        return {'DIF': dif, 'DEA': dea, 'MACD': macd}
    
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
        """布林带"""
        middle = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    @staticmethod
    def ATR(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """平均真实波幅"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()


class FactorEvaluator:
    """
    因子评估器 - 计算 IC、Rank IC、IR 等指标
    """
    
    @staticmethod
    def calculate_ic(factor: pd.Series, forward_return: pd.Series) -> float:
        """计算信息系数"""
        return factor.corr(forward_return)
    
    @staticmethod
    def calculate_rank_ic(factor: pd.Series, forward_return: pd.Series) -> float:
        """计算秩信息系数"""
        return factor.rank().corr(forward_return.rank())
    
    @staticmethod
    def calculate_ir(ic_series: pd.Series) -> float:
        """计算信息比率"""
        if ic_series.std() == 0:
            return 0.0
        return ic_series.mean() / ic_series.std()
    
    @staticmethod
    def evaluate_factor(factor: pd.Series, forward_return: pd.Series) -> Dict[str, float]:
        """综合评估因子"""
        return {
            'IC': FactorEvaluator.calculate_ic(factor, forward_return),
            'Rank_IC': FactorEvaluator.calculate_rank_ic(factor, forward_return),
        }
