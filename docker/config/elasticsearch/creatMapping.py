#!/usr/bin/env python
"""创建 Elasticsearch 索引 Mapping 脚本

从 mappings 目录加载 YAML 配置文件，自动创建对应的索引。
"""

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError
import yaml
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from common.env import ES_HOST, ES_PORT, ES_USER, ES_PASSWORD

def get_es_client(host=ES_HOST, port=ES_PORT, user=ES_USER, password=ES_PASSWORD):
    """获取 Elasticsearch 客户端"""
    try:
        es = Elasticsearch(
            hosts=[f"http://{host}:{port}"],
            basic_auth=(user, password),
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        if es.ping():
            print(f"✅ 成功连接到 Elasticsearch: http://{host}:{port}")
            return es
        else:
            print(f"❌ 无法连接到 Elasticsearch: http://{host}:{port}")
            return None
    except Exception as e:
        print(f"❌ Elasticsearch 连接失败: {str(e)}")
        return None

def create_index(es, index_name, mapping, force_recreate=False):
    """创建索引"""
    try:
        if es.indices.exists(index=index_name):
            if force_recreate:
                print(f"⚠️ 索引 {index_name} 已存在，正在删除并重新创建...")
                es.indices.delete(index=index_name)
            else:
                print(f"ℹ️ 索引 {index_name} 已存在，跳过创建")
                return False
        
        es.indices.create(index=index_name, body=mapping)
        print(f"✅ 成功创建索引: {index_name}")
        return True
    except RequestError as e:
        print(f"❌ 创建索引 {index_name} 失败: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 创建索引 {index_name} 异常: {str(e)}")
        return False

def load_mappings_from_dir(mappings_dir):
    """从指定目录加载所有 YAML 映射配置"""
    mappings = []
    if not os.path.exists(mappings_dir):
        print(f"❌ 映射配置目录不存在: {mappings_dir}")
        return mappings
        
    for filename in sorted(os.listdir(mappings_dir)):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            filepath = os.path.join(mappings_dir, filename)
            index_name = os.path.splitext(filename)[0]
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    mapping = yaml.safe_load(f)
                if mapping:
                    mappings.append((index_name, mapping))
                    print(f"📄 已加载映射配置: {filename} -> 索引 {index_name}")
            except Exception as e:
                print(f"❌ 加载映射配置失败 {filename}: {str(e)}")
                
    return mappings

def main():
    print("=" * 70)
    print("创建 Elasticsearch 索引 Mapping")
    print("=" * 70)
    
    import argparse
    parser = argparse.ArgumentParser(description='创建 Elasticsearch 索引 Mapping')
    parser.add_argument('--host', default=ES_HOST, help='Elasticsearch 主机')
    parser.add_argument('--port', type=int, default=ES_PORT, help='Elasticsearch 端口')
    parser.add_argument('--user', default=ES_USER, help='Elasticsearch 用户名')
    parser.add_argument('--password', default=ES_PASSWORD, help='Elasticsearch 密码')
    parser.add_argument('--force', action='store_true', help='强制重新创建索引')
    args = parser.parse_args()
    
    es = get_es_client(args.host, args.port, args.user, args.password)
    if not es:
        print("❌ 无法连接到 Elasticsearch，退出")
        sys.exit(1)
    
    mappings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mappings')
    print(f"\n📁 加载映射配置目录: {mappings_dir}")
    
    indices = load_mappings_from_dir(mappings_dir)
    if not indices:
        print("❌ 未找到任何映射配置文件")
        es.close()
        sys.exit(1)
    
    print("\n--- 创建索引 ---")
    
    success_count = 0
    for index_name, mapping in indices:
        print(f"\n处理索引: {index_name}")
        if create_index(es, index_name, mapping, args.force):
            success_count += 1
    
    print(f"\n{'=' * 70}")
    print(f"创建完成: {success_count}/{len(indices)} 个索引")
    print(f"{'=' * 70}")
    
    es.close()

if __name__ == "__main__":
    main()
