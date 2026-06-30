#!/usr/bin/env python
"""测试后端API的ReportList接口"""

import requests

def test_report_list_api():
    print("=" * 70)
    print("测试 ReportList API 接口")
    print("=" * 70)
    
    base_url = 'http://localhost:8000/api/v1'
    
    print(f"\n1. 测试健康检查:")
    try:
        response = requests.get(f"{base_url}/health/")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.json()}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
        return
    
    print("\n2. 测试报告统计:")
    try:
        response = requests.get(f"{base_url}/reports/stats/")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.json()}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    print("\n3. 测试报告列表:")
    try:
        response = requests.get(f"{base_url}/reports/list/?page=1&size=10")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   total: {data.get('total', 'N/A')}")
            print(f"   data length: {len(data.get('data', []))}")
            if data.get('data'):
                print(f"   第一条数据: {data['data'][0]}")
        else:
            print(f"   错误响应: {response.text}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n4. 测试威胁分布:")
    try:
        response = requests.get(f"{base_url}/dashboard/threat-distribution/?range=all")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   total: {data.get('total', 'N/A')}")
            print(f"   data: {data.get('data', {})}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_report_list_api()