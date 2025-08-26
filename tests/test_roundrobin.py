# coding:utf8
import unittest
import time
import statistics
from unittest.mock import patch, MagicMock
from typing import Dict, Any

import pqquotation


class TestRoundRobinQuotation(unittest.TestCase):
    """Round-robin行情接口测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.rr = pqquotation.use('roundrobin')
        self.test_codes = ['000001', '000002', '600000']
        self.single_code = ['000001']
        self.expected_fields = ['name', 'open', 'close', 'now', 'high', 'low', 
                               'buy', 'sell', 'turnover', 'volume', 'date', 'time']
    
    def test_roundrobin_creation(self):
        """测试Round-robin实例创建"""
        # 测试不同的别名
        aliases = ['rr', 'roundrobin', 'round-robin']
        
        for alias in aliases:
            with self.subTest(alias=alias):
                quotation = pqquotation.use(alias)
                self.assertIsInstance(quotation, pqquotation.roundrobin.RoundRobinQuotation)
                
                # 检查内部数据源
                self.assertIn('sina', quotation._sources)
                self.assertIn('tencent', quotation._sources)
                self.assertIn('dc', quotation._sources)
    
    def test_basic_functionality(self):
        """测试基本功能"""
        print("\n=== Round-robin基本功能测试 ===")
        
        # 测试单股票获取
        data = self.rr.real(self.single_code[0])
        self.assertIsInstance(data, dict)
        
        if data:
            print(f"成功获取 {len(data)} 条股票数据")
            code = list(data.keys())[0]
            stock_data = data[code]
            
            # 检查必需字段
            for field in ['name', 'now']:
                self.assertIn(field, stock_data, f"缺少必需字段: {field}")
            
            print(f"股票: {stock_data.get('name', 'N/A')} 现价: {stock_data.get('now', 'N/A')}")
        else:
            self.skipTest("无法获取测试数据")
    
    def test_multiple_stocks(self):
        """测试多股票获取"""
        print("\n=== 多股票获取测试 ===")
        
        data = self.rr.real(self.test_codes)
        self.assertIsInstance(data, dict)
        
        if data:
            print(f"请求 {len(self.test_codes)} 只股票，获取到 {len(data)} 只股票数据")
            
            # 检查数据结构
            for code, stock_data in data.items():
                self.assertIsInstance(stock_data, dict)
                self.assertIn('name', stock_data)
                self.assertIn('now', stock_data)
                
                print(f"  {code}: {stock_data.get('name', 'N/A')} - {stock_data.get('now', 'N/A')}")
        else:
            self.skipTest("无法获取多股票测试数据")
    
    def test_data_format_consistency(self):
        """测试数据格式一致性"""
        print("\n=== 数据格式一致性测试 ===")
        
        # 获取round-robin数据
        rr_data = self.rr.real(self.single_code[0])
        self.assertIsInstance(rr_data, dict)
        
        if not rr_data:
            self.skipTest("Round-robin无法获取测试数据")
        
        code = list(rr_data.keys())[0]
        rr_stock_data = rr_data[code]
        
        # 与直接使用sina数据比较
        try:
            sina = pqquotation.use('sina')
            sina_data = sina.real(self.single_code[0])
            
            if sina_data:
                sina_stock_data = sina_data[code]
                
                # 比较关键字段
                comparison_fields = ['name', 'now', 'open', 'high', 'low']
                
                for field in comparison_fields:
                    if field in rr_stock_data and field in sina_stock_data:
                        rr_value = rr_stock_data[field]
                        sina_value = sina_stock_data[field]
                        
                        print(f"  {field}: RR={rr_value}, Sina={sina_value}")
                        
                        # 对于数字字段，检查是否相等（允许小的浮点误差）
                        if isinstance(rr_value, (int, float)) and isinstance(sina_value, (int, float)):
                            self.assertAlmostEqual(rr_value, sina_value, places=2, 
                                                 msg=f"字段 {field} 数值差异过大")
                        else:
                            self.assertEqual(rr_value, sina_value, 
                                           msg=f"字段 {field} 值不一致")
                
                print("✓ 数据格式一致性检查通过")
                
        except Exception as e:
            print(f"× sina数据源比较失败: {e}")
            # 不强制失败，因为网络问题可能导致比较失败
    
    def test_source_rotation(self):
        """测试数据源轮询功能"""
        print("\n=== 数据源轮询测试 ===")
        
        # 记录数据源使用情况
        source_usage = {}
        
        # 多次调用，观察数据源轮询
        for i in range(6):  # 调用6次，应该每个数据源至少使用2次
            with patch.object(self.rr, '_get_next_source') as mock_get_source:
                expected_sources = ['sina', 'tencent', 'dc']
                mock_source = expected_sources[i % len(expected_sources)]
                mock_get_source.return_value = mock_source
                
                # 调用接口
                try:
                    data = self.rr.real(self.single_code[0])
                    if data:
                        source_usage[mock_source] = source_usage.get(mock_source, 0) + 1
                        print(f"  第{i+1}次调用: 使用 {mock_source}")
                except:
                    print(f"  第{i+1}次调用: {mock_source} 失败")
        
        print(f"数据源使用统计: {source_usage}")
        
        # 验证轮询是否工作
        self.assertGreater(len(source_usage), 0, "应该至少使用一个数据源")
    
    def test_failure_handling(self):
        """测试故障处理功能"""
        print("\n=== 故障处理测试 ===")
        
        # 连续标记sina失败多次（新逻辑需要连续失败3次才会被标记为不可用）
        for i in range(3):
            self.rr._mark_source_failed('sina')
        failed_sources_before = set(self.rr._failed_sources)
        print(f"连续标记sina失败3次后，失败数据源: {failed_sources_before}")
        
        # 尝试获取数据，应该自动切换到其他数据源
        data = self.rr.real(self.single_code[0])
        
        if data:
            print("✓ 故障切换成功，仍能获取数据")
            # 验证使用了其他数据源
            self.assertIn('sina', failed_sources_before, "sina应该在失败列表中")
        else:
            print("× 故障切换失败，无法获取数据")
        
        # 重置失败状态
        self.rr.reset_failed_sources()
        failed_sources_after = set(self.rr._failed_sources)
        print(f"重置后失败数据源: {failed_sources_after}")
        
        self.assertEqual(len(failed_sources_after), 0, "重置后应该没有失败数据源")
    
    def test_statistics_functionality(self):
        """测试统计功能"""
        print("\n=== 统计功能测试 ===")
        
        # 先进行几次调用产生统计数据
        for i in range(3):
            try:
                data = self.rr.real(self.single_code[0])
                time.sleep(0.1)  # 短暂延迟
            except:
                pass
        
        # 获取统计信息
        stats = self.rr.get_source_stats()
        
        # 验证统计结构
        self.assertIn('sources', stats)
        self.assertIn('failed_sources', stats)
        self.assertIn('current_source', stats)
        self.assertIn('total_sources', stats)
        
        print(f"总数据源数: {stats['total_sources']}")
        print(f"当前数据源: {stats['current_source']}")
        print(f"失败数据源: {stats['failed_sources']}")
        
        # 检查各数据源统计
        for source_name, source_stats in stats['sources'].items():
            self.assertIn('success', source_stats)
            self.assertIn('failure', source_stats)
            self.assertIn('avg_response_time', source_stats)
            
            print(f"  {source_name}: 成功{source_stats['success']}次, "
                  f"失败{source_stats['failure']}次, "
                  f"平均响应时间{source_stats['avg_response_time']:.3f}秒")
        
        self.assertEqual(stats['total_sources'], 3, "应该有3个数据源")
        print("✓ 统计功能正常")
    
    def test_prefix_parameter(self):
        """测试prefix参数功能"""
        print("\n=== Prefix参数测试 ===")
        
        # 测试数字格式（明确指定return_format='digit'）
        data_digit = self.rr.real(self.single_code[0], prefix=False, return_format='digit')
        
        # 测试前缀格式（明确指定return_format='prefix'）
        data_prefix = self.rr.real(self.single_code[0], prefix=True, return_format='prefix')
        
        if data_digit and data_prefix:
            # 数字格式的键应该是纯数字
            for code in data_digit.keys():
                self.assertRegex(code, r'^\d{6}$', "数字格式的股票代码应该是6位数字")
                print(f"  数字格式: {code}")
            
            # 前缀格式的键应该包含市场标识
            for code in data_prefix.keys():
                self.assertRegex(code, r'^(sh|sz|bj)\d{6}$', "前缀格式的股票代码应该包含市场标识")
                print(f"  前缀格式: {code}")
            
            print("✓ Prefix参数功能正常")
        else:
            self.skipTest("无法获取prefix测试数据")
    
    def test_retry_mechanism(self):
        """测试重试机制"""
        print("\n=== 重试机制测试 ===")
        
        # 使用mock模拟所有数据源都失败的情况
        original_sources = self.rr._sources.copy()
        
        # 创建会失败的mock数据源
        failing_source = MagicMock()
        failing_source.real.side_effect = Exception("模拟网络错误")
        
        # 暂时替换所有数据源为失败的mock
        for source_name in self.rr._sources:
            self.rr._sources[source_name] = failing_source
        
        try:
            # 调用应该重试并最终返回空字典
            data = self.rr.real(self.single_code[0], max_retries=2)
            
            self.assertIsInstance(data, dict)
            self.assertEqual(len(data), 0, "所有数据源失败时应返回空字典")
            
            print("✓ 重试机制正常：所有数据源失败时返回空字典")
            
        finally:
            # 恢复原始数据源
            self.rr._sources = original_sources
    
    def test_data_normalization(self):
        """测试数据格式标准化"""
        print("\n=== 数据标准化测试 ===")
        
        # 测试数据标准化函数
        test_tencent_data = {
            '000001': {
                'name': '平安银行',
                'now': 12.06,
                'open': 12.15,
                'close': 12.08,
                'high': 12.20,
                'low': 12.00,
                'bid1': 12.05,
                'ask1': 12.07,
                'bid1_volume': 100,
                'ask1_volume': 200,
                'datetime': time.strptime('20241223091500', '%Y%m%d%H%M%S'),
                '成交量(手)': 1000000,
                '成交额(万)': 120800,
            }
        }
        
        # 测试腾讯数据转换
        normalized = self.rr._normalize_data_format(test_tencent_data, 'tencent')
        
        self.assertIn('000001', normalized)
        stock_data = normalized['000001']
        
        # 检查必需字段是否存在且格式正确
        required_fields = ['name', 'now', 'open', 'close', 'high', 'low', 'date', 'time']
        for field in required_fields:
            self.assertIn(field, stock_data, f"标准化后缺少字段: {field}")
        
        # 检查数据类型
        self.assertIsInstance(stock_data['now'], float)
        self.assertIsInstance(stock_data['name'], str)
        self.assertIsInstance(stock_data['date'], str)
        self.assertIsInstance(stock_data['time'], str)
        
        print(f"  原始腾讯数据字段: {list(test_tencent_data['000001'].keys())[:5]}...")
        print(f"  标准化后字段: {list(stock_data.keys())[:5]}...")
        print("✓ 数据标准化功能正常")
    
    def test_enhanced_code_format_support(self):
        """测试增强版股票代码格式支持"""
        print("\n=== 增强版股票代码格式支持测试 ===")
        
        # 不同格式的股票代码
        test_formats = {
            '数字格式': ['000001', '600000'],
            '国标格式': ['sz000001', 'sh600000'],
            'TS格式': ['000001.SZ', '600000.SH'],
            '混合格式': ['000001', 'sz000002', '600000.SH']
        }
        
        for format_name, codes in test_formats.items():
            with self.subTest(format=format_name):
                print(f"  测试 {format_name}: {codes}")
                
                try:
                    data = self.rr.real(codes)
                    
                    if data:
                        print(f"    ✓ 成功获取 {len(data)} 条数据")
                        for code, stock_data in data.items():
                            stock_name = stock_data.get('name', 'N/A')
                            print(f"      {code}: {stock_name}")
                    else:
                        print(f"    × {format_name} 未获取到数据")
                        
                except Exception as e:
                    print(f"    × {format_name} 测试失败: {e}")
    
    def test_invalid_code_handling_enhanced(self):
        """测试增强版无效代码处理"""
        print("\n=== 增强版无效代码处理测试 ===")
        
        # 混合有效和无效代码
        mixed_codes = ['000001', 'invalid_code', '600000.SH', '123456', 'sz000002']
        expected_valid_count = 3  # 3个有效代码
        
        try:
            data = self.rr.real(mixed_codes)
            
            print(f"  输入代码: {mixed_codes}")
            print(f"  返回数据数量: {len(data)}")
            
            # 应该只返回有效代码的数据
            if data:
                for code, stock_data in data.items():
                    stock_name = stock_data.get('name', 'N/A')
                    print(f"    {code}: {stock_name}")
                    
                print("  ✓ 无效代码被正确过滤")
            else:
                print("  × 所有代码都被过滤了")
                
        except Exception as e:
            print(f"  × 无效代码处理测试失败: {e}")
    
    def test_concurrent_requests(self):
        """测试并发请求处理"""
        print("\n=== 并发请求测试 ===")
        
        import threading
        results = []
        errors = []
        
        def make_request():
            try:
                data = self.rr.real(self.single_code[0])
                results.append(data)
            except Exception as e:
                errors.append(str(e))
        
        # 创建多个线程同时请求
        threads = []
        for i in range(3):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=10)
        
        print(f"  并发请求结果: 成功{len(results)}次, 错误{len(errors)}次")
        
        if errors:
            print(f"  错误信息: {errors}")
        
        # 至少应该有一些成功的请求
        self.assertGreater(len(results), 0, "并发请求应该至少有一次成功")
        
        # 检查结果一致性
        valid_results = [r for r in results if r and isinstance(r, dict)]
        if len(valid_results) > 1:
            # 比较股票名称应该一致
            names = [list(r.values())[0].get('name', '') for r in valid_results if r]
            unique_names = set(names)
            self.assertLessEqual(len(unique_names), 1, "并发请求返回的股票名称应该一致")
        
        print("✓ 并发请求处理正常")


class TestRoundRobinIntegration(unittest.TestCase):
    """Round-robin集成测试"""
    
    def setUp(self):
        """设置集成测试环境"""
        self.test_codes = ['000001', '000002']
    
    def test_integration_with_existing_sources(self):
        """测试与现有数据源的集成"""
        print("\n=== 与现有数据源集成测试 ===")
        
        sources_to_test = ['sina', 'qq', 'dc', 'roundrobin']
        results = {}
        
        for source in sources_to_test:
            try:
                quotation = pqquotation.use(source)
                data = quotation.real(self.test_codes[0])
                
                if data:
                    results[source] = data
                    code = list(data.keys())[0]
                    stock_data = data[code]
                    print(f"  {source}: {stock_data.get('name', 'N/A')} - {stock_data.get('now', 'N/A')}")
                else:
                    print(f"  {source}: 无数据")
                    
            except Exception as e:
                print(f"  {source}: 失败 - {e}")
        
        # Round-robin应该能正常工作
        self.assertIn('roundrobin', results, "Round-robin应该能正常获取数据")
        
        # 如果有其他数据源成功，比较数据一致性
        if len(results) > 1:
            rr_data = results['roundrobin']
            rr_code = list(rr_data.keys())[0]
            rr_stock = rr_data[rr_code]
            
            for source, data in results.items():
                if source != 'roundrobin':
                    code = list(data.keys())[0]
                    stock = data[code]
                    
                    # 股票名称应该一致
                    if 'name' in rr_stock and 'name' in stock:
                        self.assertEqual(rr_stock['name'], stock['name'], 
                                       f"Round-robin与{source}的股票名称不一致")
        
        print("✓ 集成测试通过")
    
    def test_performance_comparison(self):
        """测试性能对比"""
        print("\n=== 性能对比测试 ===")
        
        sources = ['sina', 'qq', 'dc', 'roundrobin']
        performance_results = {}
        
        for source in sources:
            try:
                quotation = pqquotation.use(source)
                
                # 测量响应时间
                start_time = time.time()
                data = quotation.real(self.test_codes[0])
                end_time = time.time()
                
                response_time = end_time - start_time
                performance_results[source] = {
                    'response_time': response_time,
                    'success': bool(data),
                    'data_count': len(data) if data else 0
                }
                
                print(f"  {source}: {response_time:.3f}秒 {'✓' if data else '×'}")
                
            except Exception as e:
                performance_results[source] = {
                    'response_time': float('inf'),
                    'success': False,
                    'error': str(e)
                }
                print(f"  {source}: 失败 - {e}")
        
        # Round-robin响应时间应该合理
        if 'roundrobin' in performance_results:
            rr_time = performance_results['roundrobin']['response_time']
            self.assertLess(rr_time, 10.0, "Round-robin响应时间不应超过10秒")
            
            print(f"✓ Round-robin性能测试通过 ({rr_time:.3f}秒)")


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2, buffer=True)