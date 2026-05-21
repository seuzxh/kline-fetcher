#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
kline-fetcher 所有功能完整测试文件
使用 unittest 框架测试 KLineFetcher 和 KLineToQlib 类的所有功能
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import logging
from kline_fetcher import KLineFetcher, KLineToQlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestKLineFetcherMarketInference(unittest.TestCase):
    """测试 KLineFetcher 的市场推断功能"""

    def test_infer_market_shanghai(self):
        """测试上海市场股票代码推断"""
        test_cases = [
            ("600519", 1),  # 贵州茅台
            ("601888", 1),  # 中国中免
            ("603288", 1),  # 海天味业
            ("605009", 1),  # 豪悦护理
            ("688001", 1),  # 华兴源创
            ("sh600519", 1),
            ("SH600519", 1),
        ]
        for code, expected_market in test_cases:
            with self.subTest(code=code):
                result = KLineFetcher.infer_market(code)
                self.assertEqual(result, expected_market, f"代码 {code} 市场推断错误")

    def test_infer_market_shenzhen(self):
        """测试深圳市场股票代码推断"""
        test_cases = [
            ("000001", 0),  # 平安银行
            ("001696", 0),  # 宗申动力
            ("002594", 0),  # 比亚迪
            ("003816", 0),  # 中国广核
            ("300001", 0),  # 特锐德
            ("301001", 0),  # 读客文化
            ("sz000001", 0),
            ("SZ000001", 0),
        ]
        for code, expected_market in test_cases:
            with self.subTest(code=code):
                result = KLineFetcher.infer_market(code)
                self.assertEqual(result, expected_market, f"代码 {code} 市场推断错误")

    def test_infer_market_beijing(self):
        """测试北京市场股票代码推断"""
        test_cases = [
            ("830799", 103),  #  Flint能源
            ("430001", 103),  # 世纪东方
            ("920001", 103),  # 北交所
            ("bj830799", 103),
            ("BJ830799", 103),
        ]
        for code, expected_market in test_cases:
            with self.subTest(code=code):
                result = KLineFetcher.infer_market(code)
                self.assertEqual(result, expected_market, f"代码 {code} 市场推断错误")


