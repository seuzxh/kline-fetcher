#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
qlib 集成模块
提供与 qlib 数据格式和表达式引擎的无缝集成
"""

from typing import List, Dict, Optional
import numpy as np
import pandas as pd


class QlibDataHelper:
    """
    qlib 数据格式辅助工具
    """
    
    @staticmethod
    def ensure_qlib_format(kline_data: List[Dict]) -> pd.DataFrame:
        """
        确保数据符合 qlib 格式要求
        
        参数:
            kline_data: K线数据列表
            
        返回:
            符合 qlib 格式的 DataFrame
        """
        df = pd.DataFrame(kline_data)
        
        # 确保必需字段存在
        required_fields = ["date", "open", "close", "high", "low", "volume", "factor"]
        for field in required_fields:
            if field not in df.columns:
                if field == "factor":
                    df[field] = 1.0  # 默认复权因子为 1
                else:
                    df[field] = np.nan
        
        # 日期格式化
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 确保数据类型正确
        numeric_fields = ["open", "close", "high", "low", "volume", "factor", 
                         "vwap", "money", "change", "change_pct"]
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce')
        
        return df
    
    @staticmethod
    def build_data_loader_config(factor_expressions: List[str],
                                factor_names: List[str],
                                label_expression: str = "Ref($close, -2)/Ref($close, -1) - 1",
                                label_name: str = "LABEL",
                                instruments: str = "csi300",
                                start_time: str = "2010-01-01",
                                end_time: str = "2020-12-31") -> Dict:
        """
        构建 qlib DataLoader 配置
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
    def evaluate_factor_ic(factor_expression: str,
                          instruments: str = "csi300",
                          start_time: str = "2010-01-01",
                          end_time: str = "2020-12-31") -> Dict[str, float]:
        """
        使用 qlib 评估因子 IC
        
        需要先安装 qlib: pip install pyqlib
        """
        try:
            from qlib.data.dataset.handler import DataHandlerLP
            from qlib.data.dataset import DatasetH
            
            handler_config = QlibDataHelper.build_data_loader_config(
                [factor_expression], ["FACTOR"],
                instruments=instruments,
                start_time=start_time,
                end_time=end_time
            )
            
            segments = {"test": [start_time, end_time]}
            handler = DataHandlerLP(**handler_config)
            ds = DatasetH(handler=handler, segments=segments)
            df = ds.prepare("test")
            
            # 计算 IC
            ic_series = df.groupby("datetime").apply(
                lambda x: x["FACTOR"].corr(x["LABEL"])
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
    """
    qlib 表达式构建器
    生成符合 qlib 表达式引擎语法的因子表达式
    """
    
    @staticmethod
    def MA(field: str, window: int) -> str:
        """Mean(${field}, {window})"""
        return f"Mean(${field}, {window})"
    
    @staticmethod
    def EMA(field: str, window: int) -> str:
        """EWM(${field}, {window})"""
        return f"EWM(${field}, {window})"
    
    @staticmethod
    def MACD() -> str:
        """MACD 因子表达式"""
        return "(EMA($close, 12) - EMA($close, 26))/$close - EMA((EMA($close, 12) - EMA($close, 26))/$close, 9)/$close"
    
    @staticmethod
    def RSI(window: int = 14) -> str:
        """RSI 因子表达式"""
        return f"RSI($close, {window})"
    
    @staticmethod
    def ROC(field: str, window: int) -> str:
        """${field} / Ref(${field}, {window})"""
        return f"${field} / Ref(${field}, {window})"
    
    @staticmethod
    def STD(field: str, window: int) -> str:
        """Std(${field}, {window})"""
        return f"Std(${field}, {window})"
    
    @staticmethod
    def CORR(field1: str, field2: str, window: int) -> str:
        """Corr(${field1}, ${field2}, {window})"""
        return f"Corr(${field1}, ${field2}, {window})"
    
    @staticmethod
    def REF(field: str, periods: int) -> str:
        """Ref(${field}, {periods})"""
        return f"Ref(${field}, {periods})"
    
    @staticmethod
    def MAX(field: str, window: int) -> str:
        """Max(${field}, {window})"""
        return f"Max(${field}, {window})"
    
    @staticmethod
    def MIN(field: str, window: int) -> str:
        """Min(${field}, {window})"""
        return f"Min(${field}, {window})"
    
    @staticmethod
    def RSV(window: int) -> str:
        """(close - Min(low, window)) / (Max(high, window) - Min(low, window))"""
        return f"($close - Min($low, {window})) / (Max($high, {window}) - Min($low, {window}))"


class Alpha158Expressions:
    """
    Alpha158 因子表达式集合
    包含 158 个技术因子的 qlib 表达式
    """
    
    @staticmethod
    def get_kline_factors() -> Dict[str, str]:
        """K线基础因子（9个）"""
        return {
            'KMID': '($close - $open) / $open',
            'KLEN': '($high - $low) / $open',
            'KMID2': '($close - $open) / ($high - $low)',
            'KUP': '($high - Max($open, $close)) / $open',
            'KUP2': '($high - Max($open, $close)) / ($high - $low)',
            'KLOW': '(Min($open, $close) - $low) / $open',
            'KLOW2': '(Min($open, $close) - $low) / ($high - $low)',
            'KSFT': '(2 * $close - $high - $low) / $open',
            'KSFT2': '(2 * $close - $high - $low) / ($high - $low)',
        }
    
    @staticmethod
    def get_static_factors() -> Dict[str, str]:
        """静态价格因子（4个）"""
        return {
            'OPEN0': '$open / $close',
            'HIGH0': '$high / $close',
            'LOW0': '$low / $close',
            'VWAP0': '$vwap / $close',
        }
    
    @staticmethod
    def get_trend_factors() -> Dict[str, str]:
        """趋势类因子（25个）"""
        factors = {}
        windows = [5, 10, 20, 30, 60]
        
        for w in windows:
            factors[f'ROC{w}'] = f'$close / Ref($close, {w})'
            factors[f'MA{w}'] = f'Mean($close, {w}) / $close'
            factors[f'BETA{w}'] = f'Slope($close, {w}) / $close'
            factors[f'RSQR{w}'] = f'Rsquare($close, {w})'
            factors[f'RESI{w}'] = f'Resi($close, {w}) / $close'
        
        return factors
    
    @staticmethod
    def get_volatility_factors() -> Dict[str, str]:
        """波动类因子（30个）"""
        factors = {}
        windows = [5, 10, 20, 30, 60]
        
        for w in windows:
            factors[f'STD{w}'] = f'Std($close, {w}) / $close'
            factors[f'MAX{w}'] = f'Max($high, {w}) / $close'
            factors[f'MIN{w}'] = f'Min($low, {w}) / $close'
            factors[f'QTLU{w}'] = f'Quantile($close, {w}, 0.8) / $close'
            factors[f'QTLD{w}'] = f'Quantile($close, {w}, 0.2) / $close'
            factors[f'RSV{w}'] = f'($close - Min($low, {w})) / (Max($high, {w}) - Min($low, {w}))'
        
        return factors
    
    @staticmethod
    def get_extreme_factors() -> Dict[str, str]:
        """极值位置类因子（15个）"""
        factors = {}
        windows = [5, 10, 20, 30, 60]
        
        for w in windows:
            factors[f'IMAX{w}'] = f'IdxMax($high, {w}) / {w}'
            factors[f'IMIN{w}'] = f'IdxMin($low, {w}) / {w}'
            factors[f'IMXD{w}'] = f'(IdxMax($high, {w}) - IdxMin($low, {w})) / {w}'
        
        return factors
    
    @staticmethod
    def get_price_volume_factors() -> Dict[str, str]:
        """价量统计类因子（45个）"""
        factors = {}
        windows = [5, 10, 20, 30, 60]
        
        for w in windows:
            factors[f'CORR{w}'] = f'Corr($close, Log($volume+1), {w})'
            factors[f'CORD{w}'] = f'Corr($close/Ref($close,1), Log($volume/Ref($volume,1)+1), {w})'
            factors[f'CNTP{w}'] = f'Mean($close > Ref($close,1), {w})'
            factors[f'CNTN{w}'] = f'Mean($close < Ref($close,1), {w})'
            factors[f'CNTD{w}'] = f'Mean($close>Ref($close,1),{w}) - Mean($close<Ref($close,1),{w})'
            factors[f'COVP{w}'] = f'Cov($close, $volume, {w})'
            factors[f'AMCN{w}'] = f'Mean(($volume - Mean($volume,{w}))^2, {w})'
            factors[f'MAAM{w}'] = f'Mean($amount, {w}) / $amount'
            factors[f'CVOL{w}'] = f'Std($volume, {w}) / Mean($volume, {w})'
        
        return factors
    
    @staticmethod
    def get_all_factors() -> Dict[str, str]:
        """获取所有 Alpha158 因子表达式"""
        all_factors = {}
        all_factors.update(Alpha158Expressions.get_kline_factors())
        all_factors.update(Alpha158Expressions.get_static_factors())
        all_factors.update(Alpha158Expressions.get_trend_factors())
        all_factors.update(Alpha158Expressions.get_volatility_factors())
        all_factors.update(Alpha158Expressions.get_extreme_factors())
        all_factors.update(Alpha158Expressions.get_price_volume_factors())
        return all_factors
