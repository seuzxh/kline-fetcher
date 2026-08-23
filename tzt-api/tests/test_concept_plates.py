#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
概念板块功能完整测试文件
使用 unittest 框架测试 ConceptPlateFetcher 类中的概念板块相关功能

v2.1.0 起，概念板块方法已从 KLineFetcher 剥离到 ConceptPlateFetcher。
本测试为集成测试（需真实 API），默认不运行，手动触发：
    pytest tests/test_concept_plates.py -m integration
"""

import sys
import os

# 添加项目根目录到路径，使测试文件能找到 kline_fetcher 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import logging
import pytest
from tzt_api import ConceptPlateFetcher

# 标记为集成测试：默认跳过，仅在设置 KLINE_API_BASE_URL 且显式 -m integration 时运行
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("KLINE_API_BASE_URL"),
        reason="需要设置 KLINE_API_BASE_URL 环境变量才能运行集成测试",
    ),
]

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestConceptPlates(unittest.TestCase):
    """概念板块功能测试类"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化，在所有测试方法执行前运行一次"""
        logger.info("=== 初始化概念板块测试 ===")
        cls.fetcher = ConceptPlateFetcher()
        # 保存测试用的概念板块代码和股票代码
        cls.test_plate_code = "994612"  # 示例概念板块代码
        cls.test_stock_code = "600519"  # 示例股票代码（贵州茅台）
        cls.test_stock_market = 1  # 市场代码（1表示上海）

    def setUp(self):
        """每个测试方法执行前运行"""
        logger.info(f"\n--- 开始测试: {self._testMethodName} ---")

    def tearDown(self):
        """每个测试方法执行后运行"""
        logger.info(f"--- 测试完成: {self._testMethodName} ---\n")

    def test_01_get_all_concept_plates(self):
        """
        测试 get_all_concept_plates 方法
        验证：
        1. 返回值不为 None
        2. 返回值是非空列表
        3. 每个板块包含必填字段（code, name, market）
        """
        logger.info("测试获取所有概念板块列表")
        
        # 调用方法
        plates = self.fetcher.get_all_concept_plates()
        
        # 验证返回值不为 None
        self.assertIsNotNone(plates, "获取概念板块失败，返回 None")
        
        # 验证返回值是列表类型
        self.assertIsInstance(plates, list, "返回值不是列表类型")
        
        # 验证列表不为空
        self.assertGreater(len(plates), 0, "概念板块列表为空")
        
        # 验证每个板块包含必填字段
        required_fields = ["code", "name", "market"]
        for i, plate in enumerate(plates[:5]):  # 只检查前5个板块
            with self.subTest(plate_index=i):
                for field in required_fields:
                    self.assertIn(field, plate, f"板块缺少必填字段: {field}")
                    self.assertIsNotNone(plate[field], f"字段 {field} 的值为 None")
        
        logger.info(f"成功获取 {len(plates)} 个概念板块")
        logger.info(f"第一个板块: {plates[0]}")

    def test_02_get_concept_plate_kline(self):
        """
        测试 get_concept_plate_kline 方法
        验证：
        1. 返回值不为 None
        2. 返回值是非空列表
        3. 每条K线数据包含完整字段
        """
        logger.info(f"测试获取概念板块 {self.test_plate_code} 的K线数据")
        
        # 调用方法
        kline_data = self.fetcher.get_concept_plate_kline(self.test_plate_code)
        
        # 验证返回值不为 None
        self.assertIsNotNone(kline_data, "获取概念板块K线失败，返回 None")
        
        # 验证返回值是列表类型
        self.assertIsInstance(kline_data, list, "返回值不是列表类型")
        
        # 验证列表不为空
        self.assertGreater(len(kline_data), 0, "K线数据列表为空")
        
        # 验证每条K线包含必填字段
        required_fields = ["date", "open", "high", "low", "close", "volume", "amount"]
        for i, kline in enumerate(kline_data[:5]):  # 只检查前5条K线
            with self.subTest(kline_index=i):
                for field in required_fields:
                    self.assertIn(field, kline, f"K线缺少必填字段: {field}")
                    self.assertIsNotNone(kline[field], f"字段 {field} 的值为 None")
        
        logger.info(f"成功获取 {len(kline_data)} 条K线数据")
        logger.info(f"最新K线: {kline_data[0]}")

    def test_03_get_concept_plate_stocks(self):
        """
        测试 get_concept_plate_stocks 方法
        验证：
        1. 返回值不为 None
        2. 返回值是非空列表
        3. 每只股票包含必填字段（code, name, market）
        """
        logger.info(f"测试获取概念板块 {self.test_plate_code} 的成份股")
        
        # 调用方法
        stocks = self.fetcher.get_concept_plate_stocks(self.test_plate_code)
        
        # 验证返回值不为 None
        self.assertIsNotNone(stocks, "获取概念板块成份股失败，返回 None")
        
        # 验证返回值是列表类型
        self.assertIsInstance(stocks, list, "返回值不是列表类型")
        
        # 验证列表不为空
        self.assertGreater(len(stocks), 0, "成份股列表为空")
        
        # 验证每只股票包含必填字段
        required_fields = ["code", "name", "market"]
        for i, stock in enumerate(stocks[:5]):  # 只检查前5只股票
            with self.subTest(stock_index=i):
                for field in required_fields:
                    self.assertIn(field, stock, f"股票缺少必填字段: {field}")
                    self.assertIsNotNone(stock[field], f"字段 {field} 的值为 None")
        
        logger.info(f"成功获取 {len(stocks)} 只成份股")
        logger.info(f"第一只股票: {stocks[0]}")

    def test_04_get_stock_concept_plates(self):
        """
        测试 get_stock_concept_plates 方法（v2.1.2 重写：基于官方属性 901 CoBlkIdx）
        验证：
        1. 返回值不为 None 且是非空列表
        2. 每个板块包含必填字段（code, name, market, type）
        3. plate_type 过滤生效
        """
        logger.info(f"测试获取股票 {self.test_stock_code} 所属的概念板块")

        # 调用方法
        plates = self.fetcher.get_stock_concept_plates(
            self.test_stock_code,
            self.test_stock_market
        )

        # 验证返回值不为 None
        self.assertIsNotNone(plates, "获取股票所属概念板块失败，返回 None")

        # 验证返回值是列表类型且非空（贵州茅台必有所属板块）
        self.assertIsInstance(plates, list, "返回值不是列表类型")
        self.assertGreater(len(plates), 0, "板块列表为空")

        # 验证每个板块包含必填字段
        required_fields = ["code", "name", "market", "type"]
        for i, plate in enumerate(plates[:5]):  # 只检查前5个板块
            with self.subTest(plate_index=i):
                for field in required_fields:
                    self.assertIn(field, plate, f"板块缺少必填字段: {field}")
                    self.assertIsNotNone(plate[field], f"字段 {field} 的值为 None")
                self.assertIn(plate["type"], ("industry", "region", "concept"))

        # 验证 plate_type 过滤
        concepts = self.fetcher.get_stock_concept_plates(
            self.test_stock_code,
            self.test_stock_market,
            plate_type="concept"
        )
        self.assertIsNotNone(concepts)
        self.assertGreater(len(concepts), 0, "概念板块过滤结果为空")
        for plate in concepts:
            self.assertEqual(plate["type"], "concept")

        logger.info(f"成功获取 {len(plates)} 个板块（其中概念 {len(concepts)} 个）")
        logger.info(f"前几个板块: {plates[:3]}")

    def test_05_get_concept_plate_kline_custom_count(self):
        """
        测试 get_concept_plate_kline 方法的自定义数量参数
        验证：
        1. 可以指定获取特定数量的K线数据
        """
        logger.info(f"测试获取概念板块 {self.test_plate_code} 的自定义数量K线数据")
        
        # 测试获取较少数量的K线
        test_count = -10
        kline_data = self.fetcher.get_concept_plate_kline(
            self.test_plate_code,
            count=test_count
        )
        
        # 验证返回值不为 None
        self.assertIsNotNone(kline_data, "获取概念板块K线失败，返回 None")
        
        # 验证返回的K线数量不超过请求的数量（考虑API返回的可能限制）
        self.assertLessEqual(len(kline_data), abs(test_count) + 10, f"获取的K线数量过多")
        
        logger.info(f"成功获取 {len(kline_data)} 条K线数据（请求 {abs(test_count)} 条）")

    def test_06_get_concept_plate_stocks_pagination(self):
        """
        测试 get_concept_plate_stocks 方法的分页功能
        验证：
        1. 可以通过 start 和 count 参数进行分页获取
        """
        logger.info(f"测试获取概念板块 {self.test_plate_code} 的分页成份股")
        
        # 测试第一页
        stocks_page1 = self.fetcher.get_concept_plate_stocks(
            self.test_plate_code,
            start=0,
            count=5
        )
        
        # 验证第一页数据
        self.assertIsNotNone(stocks_page1, "获取第一页成份股失败，返回 None")
        self.assertGreater(len(stocks_page1), 0, "第一页成份股列表为空")
        
        # 测试第二页
        stocks_page2 = self.fetcher.get_concept_plate_stocks(
            self.test_plate_code,
            start=5,
            count=5
        )
        
        # 验证第二页数据
        self.assertIsNotNone(stocks_page2, "获取第二页成份股失败，返回 None")
        
        logger.info(f"第一页: {len(stocks_page1)} 只股票")
        logger.info(f"第二页: {len(stocks_page2)} 只股票")


if __name__ == "__main__":
    # 运行所有测试
    unittest.main(verbosity=2)