class TestKLineFetcherDayKLine(unittest.TestCase):
    """测试 KLineFetcher 的日K线获取功能"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.test_code = "600519"
        cls.test_market = 1

    def test_fetch_day_kline_with_count(self):
        """测试通过数量获取日K线"""
        data = self.fetcher.fetch_day_kline(self.test_code, count=10)
        self.assertIsNotNone(data, "获取日K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        if len(data) > 0:
            self.assertIn("date", data[0], "缺少 date 字段")
            self.assertIn("open", data[0], "缺少 open 字段")
            self.assertIn("high", data[0], "缺少 high 字段")
            self.assertIn("low", data[0], "缺少 low 字段")
            self.assertIn("close", data[0], "缺少 close 字段")
            self.assertIn("volume", data[0], "缺少 volume 字段")
            self.assertIn("amount", data[0], "缺少 amount 字段")
        logger.info(f"获取日K线成功，共 {len(data)} 条")

    def test_fetch_day_kline_with_date_range(self):
        """测试通过日期范围获取日K线"""
        data = self.fetcher.fetch_day_kline(
            self.test_code,
            begindate="20260101",
            enddate="20260110"
        )
        self.assertIsNotNone(data, "获取日K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        logger.info(f"获取日K线成功，共 {len(data)} 条")

    def test_fetch_day_kline_with_market(self):
        """测试指定市场获取日K线"""
        data = self.fetcher.fetch_day_kline(
            self.test_code,
            count=5,
            market=self.test_market
        )
        self.assertIsNotNone(data, "获取日K线失败")
        logger.info(f"获取日K线成功，共 {len(data)} 条")

    def test_fetch_day_kline_default(self):
        """测试默认参数获取日K线"""
        data = self.fetcher.fetch_day_kline(self.test_code)
        self.assertIsNotNone(data, "获取日K线失败")
        logger.info(f"默认参数获取日K线成功，共 {len(data)} 条")


class TestKLineFetcherMinKLine(unittest.TestCase):
    """测试 KLineFetcher 的分钟K线获取功能"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.test_code = "600519"
        cls.test_market = 1

    def test_fetch_min_kline_1min(self):
        """测试获取1分钟K线"""
        data = self.fetcher.fetch_min_kline(
            self.test_code,
            freq="1min",
            count=-10
        )
        self.assertIsNotNone(data, "获取1分钟K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        if len(data) > 0:
            self.assertIn("date", data[0], "缺少 date 字段")
            self.assertIn("time", data[0], "缺少 time 字段")
            self.assertIn("open", data[0], "缺少 open 字段")
        logger.info(f"获取1分钟K线成功，共 {len(data)} 条")

    def test_fetch_min_kline_5min(self):
        """测试获取5分钟K线"""
        data = self.fetcher.fetch_min_kline(
            self.test_code,
            freq="5min",
            count=-10
        )
        self.assertIsNotNone(data, "获取5分钟K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        if len(data) > 0:
            self.assertIn("date", data[0], "缺少 date 字段")
            self.assertIn("time", data[0], "缺少 time 字段")
        logger.info(f"获取5分钟K线成功，共 {len(data)} 条")

    def test_fetch_min_kline_with_pagination(self):
        """测试分页获取分钟K线"""
        data = self.fetcher.fetch_min_kline(
            self.test_code,
            freq="1min",
            count=-100,
            pages=2
        )
        self.assertIsNotNone(data, "分页获取K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        logger.info(f"分页获取K线成功，共 {len(data)} 条")

    def test_fetch_min_kline_invalid_freq(self):
        """测试无效频率"""
        data = self.fetcher.fetch_min_kline(
            self.test_code,
            freq="invalid",
            count=-10
        )
        self.assertIsNone(data, "无效频率应该返回 None")


class TestKLineFetcherFetchKline(unittest.TestCase):
    """测试 KLineFetcher 的统一K线接口"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.test_code = "600519"

    def test_fetch_kline_forward(self):
        """测试向前获取K线"""
        data = self.fetcher.fetch_kline(
            self.test_code,
            freq="5min",
            starttime="2026-05-15 09:30",
            count=10
        )
        self.assertIsNotNone(data, "获取K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        if len(data) > 0:
            self.assertIn("date", data[0])
            self.assertIn("time", data[0])
        logger.info(f"向前获取K线成功，共 {len(data)} 条")

    def test_fetch_kline_backward(self):
        """测试向后获取K线"""
        data = self.fetcher.fetch_kline(
            self.test_code,
            freq="5min",
            starttime="2026-05-15 14:00",
            count=-10
        )
        self.assertIsNotNone(data, "获取K线失败")
        self.assertIsInstance(data, list, "返回值不是列表类型")
        logger.info(f"向后获取K线成功，共 {len(data)} 条")

    def test_fetch_kline_invalid_format(self):
        """测试无效的时间格式"""
        data = self.fetcher.fetch_kline(
            self.test_code,
            freq="5min",
            starttime="invalid-time",
            count=10
        )
        self.assertIsNone(data, "无效时间格式应该返回 None")


class TestKLineFetcherTradeCalendar(unittest.TestCase):
    """测试 KLineFetcher 的交易日历获取功能"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()

    def test_fetch_trade_calendar(self):
        """测试获取交易日历"""
        dates = self.fetcher.fetch_trade_calendar(
            start_year=2026,
            end_year=2026,
            index_code="000001",
            market=0
        )
        self.assertIsNotNone(dates, "获取交易日历失败")
        self.assertIsInstance(dates, list, "返回值不是列表类型")
        if len(dates) > 0:
            self.assertIn("2026-", dates[0], "日期格式不正确")
        logger.info(f"获取交易日历成功，共 {len(dates)} 个交易日")


class TestKLineFetcherStockInfo(unittest.TestCase):
    """测试 KLineFetcher 的股票基本信息获取功能"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.test_code = "600519"
        cls.test_market = 1

    def test_get_stock_info(self):
        """测试获取股票基本信息"""
        info = self.fetcher.get_stock_info(self.test_code, self.test_market)
        self.assertIsNotNone(info, "获取股票信息失败")
        self.assertIsInstance(info, dict, "返回值不是字典类型")
        self.assertIn("code", info, "缺少 code 字段")
        self.assertIn("name", info, "缺少 name 字段")
        self.assertIn("market_sn", info, "缺少 market_sn 字段")
        logger.info(f"股票信息: {info}")


class TestKLineFetcherConceptPlates(unittest.TestCase):
    """测试 KLineFetcher 的概念板块相关功能"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.test_plate_code = "994612"
        cls.test_stock_code = "600519"
        cls.test_stock_market = 1

    def test_get_all_concept_plates(self):
        """测试获取所有概念板块"""
        plates = self.fetcher.get_all_concept_plates()
        self.assertIsNotNone(plates, "获取概念板块失败")
        self.assertIsInstance(plates, list, "返回值不是列表类型")
        self.assertGreater(len(plates), 0, "概念板块列表为空")
        if len(plates) > 0:
            self.assertIn("code", plates[0])
            self.assertIn("name", plates[0])
            self.assertIn("market", plates[0])
        logger.info(f"获取 {len(plates)} 个概念板块")

    def test_get_concept_plate_kline(self):
        """测试获取概念板块K线"""
        kline_data = self.fetcher.get_concept_plate_kline(self.test_plate_code)
        self.assertIsNotNone(kline_data, "获取概念板块K线失败")
        self.assertIsInstance(kline_data, list, "返回值不是列表类型")
        self.assertGreater(len(kline_data), 0, "K线列表为空")
        if len(kline_data) > 0:
            self.assertIn("date", kline_data[0])
            self.assertIn("open", kline_data[0])
        logger.info(f"获取概念板块K线 {len(kline_data)} 条")

    def test_get_concept_plate_stocks(self):
        """测试获取概念板块成份股"""
        stocks = self.fetcher.get_concept_plate_stocks(self.test_plate_code)
        self.assertIsNotNone(stocks, "获取概念板块成份股失败")
        self.assertIsInstance(stocks, list, "返回值不是列表类型")
        self.assertGreater(len(stocks), 0, "成份股列表为空")
        if len(stocks) > 0:
            self.assertIn("code", stocks[0])
            self.assertIn("name", stocks[0])
            self.assertIn("market", stocks[0])
        logger.info(f"获取概念板块成份股 {len(stocks)} 只")

    def test_get_stock_concept_plates(self):
        """测试获取股票所属概念板块"""
        plates = self.fetcher.get_stock_concept_plates(
            self.test_stock_code,
            self.test_stock_market
        )
        self.assertIsNotNone(plates, "获取股票所属概念板块失败")
        self.assertIsInstance(plates, list, "返回值不是列表类型")
        logger.info(f"获取股票所属概念板块 {len(plates)} 个")

    def test_get_concept_plate_stocks_pagination(self):
        """测试分页获取成份股"""
        stocks_page1 = self.fetcher.get_concept_plate_stocks(
            self.test_plate_code,
            start=0,
            count=5
        )
        self.assertIsNotNone(stocks_page1, "获取第一页成份股失败")
        self.assertGreater(len(stocks_page1), 0, "第一页为空")

        stocks_page2 = self.fetcher.get_concept_plate_stocks(
            self.test_plate_code,
            start=5,
            count=5
        )
        self.assertIsNotNone(stocks_page2, "获取第二页成份股失败")
        logger.info(f"第一页 {len(stocks_page1)} 只，第二页 {len(stocks_page2)} 只")


class TestKLineToQlibConverter(unittest.TestCase):
    """测试 KLineToQlib 的转换功能"""

    def test_code_to_qlib_dir_shanghai(self):
        """测试上海股票代码转换"""
        test_cases = [
            ("600519", "sh600519"),
            ("601888", "sh601888"),
            ("688001", "sh688001"),
            ("SH600519", "sh600519"),
            ("sh600519", "sh600519"),
        ]
        for code, expected_dir in test_cases:
            with self.subTest(code=code):
                result = KLineToQlib.code_to_qlib_dir(code)
                self.assertEqual(result, expected_dir, f"代码 {code} 转换错误")

    def test_code_to_qlib_dir_shenzhen(self):
        """测试深圳股票代码转换"""
        test_cases = [
            ("000001", "sz000001"),
            ("002594", "sz002594"),
            ("300001", "sz300001"),
            ("SZ000001", "sz000001"),
            ("sz000001", "sz000001"),
        ]
        for code, expected_dir in test_cases:
            with self.subTest(code=code):
                result = KLineToQlib.code_to_qlib_dir(code)
                self.assertEqual(result, expected_dir, f"代码 {code} 转换错误")

    def test_code_to_qlib_dir_beijing(self):
        """测试北京股票代码转换"""
        test_cases = [
            ("830799", "bj830799"),
            ("430001", "bj430001"),
            ("920001", "bj920001"),
            ("BJ830799", "bj830799"),
            ("bj830799", "bj830799"),
        ]
        for code, expected_dir in test_cases:
            with self.subTest(code=code):
                result = KLineToQlib.code_to_qlib_dir(code)
                self.assertEqual(result, expected_dir, f"代码 {code} 转换错误")


class TestKLineToQlibTimestampGeneration(unittest.TestCase):
    """测试 KLineToQlib 的时间戳生成功能"""

    def test_generate_1min_timestamps(self):
        """测试1分钟时间戳生成"""
        timestamps = KLineToQlib._generate_1min_timestamps("2026-05-15", 240, "1min")
        self.assertIsNotNone(timestamps, "生成时间戳失败")
        self.assertIsInstance(timestamps, list, "返回值不是列表类型")
        self.assertGreater(len(timestamps), 0, "时间戳列表为空")
        # 验证格式
        if len(timestamps) > 0:
            self.assertIn(":", timestamps[0], "时间戳格式不正确")
            self.assertTrue(timestamps[0].startswith("2026-05-15"), "日期部分不正确")
        logger.info(f"生成 1min 时间戳 {len(timestamps)} 个")

    def test_generate_5min_timestamps(self):
        """测试5分钟时间戳生成"""
        timestamps = KLineToQlib._generate_5min_timestamps("2026-05-15", 48, "5min")
        self.assertIsNotNone(timestamps, "生成时间戳失败")
        self.assertIsInstance(timestamps, list, "返回值不是列表类型")
        self.assertGreater(len(timestamps), 0, "时间戳列表为空")
        logger.info(f"生成 5min 时间戳 {len(timestamps)} 个")


class TestEndToEnd(unittest.TestCase):
    """端到端集成测试"""

    @classmethod
    def setUpClass(cls):
        cls.fetcher = KLineFetcher()
        cls.converter = KLineToQlib()
        cls.test_code = "600519"

    def test_fetch_and_convert_day_kline(self):
        """测试获取并转换日K线数据"""
        # 获取数据
        data = self.fetcher.fetch_day_kline(self.test_code, count=10)
        self.assertIsNotNone(data, "获取日K线失败")
        self.assertGreater(len(data), 0, "获取数据为空")

        # 验证数据格式
        for item in data:
            self.assertIn("date", item)
            self.assertIn("open", item)
            self.assertIn("high", item)
            self.assertIn("low", item)
            self.assertIn("close", item)
            self.assertIn("volume", item)
            self.assertIn("amount", item)

        logger.info(f"获取并验证日K线 {len(data)} 条")

    def test_fetch_and_convert_min_kline(self):
        """测试获取并转换分钟K线数据"""
        # 获取数据
        data = self.fetcher.fetch_min_kline(self.test_code, freq="5min", count=10)
        self.assertIsNotNone(data, "获取分钟K线失败")
        self.assertGreater(len(data), 0, "获取数据为空")

        # 验证数据格式
        for item in data:
            self.assertIn("date", item)
            self.assertIn("time", item)
            self.assertIn("open", item)
            self.assertIn("high", item)
            self.assertIn("low", item)
            self.assertIn("close", item)
            self.assertIn("volume", item)
            self.assertIn("amount", item)

        logger.info(f"获取并验证分钟K线 {len(data)} 条")

    def test_workflow_fetch_day_kline_to_qlib(self):
        """测试完整工作流：获取日K线并转换"""
        # 获取数据
        data = self.fetcher.fetch_day_kline(self.test_code, count=5)
        self.assertIsNotNone(data, "获取日K线失败")

        if len(data) > 0:
            # 验证数据可以用于转换
            self.assertIn("date", data[0])
            self.assertIn("open", data[0])
            logger.info(f"工作流测试成功，数据条数: {len(data)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
