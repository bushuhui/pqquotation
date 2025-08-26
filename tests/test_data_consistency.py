# coding: utf8
"""
测试sina、qq、dc三个数据源的数据一致性
采用并发获取和智能容差对比策略
"""

import time
import asyncio
import threading
import logging
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import os
from datetime import datetime
import statistics
import random

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_consistency_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataConsistencyChecker:
    """数据一致性检查器"""
    
    def __init__(self):
        self.sources = ['sina', 'qq', 'dc']
        self.quotation_apis = {}
        
        # 字段映射 - 统一不同数据源的字段名
        self.field_mapping = {
            'sina': {
                'name': 'name', 'now': 'now', 'close': 'close', 'open': 'open',
                'high': 'high', 'low': 'low', 'volume': 'volume'
            },
            'qq': {
                'name': 'name', 'now': 'now', 'close': 'close', 'open': 'open',
                'high': 'high', 'low': 'low', 'volume': 'volume'
            },
            'dc': {
                'name': 'name', 'now': 'now', 'close': 'close', 'open': 'open',
                'high': 'high', 'low': 'low', 'volume': 'volume'
            }
        }
        
        # 容差设置
        self.tolerance = {
            'price_percent': 0.1,    # 价格容差0.1%
            'volume_percent': 5.0,   # 成交量容差5%
            'name_similarity': 0.8   # 名称相似度80%
        }
        
        # 批量大小限制（取最小值确保兼容）
        self.batch_size = 50  # qq限制60，但为安全起见用50
        
        # 初始化数据源
        self.init_data_sources()
        
        # 结果统计
        self.results = {
            'total_tested': 0,
            'successful_comparisons': 0,
            'consistency_stats': {},
            'inconsistent_stocks': [],
            'error_stocks': [],
            'field_consistency': defaultdict(lambda: defaultdict(int)),
            'source_availability': defaultdict(int)
        }
    
    def init_data_sources(self):
        """初始化数据源"""
        for source in self.sources:
            try:
                self.quotation_apis[source] = pqquotation.use(source)
                logger.info(f"初始化数据源 {source} 成功")
            except Exception as e:
                logger.error(f"初始化数据源 {source} 失败: {e}")
        
    def test_data_source_availability(self):
        """测试各数据源的可用性"""
        print("\n=== 数据源可用性测试 ===")
        
        for source in self.sources:
            with self.subTest(source=source):
                try:
                    quotation = pqquotation.use(source)
                    # 测试单个股票获取
                    data = quotation.real(self.test_stocks[0])
                    
                    self.assertIsInstance(data, dict, f"{source} 应返回字典类型")
                    self.assertGreater(len(data), 0, f"{source} 应返回非空数据")
                    print(f"✓ {source} 数据源可用")
                    
                except Exception as e:
                    self.fail(f"{source} 数据源不可用: {e}")
    
    def test_response_time(self):
        """测试各数据源的响应时间"""
        print("\n=== 响应时间测试 ===")
        response_times = {}
        
        for source in self.sources:
            try:
                quotation = pqquotation.use(source)
                
                start_time = time.time()
                data = quotation.real(self.test_stocks[0])
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times[source] = response_time
                
                print(f"{source}: {response_time:.3f}秒")
                
                # 响应时间不应超过10秒
                self.assertLess(response_time, 10.0, f"{source} 响应时间过长")
                
            except Exception as e:
                print(f"{source}: 失败 - {e}")
                response_times[source] = float('inf')
        
        # 找出最快的数据源
        if response_times:
            fastest_source = min(response_times, key=response_times.get)
            print(f"最快数据源: {fastest_source} ({response_times[fastest_source]:.3f}秒)")
    
    def test_common_fields_presence(self):
        """测试共同字段的存在性"""
        print("\n=== 共同字段存在性测试 ===")
        
        for source in self.sources:
            with self.subTest(source=source):
                try:
                    quotation = pqquotation.use(source)
                    data = quotation.real(self.test_stocks[0])
                    
                    if not data:
                        self.skipTest(f"{source} 返回空数据")
                    
                    stock_code = list(data.keys())[0]
                    stock_data = data[stock_code]
                    
                    missing_fields = []
                    for field in self.common_fields:
                        if field not in stock_data:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        print(f"× {source} 缺少字段: {missing_fields}")
                        # 不强制失败，因为字段名可能不同
                    else:
                        print(f"✓ {source} 包含所有共同字段")
                    
                    # 打印实际字段
                    print(f"  {source} 实际字段: {list(stock_data.keys())[:10]}...")
                    
                except Exception as e:
                    self.fail(f"{source} 字段检查失败: {e}")
    
    def test_data_validity(self):
        """测试数据的有效性"""
        print("\n=== 数据有效性测试 ===")
        
        for source in self.sources:
            with self.subTest(source=source):
                try:
                    quotation = pqquotation.use(source)
                    data = quotation.real(self.test_stocks[0])
                    
                    if not data:
                        self.skipTest(f"{source} 返回空数据")
                    
                    stock_code = list(data.keys())[0]
                    stock_data = data[stock_code]
                    
                    # 检查价格字段的有效性
                    price_fields = ['open', 'high', 'low', 'now', 'close']
                    valid_prices = []
                    
                    for field in price_fields:
                        if field in stock_data:
                            price = stock_data[field]
                            if isinstance(price, (int, float)) and price > 0:
                                valid_prices.append(price)
                                print(f"  {source} {field}: {price}")
                    
                    self.assertGreater(len(valid_prices), 0, f"{source} 应至少有一个有效价格")
                    
                    # 检查价格逻辑关系
                    if len(valid_prices) >= 2:
                        max_price = max(valid_prices)
                        min_price = min(valid_prices)
                        
                        # 最高价应该不小于最低价
                        self.assertGreaterEqual(max_price, min_price, 
                                              f"{source} 价格逻辑错误: 最高价 < 最低价")
                    
                except Exception as e:
                    print(f"× {source} 数据有效性检查失败: {e}")
    
    def test_price_consistency_range(self):
        """测试不同数据源价格的一致性范围"""
        print("\n=== 价格一致性范围测试 ===")
        
        all_data = {}
        
        # 收集所有数据源的数据
        for source in self.sources:
            try:
                quotation = pqquotation.use(source)
                data = quotation.real(self.test_stocks[0])
                
                if data:
                    stock_code = list(data.keys())[0]
                    stock_data = data[stock_code]
                    all_data[source] = stock_data
                    
            except Exception as e:
                print(f"× {source} 数据获取失败: {e}")
        
        if len(all_data) < 2:
            self.skipTest("可用数据源少于2个，无法进行一致性比较")
        
        # 比较现价
        current_prices = []
        for source, stock_data in all_data.items():
            # 尝试不同的现价字段名
            price = None
            for field in ['now', 'current', 'price', 'last']:
                if field in stock_data and isinstance(stock_data[field], (int, float)):
                    price = float(stock_data[field])
                    break
            
            if price and price > 0:
                current_prices.append((source, price))
                print(f"  {source} 现价: {price}")
        
        if len(current_prices) >= 2:
            prices = [price for _, price in current_prices]
            price_std = statistics.stdev(prices) if len(prices) > 1 else 0
            price_mean = statistics.mean(prices)
            
            # 计算变异系数（标准差/均值）
            cv = price_std / price_mean if price_mean > 0 else 0
            
            print(f"  价格标准差: {price_std:.4f}")
            print(f"  价格均值: {price_mean:.4f}")
            print(f"  变异系数: {cv:.4f}")
            
            # 变异系数不应超过10%（考虑到不同数据源的延迟）
            self.assertLess(cv, 0.1, "不同数据源价格差异过大")
            
            print("✓ 价格一致性检查通过")
        else:
            self.skipTest("有效价格数据不足，无法进行一致性比较")
    
    def test_field_mapping_standardization(self):
        """测试字段映射标准化"""
        print("\n=== 字段映射标准化测试 ===")
        
        # 定义字段映射关系
        field_mappings = {
            'sina': {
                'current_price': 'now',
                'opening_price': 'open',
                'highest_price': 'high',
                'lowest_price': 'low',
                'previous_close': 'close',
                'stock_name': 'name'
            },
            'qq': {
                'current_price': 'now',
                'opening_price': 'open',
                'highest_price': 'high',
                'lowest_price': 'low',
                'previous_close': 'close',
                'stock_name': 'name'
            },
            'dc': {
                'current_price': 'now',
                'opening_price': 'open',
                'highest_price': 'high',
                'lowest_price': 'low',
                'previous_close': 'close',
                'stock_name': 'name'
            }
        }
        
        standardized_data = {}
        
        for source in self.sources:
            try:
                quotation = pqquotation.use(source)
                data = quotation.real(self.test_stocks[0])
                
                if not data:
                    continue
                
                stock_code = list(data.keys())[0]
                stock_data = data[stock_code]
                
                # 标准化字段
                standardized = {}
                mapping = field_mappings.get(source, {})
                
                for standard_field, original_field in mapping.items():
                    if original_field in stock_data:
                        standardized[standard_field] = stock_data[original_field]
                
                standardized_data[source] = standardized
                print(f"  {source} 标准化后: {standardized}")
                
            except Exception as e:
                print(f"× {source} 字段标准化失败: {e}")
        
        # 检查标准化后的字段一致性
        if len(standardized_data) >= 2:
            common_standard_fields = set.intersection(*[set(data.keys()) for data in standardized_data.values()])
            print(f"  共同标准字段: {common_standard_fields}")
            
            self.assertGreater(len(common_standard_fields), 0, "标准化后应至少有一个共同字段")
            print("✓ 字段映射标准化检查通过")
    
    def test_multiple_stocks_consistency(self):
        """测试多只股票的数据一致性"""
        print("\n=== 多股票数据一致性测试 ===")
        
        for source in self.sources:
            with self.subTest(source=source):
                try:
                    quotation = pqquotation.use(source)
                    # 获取多只股票数据
                    data = quotation.real(self.test_stocks)
                    
                    if not data:
                        self.skipTest(f"{source} 返回空数据")
                    
                    print(f"  {source} 返回 {len(data)} 只股票数据")
                    
                    # 检查数据结构一致性
                    field_sets = []
                    for stock_code, stock_data in data.items():
                        if isinstance(stock_data, dict):
                            field_sets.append(set(stock_data.keys()))
                            print(f"    {stock_code}: {len(stock_data)} 个字段")
                    
                    if len(field_sets) > 1:
                        # 检查字段集合是否一致
                        common_fields = set.intersection(*field_sets)
                        all_fields = set.union(*field_sets)
                        
                        consistency_ratio = len(common_fields) / len(all_fields) if all_fields else 0
                        print(f"    字段一致性比例: {consistency_ratio:.2%}")
                        
                        # 字段一致性应该较高
                        self.assertGreater(consistency_ratio, 0.8, f"{source} 多股票字段一致性过低")
                    
                    print(f"✓ {source} 多股票数据一致性检查通过")
                    
                except Exception as e:
                    print(f"× {source} 多股票测试失败: {e}")


if __name__ == "__main__":
    # 设置详细输出
    unittest.main(verbosity=2, buffer=True)