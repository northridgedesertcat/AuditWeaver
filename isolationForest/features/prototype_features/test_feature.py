# -*- coding: utf-8 -*-
"""
特征提取器测试脚本
"""

from feature_extractor import FeatureExtractor

# 测试新的配置化特征提取器
def test_feature_extractor():
    # 创建特征提取器（默认使用同目录下的keywords文件夹）
    extractor = FeatureExtractor()
    
    # 测试URL示例
    test_urls = [
        "/tienda1/publico/anadir.jsp?id=1 OR 1=1",  # SQL注入
        "/search?q=<script>alert('xss')</script>",   # XSS攻击
        "/api?cmd=whoami",                          # 命令执行
        "/files/../../../etc/passwd",               # 路径遍历
        "/normal/path/to/resource"                   # 正常URL
    ]
    
    print("=== 特征提取器测试 ===")
    print(f"关键词文件夹: {extractor.keywords_dir}")
    print(f"SQL关键词数量: {len(extractor.sql_keywords)}")
    print(f"XSS关键词数量: {len(extractor.xss_keywords)}")
    print(f"命令执行关键词数量: {len(extractor.cmd_keywords)}")
    print(f"路径遍历关键词数量: {len(extractor.path_traversal_keywords)}")
    print(f"特殊字符: {extractor.special_chars}")
    print()
    
    for i, url in enumerate(test_urls, 1):
        print(f"测试 {i}: {url}")
        features = extractor.extract(url)
        print(f"特征向量: {features}")
        print(f"特征维度: {features.shape}")
        print()

def test_keyword_files():
    """测试关键词文件加载"""
    print("=== 关键词文件测试 ===")
    
    import json
    import os
    
    keywords_dir = os.path.join(os.path.dirname(__file__), "keywords")
    
    # 检查每个关键词文件
    keyword_files = [
        "sql_keywords.json",
        "xss_keywords.json", 
        "cmd_keywords.json",
        "path_traversal_keywords.json",
        "special_chars.json"
    ]
    
    for filename in keyword_files:
        file_path = os.path.join(keywords_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ {filename}: 加载成功，包含 {len(data) if isinstance(data, list) else len(str(data))} 个元素")
        else:
            print(f"✗ {filename}: 文件不存在")
    
    print()

if __name__ == "__main__":
    # 设置编码为UTF-8，避免中文乱码
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    test_keyword_files()
    test_feature_extractor()