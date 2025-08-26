# coding:utf8
import time
import logging
from typing import List, Dict, Any, Optional
from threading import Lock

from . import sina, tencent, dc, basequotation


class RoundRobinQuotation(basequotation.BaseQuotation):
    """Round-robin A股实时行情获取器
    轮流调用sina、qq(tencent)、dc数据接口，提供故障自动切换功能
    """
    
    def __init__(self):
        super().__init__()
        
        # 初始化数据源
        self._sources = {
            'sina': sina.Sina(),
            'tencent': tencent.Tencent(), 
            'dc': dc.DC()
        }
        
        # 轮询状态
        self._source_names = list(self._sources.keys())
        self._current_index = 0
        self._lock = Lock()
        
        # 故障处理
        self._failed_sources = set()
        self._retry_interval = 300  # 失败数据源重试间隔（秒），增加到5分钟
        self._last_retry_time = {}
        self._failure_threshold = 3  # 连续失败次数阈值
        self._failure_counts = {name: 0 for name in self._source_names}  # 记录每个数据源的连续失败次数
        self._last_success_time = {name: time.time() for name in self._source_names}  # 记录最后成功时间
        
        # 性能统计
        self._source_stats = {name: {'success': 0, 'failure': 0, 'avg_response_time': 0} 
                             for name in self._source_names}
        
        self._logger = logging.getLogger(__name__)

    @property
    def stock_api(self) -> str:
        """兼容基类接口，实际不使用"""
        return "round-robin"
    
    def _get_next_source(self) -> str:
        """获取下一个可用数据源 - 改进版本，更快的故障切换"""
        with self._lock:
            current_time = time.time()
            
            # 清理过期的失败源
            expired_sources = []
            for source in self._failed_sources:
                if (current_time - self._last_retry_time.get(source, 0)) > self._retry_interval:
                    expired_sources.append(source)
            
            for source in expired_sources:
                self._failed_sources.discard(source)
                self._failure_counts[source] = 0  # 重置失败计数
                self._logger.info(f"数据源 {source} 重试时间到，重新加入轮询")
            
            # 获取所有可用数据源（未被标记为失败的）
            available_sources = [s for s in self._source_names if s not in self._failed_sources]
            
            if not available_sources:
                # 如果所有数据源都失败了，强制重试最近成功过的数据源
                # 选择最近成功时间最晚的数据源
                best_source = max(self._source_names, 
                                key=lambda s: self._last_success_time.get(s, 0))
                self._logger.warning(f"所有数据源都不可用，强制重试最近成功的数据源: {best_source}")
                return best_source
            
            # 在可用数据源中进行round-robin选择
            # 更新索引以指向下一个可用数据源
            attempts = 0
            while attempts < len(self._source_names):
                candidate = self._source_names[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._source_names)
                
                if candidate in available_sources:
                    return candidate
                    
                attempts += 1
            
            # 备用选择：返回第一个可用数据源
            return available_sources[0]
    
    def _mark_source_failed(self, source_name: str):
        """标记数据源失败 - 改进版本，基于连续失败次数判断"""
        with self._lock:
            self._failure_counts[source_name] += 1
            self._source_stats[source_name]['failure'] += 1
            
            # 连续失败次数达到阈值时，才将数据源标记为不可用
            if self._failure_counts[source_name] >= self._failure_threshold:
                self._failed_sources.add(source_name)
                self._last_retry_time[source_name] = time.time()
                self._logger.warning(f"数据源 {source_name} 连续失败 {self._failure_counts[source_name]} 次，标记为不可用")
            else:
                self._logger.info(f"数据源 {source_name} 失败 ({self._failure_counts[source_name]}/{self._failure_threshold})")
    
    def _is_source_recently_failed(self, source_name: str) -> bool:
        """检查数据源是否最近失败过，用于快速跳过明显有问题的数据源"""
        current_time = time.time()
        last_success = self._last_success_time.get(source_name, 0)
        
        # 如果超过2分钟没有成功，且有失败记录，则认为最近失败过
        return (current_time - last_success > 120 and 
                self._failure_counts.get(source_name, 0) > 0)
    
    def _mark_source_success(self, source_name: str, response_time: float):
        """标记数据源成功 - 改进版本，重置失败状态"""
        with self._lock:
            # 成功时立即从失败列表中移除，并重置失败计数
            self._failed_sources.discard(source_name)
            self._failure_counts[source_name] = 0
            self._last_success_time[source_name] = time.time()
            
            stats = self._source_stats[source_name]
            stats['success'] += 1
            # 简单的移动平均
            stats['avg_response_time'] = (stats['avg_response_time'] + response_time) / 2
    
    def _normalize_data_format(self, data: Dict[str, Any], source_name: str, return_format: str = 'digit') -> Dict[str, Any]:
        """统一数据格式，将不同数据源的格式标准化为sina格式
        :param return_format: 如果是'prefix'格式，则保持键的格式不变
        """
        # 对于prefix格式，直接返回原始数据，不进行键转换
        if return_format == 'prefix':
            if source_name == 'sina':
                return data
            elif source_name == 'tencent':
                return self._convert_tencent_to_sina(data, preserve_keys=True)
            elif source_name == 'dc':
                return self._convert_dc_to_sina(data, preserve_keys=True)
            else:
                return data
        else:
            # 其他格式按原来的逻辑处理
            if source_name == 'sina':
                return data
            elif source_name == 'tencent':
                return self._convert_tencent_to_sina(data)
            elif source_name == 'dc':
                return self._convert_dc_to_sina(data)
            else:
                return data
    
    def _convert_tencent_to_sina(self, data: Dict[str, Any], preserve_keys: bool = False) -> Dict[str, Any]:
        """将腾讯数据格式转换为sina格式
        :param preserve_keys: 是否保持原始键格式（用于prefix格式）
        """
        normalized = {}
        for code, stock_data in data.items():
            try:
                # 处理时间格式
                datetime_obj = stock_data.get('datetime')
                if datetime_obj:
                    import datetime as dt
                    if hasattr(datetime_obj, 'strftime'):
                        # datetime对象
                        date = datetime_obj.strftime('%Y-%m-%d')
                        time_str = datetime_obj.strftime('%H:%M:%S')
                    else:
                        # struct_time对象
                        date = time.strftime('%Y-%m-%d', datetime_obj)
                        time_str = time.strftime('%H:%M:%S', datetime_obj)
                else:
                    date = time.strftime('%Y-%m-%d')
                    time_str = time.strftime('%H:%M:%S')
                
                normalized[code] = {
                    'name': stock_data.get('name', ''),
                    'open': stock_data.get('open', 0.0),
                    'close': stock_data.get('close', 0.0),
                    'now': stock_data.get('now', 0.0),
                    'high': stock_data.get('high', 0.0),
                    'low': stock_data.get('low', 0.0),
                    'buy': stock_data.get('bid1', 0.0),
                    'sell': stock_data.get('ask1', 0.0),
                    'turnover': int(stock_data.get('成交量(手)', 0)),
                    'volume': stock_data.get('成交额(万)', 0.0) / 10000,  # 转换为万元
                    'bid1_volume': int(stock_data.get('bid1_volume', 0)),
                    'bid1': stock_data.get('bid1', 0.0),
                    'bid2_volume': int(stock_data.get('bid2_volume', 0)),
                    'bid2': stock_data.get('bid2', 0.0),
                    'bid3_volume': int(stock_data.get('bid3_volume', 0)),
                    'bid3': stock_data.get('bid3', 0.0),
                    'bid4_volume': int(stock_data.get('bid4_volume', 0)),
                    'bid4': stock_data.get('bid4', 0.0),
                    'bid5_volume': int(stock_data.get('bid5_volume', 0)),
                    'bid5': stock_data.get('bid5', 0.0),
                    'ask1_volume': int(stock_data.get('ask1_volume', 0)),
                    'ask1': stock_data.get('ask1', 0.0),
                    'ask2_volume': int(stock_data.get('ask2_volume', 0)),
                    'ask2': stock_data.get('ask2', 0.0),
                    'ask3_volume': int(stock_data.get('ask3_volume', 0)),
                    'ask3': stock_data.get('ask3', 0.0),
                    'ask4_volume': int(stock_data.get('ask4_volume', 0)),
                    'ask4': stock_data.get('ask4', 0.0),
                    'ask5_volume': int(stock_data.get('ask5_volume', 0)),
                    'ask5': stock_data.get('ask5', 0.0),
                    'date': date,
                    'time': time_str,
                }
            except Exception as e:
                self._logger.warning(f"转换腾讯数据格式失败 {code}: {e}")
                continue
                
        return normalized
    
    def _convert_dc_to_sina(self, data: Dict[str, Any], preserve_keys: bool = False) -> Dict[str, Any]:
        """将东方财富数据格式转换为sina格式
        :param preserve_keys: 是否保持原始键格式（用于prefix格式）
        """
        # DC数据格式已经与sina基本一致，直接返回
        return data
    
    def real(self, stock_codes, prefix=False, max_retries=3, return_format=None):
        """获取指定股票的实时行情，支持Round-robin和故障切换 (增强版)
        :param stock_codes: 股票代码或股票代码列表，
                支持多种格式：数字格式(000001), 前缀格式(sz000001), 国标格式(000001.SZ)
        :param prefix: 是否在返回键中包含市场前缀（当return_format='national'时此参数被忽略）
        :param max_retries: 最大重试次数
        :param return_format: 返回数据中股票代码的格式 ('digit': 000001, 'prefix': sz000001, 'national': 000001.SZ)
                    如果为None，使用全局配置的默认格式
        :return: 行情字典
        """
        # 导入配置模块
        from . import config
        
        # 如果没有指定return_format，使用全局配置
        if return_format is None:
            return_format = config.get_config().default_return_format
        
        if not isinstance(stock_codes, list):
            stock_codes = [stock_codes]
        
        # 预处理：验证和标准化股票代码
        from . import helpers
        valid_codes = []
        for code in stock_codes:
            if helpers.validate_stock_code(code):
                valid_codes.append(code)
            else:
                self._logger.warning(f"跳过无效股票代码 {code}。{helpers.format_stock_code_examples()}")
        
        if not valid_codes:
            self._logger.error("没有有效的股票代码")
            return {}
        
        # 改进的重试逻辑：尝试所有可用数据源
        attempted_sources = set()
        total_attempts = 0
        
        while total_attempts < max_retries:
            # 获取下一个数据源
            source_name = self._get_next_source()
            
            # 如果已经尝试过所有数据源但仍未成功，等待一小段时间后重置尝试记录
            if source_name in attempted_sources and len(attempted_sources) >= len(self._source_names):
                self._logger.info(f"已尝试所有数据源，等待1秒后重置尝试记录")
                time.sleep(1)  # 短暂等待
                attempted_sources.clear()
            
            attempted_sources.add(source_name)
            source = self._sources[source_name]
            
            # 跳过最近明显有问题的数据源（除非是最后尝试）
            if self._is_source_recently_failed(source_name) and total_attempts < max_retries - 1:
                self._logger.debug(f"跳过最近失败过的数据源 {source_name}")
                total_attempts += 1
                continue
            
            start_time = time.time()
            try:
                self._logger.info(f"使用数据源 {source_name} 获取行情数据 (尝试 {total_attempts + 1}/{max_retries})")
                
                # 根据return_format调用底层接口
                if return_format == 'national':
                    # 国标格式时先获取数字格式数据，然后转换
                    raw_data = source.real(valid_codes, prefix=False, return_format='digit')
                elif return_format == 'prefix':
                    # 前缀格式
                    raw_data = source.real(valid_codes, prefix=True, return_format='prefix')  
                else:
                    # 数字格式或其他
                    raw_data = source.real(valid_codes, prefix=prefix, return_format=return_format)
                
                # 验证返回数据的有效性
                if raw_data and isinstance(raw_data, dict) and len(raw_data) > 0:
                    # 检查数据是否为空或无效
                    valid_data = {k: v for k, v in raw_data.items() 
                                if v and isinstance(v, dict) and v.get('now', 0) > 0}
                    
                    if valid_data:
                        response_time = time.time() - start_time
                        self._mark_source_success(source_name, response_time)
                        
                        # 数据格式标准化
                        normalized_data = self._normalize_data_format(valid_data, source_name, return_format)
                        
                        # 根据return_format进行最终格式转换
                        if return_format == 'national':
                            # 转换为国标格式，传入原始代码以保留市场信息
                            final_data = helpers.convert_data_keys_to_national_format(normalized_data, valid_codes)
                        elif return_format == 'prefix':
                            # 前缀格式已经在调用底层接口时设置了prefix=True，保持原有数据
                            final_data = normalized_data
                        else:
                            # 数字格式，保持原有数据
                            final_data = normalized_data
                        
                        self._logger.info(f"数据源 {source_name} 成功返回 {len(final_data)} 条有效数据")
                        return final_data
                    else:
                        raise Exception("返回数据为空或无效（价格为0）")
                else:
                    raise Exception("返回数据为空")
                    
            except Exception as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                self._logger.error(f"数据源 {source_name} 获取数据失败 (耗时 {response_time:.2f}s): {error_msg}")
                self._mark_source_failed(source_name)
                total_attempts += 1
                
                # 如果这是一个快速失败（如连接拒绝），立即尝试下一个数据源
                if response_time < 5.0 and total_attempts < max_retries:
                    self._logger.info(f"快速失败，立即尝试下一个数据源")
                    continue
                    
                if total_attempts >= max_retries:
                    self._logger.error(f"已达到最大重试次数 {max_retries}，无法获取股票数据")
                    break
        
        # 所有尝试都失败了，返回空字典
        self._logger.error(f"未获取到{','.join(valid_codes)}的行情数据")
        return {}
    
    def get_source_stats(self) -> Dict[str, Any]:
        """获取数据源统计信息 - 增强版本"""
        with self._lock:
            current_time = time.time()
            stats = {
                'sources': dict(self._source_stats),
                'failed_sources': list(self._failed_sources),
                'current_source': self._source_names[self._current_index],
                'total_sources': len(self._source_names),
                'failure_counts': dict(self._failure_counts),
                'last_success_time': {
                    name: {
                        'timestamp': self._last_success_time.get(name, 0),
                        'seconds_ago': current_time - self._last_success_time.get(name, 0)
                    } for name in self._source_names
                },
                'available_sources': [s for s in self._source_names if s not in self._failed_sources],
                'failure_threshold': self._failure_threshold,
                'retry_interval': self._retry_interval
            }
        return stats
    
    def reset_failed_sources(self):
        """重置所有失败的数据源状态 - 增强版本"""
        with self._lock:
            self._failed_sources.clear()
            self._last_retry_time.clear()
            self._failure_counts = {name: 0 for name in self._source_names}
            self._logger.info("已重置所有失败数据源状态")
    
    def force_exclude_source(self, source_name: str, duration: int = 600):
        """强制排除指定数据源一段时间（用于维护等场景）
        :param source_name: 要排除的数据源名称
        :param duration: 排除持续时间（秒），默认10分钟
        """
        if source_name not in self._source_names:
            self._logger.warning(f"无效的数据源名称: {source_name}")
            return
            
        with self._lock:
            self._failed_sources.add(source_name)
            self._last_retry_time[source_name] = time.time()
            # 临时调整重试间隔
            original_interval = self._retry_interval
            self._retry_interval = duration
            self._logger.warning(f"强制排除数据源 {source_name} {duration} 秒")
            
        # 恢复原来的重试间隔（这里简化处理，实际可以用定时器）
        def restore_interval():
            time.sleep(5)  # 短暂延迟后恢复
            self._retry_interval = original_interval
        
        import threading
        threading.Thread(target=restore_interval, daemon=True).start()
    
    def get_health_summary(self) -> str:
        """获取数据源健康状况摘要"""
        stats = self.get_source_stats()
        available = stats['available_sources']
        failed = stats['failed_sources']
        
        summary = f"数据源状态: {len(available)}/{stats['total_sources']} 可用"
        if failed:
            summary += f", 故障源: {', '.join(failed)}"
        
        # 显示最近成功时间
        recent_failures = []
        for name, time_info in stats['last_success_time'].items():
            if time_info['seconds_ago'] > 300:  # 5分钟内没成功
                recent_failures.append(f"{name}({int(time_info['seconds_ago']/60)}分钟前)")
        
        if recent_failures:
            summary += f", 近期问题: {', '.join(recent_failures)}"
        
        return summary
    
    # 兼容基类接口
    def get_stocks_by_range(self, params):
        """兼容基类接口，但不直接使用"""
        pass
    
    def format_response_data(self, rep_data, **kwargs):
        """兼容基类接口，但实际格式化在_normalize_data_format中处理"""
        return rep_data