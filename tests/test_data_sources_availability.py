# coding: utf8
"""
测试sina、qq、dc三个数据源对股票代码的可访问性
采用分组、采样、重试策略避免被屏蔽
"""

import time
import random
import logging
from typing import List, Dict, Set, Optional
from collections import defaultdict, Counter
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_source_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataSourceTester:
    """数据源可用性测试器"""
    
    def __init__(self, codes_file: str = 'all_codes.txt'):
        self.codes_file = codes_file
        self.sources = ['sina', 'qq', 'dc']
        self.batch_size = 50  # 每批测试50个股票
        self.batch_interval = 2  # 批次间隔2秒
        self.max_retries = 3  # 最大重试次数
        self.sample_size = 200  # 每个市场采样数量
        
        # 初始化数据源
        self.quotation_apis = {}
        for source in self.sources:
            try:
                self.quotation_apis[source] = pqquotation.use(source)
                logger.info(f"初始化数据源 {source} 成功")
            except Exception as e:
                logger.error(f"初始化数据源 {source} 失败: {e}")
                
        # 测试结果统计
        self.results = {
            source: {
                'success': 0,
                'failed': 0,
                'error_codes': set(),
                'success_codes': set(),
                'errors': defaultdict(int)
            } for source in self.sources
        }
    
    def load_stock_codes(self) -> List[str]:
        """加载股票代码"""
        codes_path = os.path.join(os.path.dirname(__file__), self.codes_file)
        try:
            with open(codes_path, 'r', encoding='utf-8') as f:
                codes = [line.strip() for line in f if line.strip()]
            logger.info(f"加载股票代码 {len(codes)} 个")
            return codes
        except FileNotFoundError:
            logger.error(f"找不到股票代码文件: {codes_path}")
            return []
        except Exception as e:
            logger.error(f"加载股票代码失败: {e}")
            return []
    
    def sample_codes(self, all_codes: List[str]) -> List[str]:
        """采样股票代码，避免全量测试"""
        if len(all_codes) <= self.sample_size * 2:
            return all_codes
            
        # 按市场分类
        sz_codes = [code for code in all_codes if code.endswith('.SZ')]
        sh_codes = [code for code in all_codes if code.endswith('.SH')]
        
        # 每个市场采样
        sampled_codes = []
        if sz_codes:
            sampled_codes.extend(random.sample(sz_codes, min(self.sample_size, len(sz_codes))))
        if sh_codes:
            sampled_codes.extend(random.sample(sh_codes, min(self.sample_size, len(sh_codes))))
            
        # 随机打乱顺序
        random.shuffle(sampled_codes)
        logger.info(f"采样股票代码 {len(sampled_codes)} 个 (SZ: {len([c for c in sampled_codes if c.endswith('.SZ')])}, SH: {len([c for c in sampled_codes if c.endswith('.SH')])})")
        return sampled_codes
    
    def test_batch(self, source: str, codes: List[str], retry_count: int = 0) -> Dict[str, any]:
        """测试一批股票代码"""
        if source not in self.quotation_apis:
            return {'success': False, 'error': f'数据源 {source} 未初始化'}
            
        try:
            api = self.quotation_apis[source]
            # 获取行情数据
            data = api.stocks(codes)
            
            success_codes = set()
            failed_codes = set()
            
            # 检查每个股票的数据
            for code in codes:
                if code in data and data[code] and 'name' in data[code]:
                    # 检查关键字段是否有效
                    stock_data = data[code]
                    if (stock_data.get('name') and 
                        stock_data.get('now') is not None and 
                        stock_data.get('now') > 0):
                        success_codes.add(code)
                    else:
                        failed_codes.add(code)
                else:
                    failed_codes.add(code)
            
            return {
                'success': True,
                'success_codes': success_codes,
                'failed_codes': failed_codes,
                'total_returned': len(data) if data else 0
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"数据源 {source} 测试批次失败 (第{retry_count+1}次): {error_msg}")
            
            # 如果还有重试机会，等待后重试
            if retry_count < self.max_retries - 1:
                time.sleep(min(5 * (retry_count + 1), 15))  # 指数退避
                return self.test_batch(source, codes, retry_count + 1)
            
            return {
                'success': False,
                'error': error_msg,
                'failed_codes': set(codes)
            }
    
    def test_source(self, source: str, codes: List[str]) -> None:
        """测试单个数据源"""
        logger.info(f"开始测试数据源: {source}")
        
        # 分批测试
        batches = [codes[i:i + self.batch_size] for i in range(0, len(codes), self.batch_size)]
        
        for i, batch in enumerate(batches):
            logger.info(f"测试 {source} - 批次 {i+1}/{len(batches)} ({len(batch)}个股票)")
            
            result = self.test_batch(source, batch)
            
            if result.get('success'):
                success_codes = result.get('success_codes', set())
                failed_codes = result.get('failed_codes', set())
                
                self.results[source]['success'] += len(success_codes)
                self.results[source]['failed'] += len(failed_codes)
                self.results[source]['success_codes'].update(success_codes)
                self.results[source]['error_codes'].update(failed_codes)
                
                logger.info(f"{source} 批次 {i+1}: 成功 {len(success_codes)}, 失败 {len(failed_codes)}")
            else:
                error = result.get('error', '未知错误')
                failed_codes = result.get('failed_codes', set())
                
                self.results[source]['failed'] += len(failed_codes)
                self.results[source]['error_codes'].update(failed_codes)
                self.results[source]['errors'][error] += 1
                
                logger.error(f"{source} 批次 {i+1} 完全失败: {error}")
            
            # 批次间等待，避免被屏蔽
            if i < len(batches) - 1:
                time.sleep(self.batch_interval)
        
        logger.info(f"数据源 {source} 测试完成")
    
    def run_test(self, full_test: bool = False) -> None:
        """运行完整测试"""
        logger.info("=" * 60)
        logger.info("开始数据源可用性测试")
        logger.info("=" * 60)
        
        # 加载股票代码
        all_codes = self.load_stock_codes()
        if not all_codes:
            logger.error("无法加载股票代码，测试终止")
            return
        
        # 选择测试代码
        if full_test:
            test_codes = all_codes
            logger.info(f"全量测试模式: {len(test_codes)} 个股票代码")
        else:
            test_codes = self.sample_codes(all_codes)
            logger.info(f"采样测试模式: {len(test_codes)} 个股票代码")
        
        if not test_codes:
            logger.error("没有可测试的股票代码")
            return
        
        # 测试各数据源
        for source in self.sources:
            if source in self.quotation_apis:
                self.test_source(source, test_codes)
            else:
                logger.warning(f"跳过数据源 {source} (初始化失败)")
        
        # 输出测试结果
        self.print_summary(len(test_codes))
        self.save_detailed_results()
    
    def print_summary(self, total_tested: int) -> None:
        """打印测试摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("测试结果摘要")
        logger.info("=" * 60)
        
        print(f"\n{'数据源':<10} {'成功数':<8} {'失败数':<8} {'成功率':<10} {'状态'}")
        print("-" * 50)
        
        for source in self.sources:
            if source in self.results:
                result = self.results[source]
                success = result['success']
                failed = result['failed']
                success_rate = (success / (success + failed) * 100) if (success + failed) > 0 else 0
                
                status = "正常" if success_rate >= 80 else "异常" if success_rate >= 50 else "不可用"
                
                print(f"{source:<10} {success:<8} {failed:<8} {success_rate:<9.1f}% {status}")
                
                # 显示主要错误
                if result['errors']:
                    most_common_error = Counter(result['errors']).most_common(1)[0]
                    print(f"           主要错误: {most_common_error[0]} ({most_common_error[1]}次)")
        
        print()
        
        # 交集分析
        if len(self.sources) > 1:
            logger.info("数据源可用性交集分析:")
            success_sets = {source: self.results[source]['success_codes'] 
                           for source in self.sources if source in self.results}
            
            if len(success_sets) >= 2:
                all_sources_success = set.intersection(*success_sets.values())
                print(f"所有数据源都能获取的股票: {len(all_sources_success)} 个")
                
                for source in self.sources:
                    if source in success_sets:
                        unique_codes = success_sets[source] - set.union(*[s for k, s in success_sets.items() if k != source])
                        print(f"{source} 独有可获取股票: {len(unique_codes)} 个")
    
    def save_detailed_results(self) -> None:
        """保存详细测试结果"""
        filename = f"data_source_test_results_{int(time.time())}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("数据源可用性测试详细结果\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"测试配置: 批次大小={self.batch_size}, 批次间隔={self.batch_interval}秒, 最大重试={self.max_retries}次\n\n")
                
                for source in self.sources:
                    if source in self.results:
                        result = self.results[source]
                        f.write(f"数据源: {source}\n")
                        f.write(f"成功: {result['success']} 个\n")
                        f.write(f"失败: {result['failed']} 个\n")
                        
                        if result['errors']:
                            f.write("错误统计:\n")
                            for error, count in result['errors'].items():
                                f.write(f"  {error}: {count}次\n")
                        
                        if result['error_codes']:
                            f.write(f"失败的股票代码({len(result['error_codes'])}个):\n")
                            for code in sorted(result['error_codes']):
                                f.write(f"  {code}\n")
                        
                        f.write("\n" + "-" * 40 + "\n\n")
            
            logger.info(f"详细结果已保存到: {filename}")
            
        except Exception as e:
            logger.error(f"保存详细结果失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='测试数据源可用性')
    parser.add_argument('--full', action='store_true', help='全量测试所有股票代码')
    parser.add_argument('--sample-size', type=int, default=200, help='采样大小 (默认: 200)')
    parser.add_argument('--batch-size', type=int, default=50, help='批次大小 (默认: 50)')
    parser.add_argument('--interval', type=float, default=2, help='批次间隔秒数 (默认: 2)')
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = DataSourceTester()
    tester.sample_size = args.sample_size
    tester.batch_size = args.batch_size
    tester.batch_interval = args.interval
    
    try:
        # 运行测试
        tester.run_test(full_test=args.full)
        
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
    finally:
        logger.info("测试结束")


if __name__ == '__main__':
    main()