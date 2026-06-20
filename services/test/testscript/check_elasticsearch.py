import os
import sys
from elasticsearch import Elasticsearch

def main():
    try:
        es = Elasticsearch(
            "http://localhost:19200",
            basic_auth=("elastic", "password")
        )
        
        if es.ping():
            print("成功连接到 Elasticsearch")
            
            indices = es.indices.get_alias("*")
            print("\n=== Elasticsearch 索引列表 ===")
            for index_name in sorted(indices.keys()):
                print(f"  - {index_name}")
            
            for index_name in indices.keys():
                try:
                    mapping = es.indices.get_mapping(index=index_name)
                    print(f"\n=== 索引 {index_name} 的映射 ===")
                    
                    mappings = mapping[index_name].get('mappings', {}).get('properties', {})
                    if mappings:
                        for field, props in mappings.items():
                            field_type = props.get('type', 'unknown')
                            print(f"  {field}: {field_type}")
                    else:
                        print("  无映射信息")
                    
                    sample_data = es.search(index=index_name, size=1)
                    if sample_data['hits']['total']['value'] > 0:
                        print("\n  示例数据:")
                        doc = sample_data['hits']['hits'][0]['_source']
                        import json
                        print(json.dumps(doc, ensure_ascii=False, indent=2))
                    else:
                        print("\n  无数据")
                        
                except Exception as e:
                    print(f"  无法获取索引 {index_name} 的信息: {e}")
                    
        else:
            print("无法连接到 Elasticsearch")
            
    except Exception as e:
        print(f"连接错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()