import re
import os
import sys
from collections import Counter

# 计算KeyWords目录路径
current_dir = os.path.dirname(os.path.abspath(__file__))
isolation_forest_dir = os.path.dirname(os.path.dirname(current_dir))
key_words_dir = os.path.join(isolation_forest_dir, 'KeyWords')

# 添加KeyWords目录到Python路径
sys.path.append(isolation_forest_dir)

# 导入关键词
from KeyWords.sql_keywords import SQL_KEYWORDS
from KeyWords.command_injection_keywords import COMMAND_INJECTION_KEYWORDS
from KeyWords.path_traversal_keywords import PATH_TRAVERSAL_KEYWORDS
from KeyWords.sensitive_files import SENSITIVE_FILES
from KeyWords.bot_keywords import BOT_KEYWORDS


class FeaturesExtractor:
    @staticmethod
    def method_is_get(method):
        return 1 if method.upper() == 'GET' else 0

    @staticmethod
    def method_is_post(method):
        return 1 if method.upper() == 'POST' else 0

    @staticmethod
    def uri_length(uri):
        return len(uri)

    @staticmethod
    def uri_depth(uri):
        return uri.count('/')

    @staticmethod
    def has_query(uri):
        return 1 if '?' in uri else 0

    @staticmethod
    def query_length(uri):
        if '?' in uri:
            return len(uri.split('?', 1)[1])
        return 0

    @staticmethod
    def special_char_count(uri):
        special_chars = re.findall(r'[<>!@#$%^&*()\[\]{}|;:,./?]', uri)
        return len(special_chars)

    @staticmethod
    def digit_ratio(uri):
        if not uri:
            return 0
        digits = len(re.findall(r'\d', uri))
        return digits / len(uri)

    @staticmethod
    def url_encoded_count(uri):
        return len(re.findall(r'%[0-9A-Fa-f]{2}', uri))

    @staticmethod
    def has_double_encoding(uri):
        return 1 if '%25' in uri else 0

    @staticmethod
    def path_traversal_count(uri):
        traversal_patterns = ["../", "%2e%2e/", "%2e%2e%2f"]
        count = 0
        for pattern in traversal_patterns:
            count += uri.lower().count(pattern)
        return count

    @staticmethod
    def has_sensitive_file(uri):
        for sensitive in SENSITIVE_FILES:
            if sensitive in uri.lower():
                return 1
        return 0

    @staticmethod
    def has_cmd_keyword(uri):
        for keyword in COMMAND_INJECTION_KEYWORDS:
            if keyword in uri.lower():
                return 1
        return 0

    @staticmethod
    def has_sql_keyword(uri):
        for keyword in SQL_KEYWORDS:
            if keyword in uri.upper():
                return 1
        return 0

    @staticmethod
    def is_binary_request(uri):
        binary_pattern = re.findall(r'\\x[0-9A-Fa-f]{2}', uri)
        return 1 if len(binary_pattern) > 0 else 0

    @staticmethod
    def status_code(status):
        try:
            return int(status)
        except:
            return 0

    @staticmethod
    def is_4xx(status):
        try:
            code = int(status)
            return 1 if 400 <= code < 500 else 0
        except:
            return 0

    @staticmethod
    def is_5xx(status):
        try:
            code = int(status)
            return 1 if 500 <= code < 600 else 0
        except:
            return 0

    @staticmethod
    def user_agent_length(user_agent):
        return len(user_agent) if user_agent else 0

    @staticmethod
    def is_empty_user_agent(user_agent):
        return 1 if not user_agent else 0

    @staticmethod
    def is_bot_user_agent(user_agent):
        if not user_agent:
            return 0
        for bot in BOT_KEYWORDS:
            if bot in user_agent.lower():
                return 1
        return 0

    @classmethod
    def extract_features(cls, log_entry):
        """提取所有特征

        Args:
            log_entry: 包含日志信息的字典，至少包含以下键：
                - method: HTTP方法
                - uri: 请求URI
                - status: 状态码
                - user_agent: User-Agent

        Returns:
            dict: 包含所有特征的字典
        """
        features = {}

        uri = log_entry.get('uri', '')

        features['method_is_get'] = cls.method_is_get(log_entry.get('method', ''))
        features['method_is_post'] = cls.method_is_post(log_entry.get('method', ''))

        features['uri_length'] = cls.uri_length(uri)
        features['uri_depth'] = cls.uri_depth(uri)
        features['has_query'] = cls.has_query(uri)
        features['query_length'] = cls.query_length(uri)
        features['special_char_count'] = cls.special_char_count(uri)
        features['digit_ratio'] = cls.digit_ratio(uri)

        features['url_encoded_count'] = cls.url_encoded_count(uri)
        features['has_double_encoding'] = cls.has_double_encoding(uri)

        features['path_traversal_count'] = cls.path_traversal_count(uri)
        features['has_sensitive_file'] = cls.has_sensitive_file(uri)

        features['has_cmd_keyword'] = cls.has_cmd_keyword(uri)
        features['has_sql_keyword'] = cls.has_sql_keyword(uri)

        features['is_binary_request'] = cls.is_binary_request(uri)

        status = log_entry.get('status', '')
        features['status_code'] = cls.status_code(status)
        features['is_4xx'] = cls.is_4xx(status)
        features['is_5xx'] = cls.is_5xx(status)

        user_agent = log_entry.get('user_agent', '')
        features['user_agent_length'] = cls.user_agent_length(user_agent)
        features['is_empty_user_agent'] = cls.is_empty_user_agent(user_agent)
        features['is_bot_user_agent'] = cls.is_bot_user_agent(user_agent)

        return features
