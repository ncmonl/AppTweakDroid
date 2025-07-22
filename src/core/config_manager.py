import os
import json

class ConfigManager:
    def __init__(self):
        self.config_file = 'app_config.json'
        self.default_config = {
            'zipalign_enabled': False,
            'debuggable_enabled': True,  # 默认启用调试
            'output_dir': 'output'  # 添加输出目录配置
        }
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件，如果不存在则创建默认配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.default_config.copy()
        except Exception as e:
            print(f'加载配置文件失败：{str(e)}')
            return self.default_config.copy()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f'保存配置文件失败：{str(e)}')
    
    def get_value(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def set_value(self, key, value):
        """设置配置值并保存"""
        self.config[key] = value
        self.save_config()