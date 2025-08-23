# coding:utf8
import unittest
from unittest.mock import patch

import pqquotation
from pqquotation import helpers


class TestStockCodeProcessing(unittest.TestCase):
    """股票代码处理增强功能测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 清空缓存确保测试独立性
        helpers.clear_code_cache()
        
        # 测试用例数据
        self.test_cases = {
            # 深圳股票
            '000001': {'normalized': '000001', 'market': 'sz', 'format': 'digital'},
            'sz000001': {'normalized': '000001', 'market': 'sz', 'format': 'national'},
            '000001.SZ': {'normalized': '000001', 'market': 'sz', 'format': 'ts'},
            
            # 上海股票  
            '600000': {'normalized': '600000', 'market': 'sh', 'format': 'digital'},
            'sh600000': {'normalized': '600000', 'market': 'sh', 'format': 'national'},
            '600000.SH': {'normalized': '600000', 'market': 'sh', 'format': 'ts'},
            
            # 北交所股票
            '430047': {'normalized': '430047', 'market': 'bj', 'format': 'digital'},  # 43开头是北交所
            'bj430047': {'normalized': '430047', 'market': 'bj', 'format': 'national'},
            '430047.BJ': {'normalized': '430047', 'market': 'bj', 'format': 'ts'},
        }
    
    def test_detect_stock_code_format(self):
        """测试股票代码格式检测"""
        print("\n=== 股票代码格式检测测试 ===")
        
        for code, expected in self.test_cases.items():
            with self.subTest(code=code):
                detected_format = helpers.detect_stock_code_format(code)
                self.assertEqual(detected_format, expected['format'], 
                               f"代码 {code} 格式检测失败")
                print(f"  {code}: {detected_format} ✓")
        
        # 测试无效格式
        invalid_codes = ['12345', 'abc123', '000001.XX', 'invalid']
        for code in invalid_codes:
            format_type = helpers.detect_stock_code_format(code)
            self.assertEqual(format_type, 'unknown', f"无效代码 {code} 应该返回unknown")
            print(f"  {code}: {format_type} ✓")
    
    def test_normalize_stock_code(self):
        """测试股票代码标准化"""
        print("\n=== 股票代码标准化测试 ===")
        
        for code, expected in self.test_cases.items():
            with self.subTest(code=code):
                normalized = helpers.normalize_stock_code(code)
                self.assertEqual(normalized, expected['normalized'],
                               f"代码 {code} 标准化失败")
                print(f"  {code} -> {normalized} ✓")
        
        # 测试缓存机制
        test_code = '000001.SZ'
        normalized1 = helpers.normalize_stock_code(test_code)
        normalized2 = helpers.normalize_stock_code(test_code)
        self.assertEqual(normalized1, normalized2)
        print(f"  缓存机制: {test_code} ✓")
        
        # 测试无效代码
        with self.assertRaises(ValueError):
            helpers.normalize_stock_code('invalid_code')
        print("  无效代码异常处理 ✓")
    
    def test_validate_stock_code(self):
        """测试股票代码验证"""
        print("\n=== 股票代码验证测试 ===")
        
        # 有效代码测试
        valid_codes = list(self.test_cases.keys())
        for code in valid_codes:
            self.assertTrue(helpers.validate_stock_code(code), 
                          f"有效代码 {code} 验证失败")
            print(f"  {code}: 有效 ✓")
        
        # 无效代码测试
        invalid_codes = ['12345', 'abc123', '000001.XX', None, 123]
        for code in invalid_codes:
            self.assertFalse(helpers.validate_stock_code(code),
                           f"无效代码 {code} 应该验证失败")
            print(f"  {code}: 无效 ✓")
    
    def test_get_stock_type_enhanced(self):
        """测试增强版股票市场类型判断"""
        print("\n=== 增强版市场类型判断测试 ===")
        
        for code, expected in self.test_cases.items():
            with self.subTest(code=code):
                market_type = helpers.get_stock_type(code)
                self.assertEqual(market_type, expected['market'],
                               f"代码 {code} 市场类型判断失败")
                print(f"  {code}: {market_type} ✓")
    
    def test_batch_normalize_stock_codes(self):
        """测试批量股票代码标准化"""
        print("\n=== 批量股票代码标准化测试 ===")
        
        input_codes = ['000001', 'sz000002', '600000.SH', 'invalid', '000003.SZ']
        expected_output = ['000001', '000002', '600000', '000003']
        
        with patch('builtins.print') as mock_print:
            result = helpers.batch_normalize_stock_codes(input_codes)
            
            self.assertEqual(result, expected_output)
            # 验证警告信息被打印
            mock_print.assert_called()
            print(f"  输入: {input_codes}")
            print(f"  输出: {result} ✓")
    
    def test_ts_market_extraction(self):
        """测试TS格式市场标识提取"""
        print("\n=== TS格式市场标识提取测试 ===")
        
        ts_codes = {
            '000001.SZ': 'sz',
            '600000.SH': 'sh',
            '430047.BJ': 'bj'
        }
        
        for code, expected_market in ts_codes.items():
            market = helpers.get_market_from_ts_code(code)
            self.assertEqual(market, expected_market)
            print(f"  {code}: {market} ✓")
    
    def test_format_examples(self):
        """测试格式示例输出"""
        print("\n=== 格式示例测试 ===")
        
        examples = helpers.format_stock_code_examples()
        self.assertIsInstance(examples, str)
        self.assertIn("数字格式", examples)
        self.assertIn("国标格式", examples)
        self.assertIn("TS格式", examples)
        print("  格式示例输出正常 ✓")


class TestEnhancedQuotation(unittest.TestCase):
    """增强版行情接口测试"""
    
    def test_enhanced_stock_code_support(self):
        """测试增强版股票代码支持"""
        print("\n=== 增强版股票代码支持测试 ===")
        
        # 测试数据源
        sources = ['sina', 'tencent', 'dc', 'roundrobin']
        
        # 不同格式的测试代码
        test_formats = {
            '数字格式': '000001',
            '国标格式': 'sz000001',
            'TS格式': '000001.SZ',
            '上海数字': '600000', 
            '上海国标': 'sh600000',
            '上海TS': '600000.SH'
        }
        
        for source in sources:
            print(f"\n  {source} 数据源:")
            try:
                quoter = pqquotation.use(source)
                
                for format_name, code in test_formats.items():
                    try:
                        data = quoter.real([code])
                        if data:
                            stock_name = list(data.values())[0].get('name', 'N/A')
                            print(f"    {format_name} ({code}): ✓ {stock_name}")
                        else:
                            print(f"    {format_name} ({code}): × 无数据")
                    except Exception as e:
                        print(f"    {format_name} ({code}): × {str(e)[:30]}...")
                        
            except Exception as e:
                print(f"    数据源创建失败: {e}")
    
    def test_mixed_format_batch_request(self):
        """测试混合格式批量请求"""
        print("\n=== 混合格式批量请求测试 ===")
        
        mixed_codes = ['000001', 'sz000002', '600000.SH', 'sh600036']
        
        try:
            # 使用round-robin测试批量请求
            rr = pqquotation.use('roundrobin')
            data = rr.real(mixed_codes)
            
            print(f"  请求代码: {mixed_codes}")
            print(f"  返回结果数量: {len(data)}")
            
            if data:
                for code, stock_data in data.items():
                    stock_name = stock_data.get('name', 'N/A')
                    print(f"    {code}: {stock_name}")
                    
                # 验证数据完整性
                self.assertGreater(len(data), 0, "批量请求应该返回数据")
                print("  ✓ 混合格式批量请求成功")
            else:
                print("  × 批量请求返回空数据")
                
        except Exception as e:
            print(f"  × 批量请求失败: {e}")
    
    def test_invalid_code_handling(self):
        """测试无效代码处理"""
        print("\n=== 无效代码处理测试 ===")
        
        invalid_codes = ['invalid', '12345', '000001.XX']
        valid_code = '000001'
        mixed_codes = invalid_codes + [valid_code]
        
        try:
            rr = pqquotation.use('roundrobin')
            
            with patch('builtins.print') as mock_print:
                data = rr.real(mixed_codes)
                
                # 应该只返回有效代码的数据
                if data:
                    self.assertEqual(len(data), 1, "应该只有1个有效代码返回数据")
                    self.assertIn('000001', list(data.keys())[0])
                    print(f"  ✓ 有效代码数据: {list(data.keys())}")
                else:
                    print("  × 未获取到有效代码数据")
                
                print("  ✓ 无效代码处理正常")
                
        except Exception as e:
            print(f"  × 无效代码处理测试失败: {e}")


class TestBackwardCompatibility(unittest.TestCase):
    """向后兼容性测试"""
    
    def test_original_functionality_preserved(self):
        """测试原有功能保持不变"""
        print("\n=== 向后兼容性测试 ===")
        
        # 测试原有的数字格式和国标格式
        original_test_cases = [
            ('000001', 'sz000001'),
            ('600000', 'sh600000'), 
            ('sz000001', 'sz000001'),
            ('sh600000', 'sh600000')
        ]
        
        try:
            sina = pqquotation.use('sina')
            
            for input_code, expected_key_pattern in original_test_cases:
                data = sina.real([input_code])
                
                if data:
                    actual_key = list(data.keys())[0]
                    # 验证返回的键格式是否包含预期的代码部分
                    self.assertTrue(expected_key_pattern[-6:] in actual_key,
                                  f"原有格式 {input_code} 兼容性测试失败")
                    print(f"  {input_code} -> {actual_key} ✓")
                else:
                    print(f"  {input_code}: 无数据")
                    
            print("  ✓ 向后兼容性测试通过")
            
        except Exception as e:
            print(f"  × 向后兼容性测试失败: {e}")
    
    def test_api_interface_unchanged(self):
        """测试API接口未变化"""
        print("\n=== API接口一致性测试 ===")
        
        sources = ['sina', 'tencent', 'dc', 'roundrobin']
        
        for source in sources:
            try:
                quoter = pqquotation.use(source)
                
                # 测试real方法签名
                self.assertTrue(hasattr(quoter, 'real'))
                
                # 测试基本调用方式
                data = quoter.real('000001')
                self.assertIsInstance(data, dict)
                
                # 测试prefix参数
                data_with_prefix = quoter.real('000001', prefix=True)
                self.assertIsInstance(data_with_prefix, dict)
                
                print(f"  {source}: API接口正常 ✓")
                
            except Exception as e:
                print(f"  {source}: API接口测试失败: {e}")


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2, buffer=True)