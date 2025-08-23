# coding:utf8
"""
配置管理模块
用于统一管理pqquotation的配置选项
"""

class QuotationConfig:
    """行情接口配置类"""
    
    def __init__(self):
        self._default_return_format = 'national'  # 默认使用国标格式
        self._national_format_enabled = True  # 国标格式默认启用
    
    @property 
    def default_return_format(self) -> str:
        """获取默认返回格式"""
        return self._default_return_format
    
    @default_return_format.setter
    def default_return_format(self, format_type: str):
        """设置默认返回格式
        
        :param format_type: 格式类型 ('digit', 'prefix', 'national')
        """
        valid_formats = ['digit', 'prefix', 'national']
        if format_type not in valid_formats:
            raise ValueError(f"无效的返回格式: {format_type}。有效格式: {valid_formats}")
        
        self._default_return_format = format_type
        if format_type == 'national':
            self._national_format_enabled = True
    
    def enable_national_format(self):
        """启用国标格式作为默认返回格式"""
        self.default_return_format = 'national'
    
    def enable_prefix_format(self):
        """启用前缀格式作为默认返回格式"""
        self.default_return_format = 'prefix'
    
    def enable_digit_format(self):
        """启用数字格式作为默认返回格式"""
        self.default_return_format = 'digit'
    
    @property
    def national_format_enabled(self) -> bool:
        """检查是否启用了国标格式"""
        return self._national_format_enabled
    
    def get_format_examples(self) -> str:
        """获取当前格式的示例"""
        if self._default_return_format == 'national':
            return "国标格式示例: 000001.SZ, 600000.SH, 430047.BJ"
        elif self._default_return_format == 'prefix':
            return "前缀格式示例: sz000001, sh600000, bj430047"
        else:
            return "数字格式示例: 000001, 600000, 430047"
    
    def __str__(self):
        return f"QuotationConfig(default_return_format='{self._default_return_format}')"


# 全局配置实例
_global_config = QuotationConfig()


def get_config() -> QuotationConfig:
    """获取全局配置实例"""
    return _global_config


def set_default_return_format(format_type: str):
    """设置全局默认返回格式的便捷函数
    
    :param format_type: 格式类型 ('digit', 'prefix', 'national')
    """
    _global_config.default_return_format = format_type


def enable_national_format_globally():
    """全局启用国标格式的便捷函数"""
    _global_config.enable_national_format()


def enable_prefix_format_globally():
    """全局启用前缀格式的便捷函数"""
    _global_config.enable_prefix_format()


def enable_digit_format_globally():
    """全局启用数字格式的便捷函数"""
    _global_config.enable_digit_format()