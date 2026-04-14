import re
import math
import base64
from collections import Counter

# 导入关键词
try:
    from .KeyWords.sql_keywords import SQL_KEYWORDS
    from .KeyWords.xss_keywords import XSS_KEYWORDS
    from .KeyWords.path_traversal_keywords import PATH_TRAVERSAL_KEYWORDS
    from .KeyWords.command_injection_keywords import COMMAND_INJECTION_KEYWORDS
except ImportError:
    from KeyWords.sql_keywords import SQL_KEYWORDS
    from KeyWords.xss_keywords import XSS_KEYWORDS
    from KeyWords.path_traversal_keywords import PATH_TRAVERSAL_KEYWORDS
    from KeyWords.command_injection_keywords import COMMAND_INJECTION_KEYWORDS

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
    def uri_has_jsp(uri):
        return 1 if '.jsp' in uri.lower() else 0
    
    @staticmethod
    def uri_special_char_count(uri):
        special_chars = re.findall(r'[<>!@#$%^&*()\[\]{}|;:,./?]', uri)
        return len(special_chars)
    
    @staticmethod
    def calculate_entropy(text):
        if not text:
            return 0
        counter = Counter(text)
        total = len(text)
        entropy = 0
        for count in counter.values():
            probability = count / total
            entropy -= probability * math.log2(probability)
        return entropy
    
    @staticmethod
    def uri_entropy(uri):
        return FeaturesExtractor.calculate_entropy(uri)
    
    @staticmethod
    def get_query_length(query):
        return len(query) if query else 0
    
    @staticmethod
    def post_data_length(data):
        return len(data) if data else 0
    
    @staticmethod
    def query_param_count(query):
        if not query:
            return 0
        params = query.split('&')
        return len(params)
    
    @staticmethod
    def query_special_char_count(query):
        if not query:
            return 0
        special_chars = re.findall(r'[<>!@#$%^&*()\[\]{}|;:,./?]', query)
        return len(special_chars)
    
    @staticmethod
    def query_entropy(query):
        return FeaturesExtractor.calculate_entropy(query)
    
    @staticmethod
    def count_keywords(text, keywords):
        if not text:
            return 0
        count = 0
        text_upper = text.upper()
        for keyword in keywords:
            if keyword.upper() in text_upper:
                count += 1
        return count
    
    @staticmethod
    def sql_keyword_count(text):
        return FeaturesExtractor.count_keywords(text, SQL_KEYWORDS)
    
    @staticmethod
    def xss_keyword_count(text):
        return FeaturesExtractor.count_keywords(text, XSS_KEYWORDS)
    
    @staticmethod
    def path_traversal_count(text):
        return FeaturesExtractor.count_keywords(text, PATH_TRAVERSAL_KEYWORDS)
    
    @staticmethod
    def command_injection_count(text):
        return FeaturesExtractor.count_keywords(text, COMMAND_INJECTION_KEYWORDS)
    
    @staticmethod
    def query_has_base64(query):
        if not query:
            return 0
        try:
            # 尝试解码base64
            for part in query.split('&'):
                if '=' in part:
                    value = part.split('=', 1)[1]
                    # 检查是否符合base64格式
                    if re.match(r'^[A-Za-z0-9+/]+={0,2}$', value):
                        try:
                            base64.b64decode(value)
                            return 1
                        except:
                            pass
            return 0
        except:
            return 0
    
    @staticmethod
    def query_has_double_encoding(query):
        if not query:
            return 0
        # 检查是否包含%25（%的编码）
        if '%25' in query:
            return 1
        return 0
    
    @staticmethod
    def query_has_unicode_escape(query):
        if not query:
            return 0
        # 检查是否包含\uXXXX格式的unicode转义
        if re.search(r'\\u[0-9a-fA-F]{4}', query):
            return 1
        return 0
    
    @staticmethod
    def content_length(content):
        return len(content) if content else 0
    
    @staticmethod
    def has_cookie(cookie):
        return 1 if cookie else 0
    
    @staticmethod
    def cookie_length(cookie):
        return len(cookie) if cookie else 0
    
    @staticmethod
    def user_agent_length(user_agent):
        return len(user_agent) if user_agent else 0
    
    @staticmethod
    def is_empty_user_agent(user_agent):
        return 1 if not user_agent else 0
    
    @staticmethod
    def contains_sqlmap(user_agent):
        return 1 if user_agent and 'sqlmap' in user_agent.lower() else 0
    
    @staticmethod
    def contains_curl(user_agent):
        return 1 if user_agent and 'curl' in user_agent.lower() else 0
    
    @staticmethod
    def contains_python_requests(user_agent):
        return 1 if user_agent and 'python-requests' in user_agent.lower() else 0
    
    @classmethod
    def extract_features(cls, log_entry):
        """提取所有特征
        
        Args:
            log_entry: 包含日志信息的字典，至少包含以下键：
                - method: HTTP方法
                - uri: 请求URI
                - query: GET查询参数
                - post_data: POST数据
                - content: 请求内容
                - cookie: Cookie
                - user_agent: User-Agent
        
        Returns:
            dict: 包含所有特征的字典
        """
        features = {}
        
        # HTTP方法特征
        features['method_is_get'] = cls.method_is_get(log_entry.get('method', ''))
        features['method_is_post'] = cls.method_is_post(log_entry.get('method', ''))
        
        # URI特征
        uri = log_entry.get('uri', '')
        features['uri_length'] = cls.uri_length(uri)
        features['uri_depth'] = cls.uri_depth(uri)
        features['uri_has_jsp'] = cls.uri_has_jsp(uri)
        features['uri_special_char_count'] = cls.uri_special_char_count(uri)
        features['uri_entropy'] = cls.uri_entropy(uri)
        
        # 查询参数特征
        query = log_entry.get('query', '')
        features['get_query_length'] = cls.get_query_length(query)
        features['post_data_length'] = cls.post_data_length(log_entry.get('post_data', ''))
        features['query_param_count'] = cls.query_param_count(query)
        features['query_special_char_count'] = cls.query_special_char_count(query)
        features['query_entropy'] = cls.query_entropy(query)
        
        # 安全关键词特征
        combined_text = f"{uri} {query} {log_entry.get('post_data', '')}"
        features['sql_keyword_count'] = cls.sql_keyword_count(combined_text)
        features['xss_keyword_count'] = cls.xss_keyword_count(combined_text)
        features['path_traversal_count'] = cls.path_traversal_count(combined_text)
        features['command_injection_count'] = cls.command_injection_count(combined_text)
        
        # 编码特征
        features['query_has_base64'] = cls.query_has_base64(query)
        features['query_has_double_encoding'] = cls.query_has_double_encoding(query)
        features['query_has_unicode_escape'] = cls.query_has_unicode_escape(query)
        
        # 其他特征
        features['content_length'] = cls.content_length(log_entry.get('content', ''))
        features['has_cookie'] = cls.has_cookie(log_entry.get('cookie', ''))
        features['cookie_length'] = cls.cookie_length(log_entry.get('cookie', ''))
        features['user_agent_length'] = cls.user_agent_length(log_entry.get('user_agent', ''))
        features['is_empty_user_agent'] = cls.is_empty_user_agent(log_entry.get('user_agent', ''))
        features['contains_sqlmap'] = cls.contains_sqlmap(log_entry.get('user_agent', ''))
        features['contains_curl'] = cls.contains_curl(log_entry.get('user_agent', ''))
        features['contains_python_requests'] = cls.contains_python_requests(log_entry.get('user_agent', ''))
        
        return features
