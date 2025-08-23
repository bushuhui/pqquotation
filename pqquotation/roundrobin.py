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
        self._retry_interval = 60  # 失败数据源重试间隔（秒）
        self._last_retry_time = {}
        
        # 性能统计
        self._source_stats = {name: {'success': 0, 'failure': 0, 'avg_response_time': 0} 
                             for name in self._source_names}
        
        self._logger = logging.getLogger(__name__)

    @property
    def stock_api(self) -> str:
        """兼容基类接口，实际不使用"""
        return "round-robin"
    
    def _get_next_source(self) -> str:
        """获取下一个可用数据源"""
        with self._lock:
            # 清理过期的失败源
            current_time = time.time()
            expired_sources = []
            for source in self._failed_sources:
                if (current_time - self._last_retry_time.get(source, 0)) > self._retry_interval:
                    expired_sources.append(source)
            
            for source in expired_sources:
                self._failed_sources.discard(source)
                self._logger.info(f"数据源 {source} 重试时间到，重新加入轮询")
            
            # 寻找可用数据源
            attempts = 0
            while attempts < len(self._source_names):
                source_name = self._source_names[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._source_names)
                
                if source_name not in self._failed_sources:
                    return source_name
                    
                attempts += 1
            
            # 如果所有数据源都失败了，返回第一个数据源（强制重试）
            self._logger.warning("所有数据源都不可用，强制使用第一个数据源重试")
            return self._source_names[0]
    
    def _mark_source_failed(self, source_name: str):
        """标记数据源失败"""
        with self._lock:
            self._failed_sources.add(source_name)
            self._last_retry_time[source_name] = time.time()
            self._source_stats[source_name]['failure'] += 1
            self._logger.warning(f"数据源 {source_name} 被标记为失败")
    
    def _mark_source_success(self, source_name: str, response_time: float):
        """标记数据源成功"""
        with self._lock:
            self._failed_sources.discard(source_name)
            stats = self._source_stats[source_name]
            stats['success'] += 1
            # 简单的移动平均
            stats['avg_response_time'] = (stats['avg_response_time'] + response_time) / 2
    
    def _normalize_data_format(self, data: Dict[str, Any], source_name: str) -> Dict[str, Any]:
        """统一数据格式，将不同数据源的格式标准化为sina格式"""
        if source_name == 'sina':
            return data
        elif source_name == 'tencent':
            return self._convert_tencent_to_sina(data)
        elif source_name == 'dc':
            return self._convert_dc_to_sina(data)
        else:
            return data
    
    def _convert_tencent_to_sina(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将腾讯数据格式转换为sina格式"""
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
    
    def _convert_dc_to_sina(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将东方财富数据格式转换为sina格式"""
        # DC数据格式已经与sina基本一致，直接返回
        return data
    
    def real(self, stock_codes, prefix=False, max_retries=3):
        """获取指定股票的实时行情，支持Round-robin和故障切换
        :param stock_codes: 股票代码或股票代码列表
        :param prefix: 是否在返回键中包含市场前缀
        :param max_retries: 最大重试次数
        :return: 行情字典
        """
        if not isinstance(stock_codes, list):
            stock_codes = [stock_codes]
        
        retries = 0
        while retries < max_retries:
            source_name = self._get_next_source()
            source = self._sources[source_name]
            
            start_time = time.time()
            try:
                self._logger.info(f"使用数据源 {source_name} 获取行情数据")
                raw_data = source.real(stock_codes, prefix=prefix)
                
                if raw_data:
                    response_time = time.time() - start_time
                    self._mark_source_success(source_name, response_time)
                    
                    # 数据格式标准化
                    normalized_data = self._normalize_data_format(raw_data, source_name)
                    self._logger.info(f"数据源 {source_name} 成功返回 {len(normalized_data)} 条数据")
                    return normalized_data
                else:
                    raise Exception("返回数据为空")
                    
            except Exception as e:
                self._logger.error(f"数据源 {source_name} 获取数据失败: {e}")
                self._mark_source_failed(source_name)
                retries += 1
                
                if retries < max_retries:
                    self._logger.info(f"重试 {retries}/{max_retries}")
                else:
                    self._logger.error(f"所有重试均失败，无法获取股票数据")
        
        # 所有数据源都失败了，返回空字典
        return {}
    
    def get_source_stats(self) -> Dict[str, Any]:
        """获取数据源统计信息"""
        with self._lock:
            stats = {
                'sources': dict(self._source_stats),
                'failed_sources': list(self._failed_sources),
                'current_source': self._source_names[self._current_index],
                'total_sources': len(self._source_names)
            }
        return stats
    
    def reset_failed_sources(self):
        """重置所有失败的数据源状态"""
        with self._lock:
            self._failed_sources.clear()
            self._last_retry_time.clear()
            self._logger.info("已重置所有失败数据源状态")
    
    # 兼容基类接口
    def get_stocks_by_range(self, params):
        """兼容基类接口，但不直接使用"""
        pass
    
    def format_response_data(self, rep_data, **kwargs):
        """兼容基类接口，但实际格式化在_normalize_data_format中处理"""
        return rep_data