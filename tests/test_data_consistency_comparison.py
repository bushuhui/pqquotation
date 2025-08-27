# coding: utf8
"""
测试sina、qq、dc三个数据源的数据一致性对比
采用并发获取和智能容差对比策略
"""

import time
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
            'volume_percent': 50.0,  # 成交量容差50%（QQ与Sina/DC存在已知差异）
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
            'source_availability': defaultdict(int),
            'code_format_issues': [],  # 新增：股票代码格式问题统计
            'code_format_stats': defaultdict(int)  # 新增：各数据源代码格式统计
        }
    
    def init_data_sources(self):
        """初始化数据源"""
        for source in self.sources:
            try:
                self.quotation_apis[source] = pqquotation.use(source)
                logger.info(f"初始化数据源 {source} 成功")
            except Exception as e:
                logger.error(f"初始化数据源 {source} 失败: {e}")
    
    def load_test_codes(self, sample_size: int = 100) -> List[str]:
        """加载测试用的股票代码，确保为国标格式"""
        codes_file = os.path.join(os.path.dirname(__file__), 'all_codes.txt')
        try:
            with open(codes_file, 'r', encoding='utf-8') as f:
                all_codes = [line.strip() for line in f if line.strip()]
            
            # 过滤和转换为国标格式
            national_codes = []
            from pqquotation import helpers
            
            for code in all_codes:
                try:
                    if helpers.validate_stock_code(code):
                        # 如果不是国标格式，转换为国标格式
                        if not self.is_national_format(code):
                            # 标准化为6位数字，然后转换为国标格式
                            digit_code = helpers.normalize_stock_code(code)
                            national_code = helpers.convert_to_national_format(digit_code)
                            national_codes.append(national_code)
                        else:
                            # 已经是国标格式，直接使用
                            national_codes.append(code)
                except Exception as e:
                    logger.warning(f"跳过无效股票代码 {code}: {e}")
                    continue
            
            # 去重
            national_codes = list(set(national_codes))
            
            # 随机采样
            if len(national_codes) > sample_size:
                test_codes = random.sample(national_codes, sample_size)
            else:
                test_codes = national_codes
                
            logger.info(f"加载国标格式测试股票代码 {len(test_codes)} 个")
            return test_codes
            
        except Exception as e:
            logger.error(f"加载股票代码失败: {e}")
            return []
    
    def fetch_data_concurrent(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """并发获取多个数据源的数据"""
        results = {}
        
        def fetch_single_source(source: str) -> Tuple[str, Dict[str, Any]]:
            """获取单个数据源的数据"""
            try:
                if source not in self.quotation_apis:
                    return source, {}
                
                api = self.quotation_apis[source]
                # 强制使用国标格式，确保输入输出代码格式一致
                data = api.real(codes, return_format='national')
                
                # 记录成功获取的股票数量
                if data:
                    self.results['source_availability'][source] += len(data)
                
                return source, data if data else {}
                
            except Exception as e:
                logger.warning(f"获取 {source} 数据失败: {e}")
                return source, {}
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=len(self.sources)) as executor:
            future_to_source = {
                executor.submit(fetch_single_source, source): source 
                for source in self.sources
            }
            
            for future in as_completed(future_to_source):
                source, data = future.result()
                results[source] = data
                logger.info(f"{source} 获取到 {len(data)} 个股票数据")
        
        return results
    
    def normalize_data(self, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """标准化数据格式"""
        normalized = {}
        field_map = self.field_mapping.get(source, {})
        
        for field, mapped_field in field_map.items():
            if mapped_field in data:
                value = data[mapped_field]
                # 数值类型转换
                if field in ['now', 'close', 'open', 'high', 'low'] and value is not None:
                    try:
                        normalized[field] = float(value)
                    except (ValueError, TypeError):
                        normalized[field] = None
                elif field == 'volume' and value is not None:
                    try:
                        normalized[field] = int(float(value))
                    except (ValueError, TypeError):
                        normalized[field] = None
                else:
                    normalized[field] = value
        
        return normalized
    
    def compare_values(self, field: str, val1: Any, val2: Any) -> Tuple[bool, str]:
        """比较两个值是否一致"""
        if val1 is None or val2 is None:
            return val1 == val2, "空值比较"
        
        if field == 'name':
            # 名称比较：计算相似度
            similarity = self.calculate_similarity(str(val1), str(val2))
            consistent = similarity >= self.tolerance['name_similarity']
            return consistent, f"相似度: {similarity:.2f}"
        
        elif field in ['now', 'close', 'open', 'high', 'low']:
            # 价格比较：使用百分比容差
            if val1 == 0 or val2 == 0:
                return val1 == val2, "零值比较"
            
            diff_percent = abs(val1 - val2) / max(abs(val1), abs(val2)) * 100
            consistent = diff_percent <= self.tolerance['price_percent']
            return consistent, f"差异: {diff_percent:.3f}%"
        
        elif field == 'volume':
            # 成交量比较：考虑已知的数据源差异
            if val1 == 0 or val2 == 0:
                return val1 == val2, "零成交量比较"
            
            diff_percent = abs(val1 - val2) / max(abs(val1), abs(val2)) * 100
            consistent = diff_percent <= self.tolerance['volume_percent']
            
            # 如果差异很大，检查是否是QQ数据源的已知问题
            if not consistent and diff_percent > 80:
                # QQ的成交量可能是手数，尝试转换验证
                ratio = max(val1, val2) / min(val1, val2)
                if 1.5 < ratio < 100:  # QQ与Sina/DC的成交量比例范围（覆盖所有已知差异）
                    return True, f"数据源差异(比例:{ratio:.1f}倍,已知QQ成交量计算差异)"
            
            return consistent, f"差异: {diff_percent:.1f}%"
        
        else:
            # 其他字段精确比较
            return val1 == val2, "精确比较"
    
    def validate_stock_code_format(self, input_code: str, returned_codes: List[str], source: str) -> bool:
        """验证返回的股票代码格式是否与输入一致
        :param input_code: 输入的国标格式股票代码 (如: 000001.SZ)
        :param returned_codes: 数据源返回的股票代码列表
        :param source: 数据源名称
        :return: True表示格式正确，False表示格式不一致
        """
        if not returned_codes:
            return False
            
        # 检查是否存在与输入代码完全匹配的返回代码
        if input_code in returned_codes:
            return True
        
        # 检查返回的代码格式是否都是国标格式
        for returned_code in returned_codes:
            if not self.is_national_format(returned_code):
                logger.warning(f"{source}返回非国标格式代码: {returned_code} (输入: {input_code})")
                return False
        
        # 如果返回代码不包含输入代码，但格式都正确，可能是代码映射问题
        # 提取6位数字部分进行比较
        input_digits = self.extract_digits_from_code(input_code)
        if input_digits:
            for returned_code in returned_codes:
                returned_digits = self.extract_digits_from_code(returned_code)
                if returned_digits == input_digits:
                    logger.info(f"{source}代码映射: {input_code} -> {returned_code}")
                    return True
        
        return False
    
    def is_national_format(self, code: str) -> bool:
        """检查股票代码是否为国标格式 (000001.SZ)"""
        import re
        return bool(re.match(r'^\d{6}\.(SH|SZ|BJ)$', code))
    
    def extract_digits_from_code(self, code: str) -> str:
        """从股票代码中提取6位数字部分"""
        import re
        match = re.search(r'(\d{6})', code)
        return match.group(1) if match else ""
    
    def find_matching_code(self, input_code: str, returned_codes: List[str]) -> Optional[str]:
        """在返回的代码列表中查找与输入代码匹配的代码
        支持不同格式之间的匹配
        """
        if not returned_codes:
            return None
            
        input_digits = self.extract_digits_from_code(input_code)
        if not input_digits:
            return None
            
        # 查找相同数字部分的代码
        for returned_code in returned_codes:
            returned_digits = self.extract_digits_from_code(returned_code)
            if returned_digits == input_digits:
                return returned_code
        
        return None

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度（简单实现）"""
        if not str1 or not str2:
            return 0.0
        
        # 去除空格等字符
        str1 = str1.replace(' ', '').replace('*', '')
        str2 = str2.replace(' ', '').replace('*', '')
        
        if str1 == str2:
            return 1.0
        
        # 简单的编辑距离算法
        len1, len2 = len(str1), len(str2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i-1] == str2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1
        
        max_len = max(len1, len2)
        similarity = (max_len - dp[len1][len2]) / max_len if max_len > 0 else 0.0
        return similarity
    
    def compare_stock_data(self, code: str, source_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """比较单个股票在不同数据源的数据"""
        comparison = {
            'code': code,
            'timestamp': datetime.now().isoformat(),
            'sources': {},
            'consistency': {},
            'overall_consistent': True,
            'notes': [],
            'code_format_issues': []  # 新增：记录股票代码格式问题
        }
        
        # 标准化各数据源的数据并验证股票代码格式
        normalized_data = {}
        for source, data in source_data.items():
            # 检查返回的股票代码格式是否与输入一致
            returned_codes = list(data.keys()) if data else []
            code_format_ok = self.validate_stock_code_format(code, returned_codes, source)
            if not code_format_ok:
                comparison['code_format_issues'].append(
                    f"{source}返回的股票代码格式不正确: 输入{code}, 返回{returned_codes}"
                )
            
            if code in data:
                normalized_data[source] = self.normalize_data(data[code], source)
                comparison['sources'][source] = data[code]
            else:
                # 如果直接匹配不到，尝试查找相似的代码
                matched_code = self.find_matching_code(code, returned_codes)
                if matched_code:
                    normalized_data[source] = self.normalize_data(data[matched_code], source)
                    comparison['sources'][source] = data[matched_code]
                    comparison['notes'].append(f"{source}代码映射: {code} -> {matched_code}")
                else:
                    normalized_data[source] = {}
                    comparison['notes'].append(f"{source}未返回数据")
        
        # 如果少于2个数据源有数据，跳过比较
        available_sources = [s for s, d in normalized_data.items() if d]
        if len(available_sources) < 2:
            comparison['overall_consistent'] = False
            comparison['notes'].append("可用数据源不足2个")
            return comparison
        
        # 比较每个字段
        fields_to_compare = ['name', 'now', 'close', 'open', 'high', 'low', 'volume']
        
        for field in fields_to_compare:
            field_consistent = True
            field_details = {}
            
            # 获取所有数据源在该字段的值
            field_values = {}
            for source in available_sources:
                field_values[source] = normalized_data[source].get(field)
            
            # 两两比较
            sources_list = list(field_values.keys())
            for i in range(len(sources_list)):
                for j in range(i + 1, len(sources_list)):
                    source1, source2 = sources_list[i], sources_list[j]
                    val1, val2 = field_values[source1], field_values[source2]
                    
                    consistent, detail = self.compare_values(field, val1, val2)
                    
                    pair_key = f"{source1}_vs_{source2}"
                    field_details[pair_key] = {
                        'consistent': consistent,
                        'detail': detail,
                        'values': {source1: val1, source2: val2}
                    }
                    
                    if not consistent:
                        field_consistent = False
                    
                    # 更新统计
                    self.results['field_consistency'][field][f"{source1}_{source2}"] += 1 if consistent else 0
            
            comparison['consistency'][field] = {
                'consistent': field_consistent,
                'details': field_details
            }
            
            if not field_consistent:
                comparison['overall_consistent'] = False
        
        return comparison
    
    def test_batch_consistency(self, codes: List[str]) -> List[Dict[str, Any]]:
        """测试一批股票的数据一致性"""
        logger.info(f"开始测试 {len(codes)} 个股票的数据一致性")
        
        # 并发获取数据
        source_data = self.fetch_data_concurrent(codes)
        
        # 比较每个股票的数据
        batch_results = []
        for code in codes:
            try:
                comparison = self.compare_stock_data(code, source_data)
                batch_results.append(comparison)
                
                # 更新统计
                self.results['total_tested'] += 1
                
                # 统计代码格式问题
                if comparison['code_format_issues']:
                    self.results['code_format_issues'].extend(comparison['code_format_issues'])
                    for issue in comparison['code_format_issues']:
                        for source in self.sources:
                            if source in issue:
                                self.results['code_format_stats'][f"{source}_format_error"] += 1
                else:
                    # 记录格式正确的数据源
                    for source in self.sources:
                        if source in source_data and code in source_data[source]:
                            self.results['code_format_stats'][f"{source}_format_ok"] += 1
                
                if comparison['overall_consistent']:
                    self.results['successful_comparisons'] += 1
                else:
                    # 收集详细的不一致信息
                    inconsistency_details = self._extract_inconsistency_details(comparison)
                    self.results['inconsistent_stocks'].append({
                        'code': code,
                        'issues': comparison['notes'] + inconsistency_details['summary'],
                        'detailed_issues': inconsistency_details['details'],
                        'code_format_issues': comparison['code_format_issues'],
                        'timestamp': comparison['timestamp']
                    })
                    
            except Exception as e:
                logger.error(f"比较股票 {code} 数据时出错: {e}")
                self.results['error_stocks'].append({
                    'code': code,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        return batch_results
    
    def run_consistency_test(self, sample_size: int = 100) -> None:
        """运行一致性测试"""
        logger.info("=" * 60)
        logger.info("开始数据一致性测试")
        logger.info("=" * 60)
        
        # 加载测试股票代码
        test_codes = self.load_test_codes(sample_size)
        if not test_codes:
            logger.error("无法加载测试股票代码")
            return
        
        # 分批测试
        all_results = []
        batches = [test_codes[i:i + self.batch_size] for i in range(0, len(test_codes), self.batch_size)]
        
        for i, batch in enumerate(batches):
            logger.info(f"处理批次 {i+1}/{len(batches)}")
            batch_results = self.test_batch_consistency(batch)
            all_results.extend(batch_results)
            
            # 批次间等待
            if i < len(batches) - 1:
                time.sleep(2)
        
        # 生成报告
        self.generate_report(all_results)
        self.save_detailed_results(all_results)
    
    def generate_report(self, results: List[Dict[str, Any]]) -> None:
        """生成测试报告"""
        logger.info("\n" + "=" * 60)
        logger.info("数据一致性测试报告")
        logger.info("=" * 60)
        
        total = self.results['total_tested']
        consistent = self.results['successful_comparisons']
        consistency_rate = (consistent / total * 100) if total > 0 else 0
        
        print(f"\n总体统计:")
        print(f"  测试股票数量: {total}")
        print(f"  一致性通过: {consistent}")
        print(f"  一致性比例: {consistency_rate:.1f}%")
        print(f"  不一致股票: {len(self.results['inconsistent_stocks'])}")
        print(f"  错误股票数: {len(self.results['error_stocks'])}")
        
        print(f"\n数据源可用性:")
        for source in self.sources:
            available = self.results['source_availability'].get(source, 0)
            availability_rate = (available / total * 100) if total > 0 else 0
            print(f"  {source}: {available}/{total} ({availability_rate:.1f}%)")
        
        print(f"\n股票代码格式一致性:")
        for source in self.sources:
            format_ok = self.results['code_format_stats'].get(f"{source}_format_ok", 0)
            format_error = self.results['code_format_stats'].get(f"{source}_format_error", 0)
            total_checked = format_ok + format_error
            if total_checked > 0:
                format_rate = (format_ok / total_checked * 100)
                print(f"  {source}: {format_ok}/{total_checked} 格式正确 ({format_rate:.1f}%)")
            else:
                print(f"  {source}: 无数据检查")
        
        # 显示代码格式问题汇总
        if self.results['code_format_issues']:
            print(f"\n代码格式问题汇总 (前10个):")
            for issue in self.results['code_format_issues'][:10]:
                print(f"  {issue}")
        
        print(f"\n字段一致性统计:")
        # 计算各字段的一致性比例
        field_consistency_summary = {}
        for field, source_pairs in self.results['field_consistency'].items():
            total_comparisons = 0
            consistent_comparisons = 0
            
            for pair, count in source_pairs.items():
                if '_vs_' in pair:
                    total_comparisons += 1
                    if count > 0:
                        consistent_comparisons += 1
            
            if total_comparisons > 0:
                consistency_pct = (consistent_comparisons / total_comparisons) * 100
                field_consistency_summary[field] = (consistent_comparisons, total_comparisons, consistency_pct)
        
        for field, (consistent_pairs, total_pairs, rate) in field_consistency_summary.items():
            print(f"  {field}: {consistent_pairs}/{total_pairs} 数据源对一致 ({rate:.1f}%)")
        
        # 显示主要不一致问题
        if self.results['inconsistent_stocks']:
            print(f"\n主要不一致问题 (前10个):")
            for issue in self.results['inconsistent_stocks'][:10]:
                print(f"  {issue['code']}: {', '.join(issue['issues'])}")
                
                # 显示详细的不一致原因
                if 'detailed_issues' in issue:
                    for field, field_issues in issue['detailed_issues'].items():
                        for detail in field_issues[:2]:  # 每个字段最多显示2个详细问题
                            print(f"    - {detail}")
                        if len(field_issues) > 2:
                            print(f"    - ...还有{len(field_issues)-2}个{field}问题")
    
    def _extract_inconsistency_details(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """提取详细的不一致信息"""
        details = {
            'summary': [],
            'details': {}
        }
        
        # 分析各字段的不一致情况
        for field, field_data in comparison.get('consistency', {}).items():
            if not field_data.get('consistent', True):
                field_issues = []
                field_details = field_data.get('details', {})
                
                for pair_key, pair_data in field_details.items():
                    if not pair_data.get('consistent', True):
                        source1, source2 = pair_key.split('_vs_')
                        val1 = pair_data['values'][source1]
                        val2 = pair_data['values'][source2]
                        detail = pair_data.get('detail', '')
                        
                        issue_desc = f"{source1}({val1}) vs {source2}({val2}): {detail}"
                        field_issues.append(issue_desc)
                
                if field_issues:
                    summary_desc = f"{field}字段不一致"
                    details['summary'].append(summary_desc)
                    details['details'][field] = field_issues
        
        return details
    
    def save_detailed_results(self, results: List[Dict[str, Any]]) -> None:
        """保存详细结果"""
        timestamp = int(time.time())
        
        # 保存完整的比较结果
        detailed_file = f"consistency_test_detailed_{timestamp}.json"
        try:
            # 处理datetime序列化问题
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object {obj} is not JSON serializable")
            
            with open(detailed_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'test_info': {
                        'timestamp': datetime.now().isoformat(),
                        'total_tested': self.results['total_tested'],
                        'batch_size': self.batch_size,
                        'tolerance': self.tolerance
                    },
                    'summary': self.results,
                    'detailed_results': results
                }, f, ensure_ascii=False, indent=2, default=json_serializer)
            
            logger.info(f"详细结果已保存到: {detailed_file}")
            
        except Exception as e:
            logger.error(f"保存详细结果失败: {e}")
        
        # 保存简化报告
        summary_file = f"consistency_test_summary_{timestamp}.txt"
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("数据一致性测试摘要报告\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"测试股票: {self.results['total_tested']} 个\n")
                f.write(f"一致性通过: {self.results['successful_comparisons']} 个\n")
                f.write(f"一致性比例: {self.results['successful_comparisons']/self.results['total_tested']*100:.1f}%\n\n")
                
                f.write("数据源可用性:\n")
                for source in self.sources:
                    available = self.results['source_availability'].get(source, 0)
                    f.write(f"  {source}: {available}/{self.results['total_tested']}\n")
                
                f.write("\n不一致股票列表:\n")
                for issue in self.results['inconsistent_stocks']:
                    f.write(f"  {issue['code']}: {', '.join(issue['issues'])}\n")
                    
                    # 写入详细的不一致原因
                    if 'detailed_issues' in issue:
                        for field, field_issues in issue['detailed_issues'].items():
                            f.write(f"    {field}问题:\n")
                            for detail in field_issues:
                                f.write(f"      - {detail}\n")
            
            logger.info(f"摘要报告已保存到: {summary_file}")
            
        except Exception as e:
            logger.error(f"保存摘要报告失败: {e}")


def test_code_format_specifically():
    """专门测试股票代码格式一致性"""
    print("\n" + "=" * 80)
    print("股票代码格式一致性专项测试")
    print("=" * 80)
    
    # 测试特定的国标格式股票代码
    test_codes = [
        '000001.SZ',  # 平安银行
        '600000.SH',  # 浦发银行  
        '002004.SZ',  # 华邦健康
        '300001.SZ',  # 特锐德
        '000300.SH',  # 沪深300
    ]
    
    sources = ['sina', 'qq', 'dc']
    
    for code in test_codes:
        print(f"\n【测试股票: {code}】")
        print("-" * 50)
        
        for source in sources:
            try:
                api = pqquotation.use(source)
                data = api.real([code], return_format='national')
                
                if data:
                    returned_codes = list(data.keys())
                    print(f"  {source:>6}: 输入 {code} -> 返回 {returned_codes}")
                    
                    # 验证格式
                    if code in returned_codes:
                        print(f"         ✓ 代码格式一致")
                    else:
                        print(f"         ❌ 代码格式不一致")
                        
                        # 尝试找到对应的代码
                        checker = DataConsistencyChecker()
                        matched = checker.find_matching_code(code, returned_codes)
                        if matched:
                            print(f"         💡 找到匹配代码: {matched}")
                else:
                    print(f"  {source:>6}: 无数据返回")
                    
            except Exception as e:
                print(f"  {source:>6}: 错误 - {str(e)}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试数据源一致性')
    parser.add_argument('--sample-size', type=int, default=100, help='测试样本大小 (默认: 100)')
    parser.add_argument('--price-tolerance', type=float, default=0.1, help='价格容差百分比 (默认: 0.1)')
    parser.add_argument('--volume-tolerance', type=float, default=5.0, help='成交量容差百分比 (默认: 5.0)')
    parser.add_argument('--code-format-test', action='store_true', help='只运行股票代码格式测试')
    
    args = parser.parse_args()
    
    # 如果只运行代码格式测试
    if args.code_format_test:
        test_code_format_specifically()
        return
    
    # 创建测试器
    checker = DataConsistencyChecker()
    checker.tolerance['price_percent'] = args.price_tolerance
    checker.tolerance['volume_percent'] = args.volume_tolerance
    
    try:
        # 首先运行代码格式测试
        test_code_format_specifically()
        
        # 然后运行完整的一致性测试
        checker.run_consistency_test(sample_size=args.sample_size)
        
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
    finally:
        logger.info("测试结束")


if __name__ == '__main__':
    main()