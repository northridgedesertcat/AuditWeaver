import re
import json
import os
import numpy as np


class FeatureExtractor:
    """
    URL 特征提取器
    
    功能：从 URL 中提取用于安全检测的数值化特征
    用途：用于机器学习模型检测恶意 URL（如 SQL 注入、XSS、命令执行等攻击）
    """

    def __init__(self, keywords_dir: str = None):
        """
        初始化特征提取器
        
        参数:
            keywords_dir: str - 关键词文件夹路径，默认为同目录下的 keywords 文件夹
        """
        # 设置关键词文件夹路径
        if keywords_dir is None:
            # 默认使用同目录下的 keywords 文件夹
            current_dir = os.path.dirname(os.path.abspath(__file__))
            keywords_dir = os.path.join(current_dir, "keywords")
        
        self.keywords_dir = keywords_dir
        self.keywords_config = self._load_keywords_config()
    
    def _load_keywords_config(self) -> dict:
        """
        加载关键词配置文件（多文件方式）
        
        返回:
            dict - 包含所有关键词配置的字典
        
        异常:
            FileNotFoundError - 关键词文件夹不存在
        """
        if not os.path.exists(self.keywords_dir):
            raise FileNotFoundError(f"关键词文件夹不存在: {self.keywords_dir}")
        
        config = {}
        
        # 定义要加载的关键词文件
        keyword_files = {
            "sql_keywords": "sql_keywords.json",
            "xss_keywords": "xss_keywords.json", 
            "cmd_keywords": "cmd_keywords.json",
            "path_traversal_keywords": "path_traversal_keywords.json",
            "special_chars": "special_chars.json"
        }
        
        for key, filename in keyword_files.items():
            file_path = os.path.join(self.keywords_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config[key] = json.load(f)
            except FileNotFoundError:
                print(f"警告: 关键词文件不存在: {file_path}")
                config[key] = [] if key != "special_chars" else "'\"<>;(){}"
            except json.JSONDecodeError as e:
                print(f"警告: 关键词文件格式错误 {file_path}: {e}")
                config[key] = [] if key != "special_chars" else "'\"<>;(){}"
        
        return config
    
    @property
    def sql_keywords(self) -> list:
        """SQL 注入检测关键词列表"""
        return self.keywords_config.get("sql_keywords", [])
    
    @property
    def xss_keywords(self) -> list:
        """XSS（跨站脚本）检测关键词列表"""
        return self.keywords_config.get("xss_keywords", [])
    
    @property
    def cmd_keywords(self) -> list:
        """命令执行检测关键词列表"""
        return self.keywords_config.get("cmd_keywords", [])
    
    @property
    def path_traversal_keywords(self) -> list:
        """路径遍历检测关键词列表"""
        return self.keywords_config.get("path_traversal_keywords", [])
    
    @property
    def special_chars(self) -> str:
        """特殊字符字符串"""
        return self.keywords_config.get("special_chars", "'\"<>;(){}")

    def extract(self, url: str) -> np.ndarray:
        """
        从 URL 中提取特征向量
        
        参数:
            url: str - 待分析的 URL 字符串
        
        返回:
            np.ndarray - 包含 12 个特征的 numpy 数组
        """
        # 转换为小写，便于关键词匹配
        url_lower = url.lower()

        # 存储特征的列表
        features = []

        # 特征 1: URL 总长度
        # 攻击性 URL 通常较长（包含大量参数或恶意 payload）
        url_length = len(url)
        features.append(url_length)

        # 特征 2: 参数数量
        # 统计&符号数量 +1（如果存在=），表示 URL 参数的个数
        param_count = url.count("&") + 1 if "=" in url else 0
        features.append(param_count)

        # 特征 3: 等号数量
        # 表示参数赋值的次数，攻击 URL 通常有多个参数赋值
        param_value_count = url.count("=")
        features.append(param_value_count)

        # 特征 4: 路径深度
        # 统计斜杠数量，表示 URL 路径的层级深度
        path_depth = url.count("/")
        features.append(path_depth)

        # 特征 5: 特殊字符数量
        # 统计可能用于攻击的特殊字符（引号、尖括号、分号、括号等）
        special_char_count = sum(url.count(c) for c in self.special_chars)
        features.append(special_char_count)

        # 特征 6: 数字比例
        # 数字字符占总长度的比例，异常比例可能表示恶意 payload
        digits = sum(c.isdigit() for c in url)
        digit_ratio = digits / url_length if url_length else 0
        features.append(digit_ratio)

        # 特征 7: URL 编码字符数量
        # 统计%符号数量，攻击者常使用 URL 编码绕过检测
        url_encode_count = url.count("%")
        features.append(url_encode_count)

        # 特征 8: 大写字母比例
        # 大写字母占总长度的比例，用于分析 URL 的字符分布特征
        uppercase = sum(c.isupper() for c in url)
        uppercase_ratio = uppercase / url_length if url_length else 0
        features.append(uppercase_ratio)

        # 特征 9: SQL 注入关键词数量
        # 统计 SQL 注入相关关键词的出现次数
        sql_keyword_count = sum(url_lower.count(k) for k in self.sql_keywords)
        features.append(sql_keyword_count)

        # 特征 10: XSS 攻击关键词数量
        # 统计跨站脚本攻击相关关键词的出现次数
        xss_keyword_count = sum(url_lower.count(k) for k in self.xss_keywords)
        features.append(xss_keyword_count)

        # 特征 11: 路径遍历攻击关键词数量
        # 统计目录穿越攻击特征（../或..\\）的出现次数
        traversal_count = sum(url_lower.count(k) for k in self.path_traversal_keywords)
        features.append(traversal_count)

        # 特征 12: 命令执行关键词数量
        # 统计命令执行相关关键词的出现次数
        command_keyword_count = sum(url_lower.count(k) for k in self.cmd_keywords)
        features.append(command_keyword_count)

        # 返回 numpy 数组格式的特征向量
        return np.array(features)
    
    def extract_and_save(self, url: str, save_path: str = None) -> np.ndarray:
        """
        提取特征并保存到文件
        
        参数:
            url: str - 待分析的 URL 字符串
            save_path: str - 保存路径，默认为同目录下的 features.json
        
        返回:
            np.ndarray - 包含 12 个特征的 numpy 数组
        """
        features = self.extract(url)
        
        if save_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            save_path = os.path.join(current_dir, "features.json")
        
        # 读取现有特征或创建新文件
        if os.path.exists(save_path):
            with open(save_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        else:
            existing_data = {"features": [], "urls": []}
        
        # 添加新特征
        existing_data["features"].append(features.tolist())
        existing_data["urls"].append(url)
        
        # 保存到文件
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        return features
    
    def batch_extract_and_save(self, urls: list, save_path: str = None) -> np.ndarray:
        """
        批量提取特征并保存到文件
        
        参数:
            urls: list - URL 字符串列表
            save_path: str - 保存路径
        
        返回:
            np.ndarray - 特征矩阵
        """
        features_list = []
        
        for url in urls:
            features = self.extract(url)
            features_list.append(features)
        
        feature_matrix = np.array(features_list)
        
        if save_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            save_path = os.path.join(current_dir, "batch_features.json")
        
        # 保存批量特征
        save_data = {
            "features": feature_matrix.tolist(),
            "urls": urls,
            "shape": feature_matrix.shape
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        return feature_matrix
    
