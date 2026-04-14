import sys
import os

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from features_extractor import FeaturesExtractor

# 测试样例
test_logs = [
    {
        'method': 'GET',
        'uri': '/index.html',
        'query': 'id=1&name=test',
        'post_data': '',
        'content': '',
        'cookie': 'session=abc123',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    {
        'method': 'POST',
        'uri': '/login.jsp',
        'query': '',
        'post_data': 'username=admin&password=123456',
        'content': 'username=admin&password=123456',
        'cookie': '',
        'user_agent': 'python-requests/2.28.0'
    },
    {
        'method': 'GET',
        'uri': '/../../etc/passwd',
        'query': 'cmd=ls',
        'post_data': '',
        'content': '',
        'cookie': 'session=def456',
        'user_agent': 'sqlmap/1.6.10#stable'
    }
]

def test_features():
    print("Testing features extraction...")
    print("=" * 60)
    
    for i, log in enumerate(test_logs):
        print(f"Test case {i+1}:")
        print(f"Method: {log['method']}")
        print(f"URI: {log['uri']}")
        print(f"Query: {log['query']}")
        print(f"User-Agent: {log['user_agent']}")
        
        features = FeaturesExtractor.extract_features(log)
        print("Extracted features:")
        for key, value in features.items():
            print(f"  {key}: {value}")
        print("-" * 60)

if __name__ == "__main__":
    test_features()
