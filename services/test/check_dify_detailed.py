#!/usr/bin/env python
"""详细检查 Dify 服务"""

import requests

def check_dify_detailed():
    print("=" * 70)
    print("详细检查 Dify 服务")
    print("=" * 70)
    
    # 测试端口 80 上的服务
    print("\n--- 测试端口 80 ---")
    url = "http://localhost:80/v1/workflows/run"
    
    # 测试 POST 请求（与 agent 相同的方式）
    try:
        response = requests.post(url, json={"test": "data"}, timeout=10)
        print(f"   POST 请求: 状态码 {response.status_code}")
        print(f"   响应头: {dict(response.headers) if len(response.headers) < 10 else {k: v for k, v in list(response.headers.items())[:10]}}")
        print(f"   响应体: {response.text[:200]}")
    except requests.exceptions.Timeout:
        print(f"   ❌ POST 请求超时")
    except Exception as e:
        print(f"   ❌ POST 请求失败: {e}")
    
    # 测试 GET 请求
    try:
        response = requests.get("http://localhost:80/", timeout=5)
        print(f"\n   GET /: 状态码 {response.status_code}")
        print(f"   响应体前500字符: {response.text[:500]}")
    except Exception as e:
        print(f"   ❌ GET / 失败: {e}")
    
    # 测试端口 3000
    print("\n--- 测试端口 3000 ---")
    try:
        response = requests.get("http://localhost:3000/", timeout=5)
        print(f"   GET /: 状态码 {response.status_code}")
        print(f"   响应体前500字符: {response.text[:500]}")
    except Exception as e:
        print(f"   ❌ GET / 失败: {e}")
    
    # 测试可能的 Dify API 路径
    print("\n--- 测试常见 API 路径 ---")
    paths = [
        "/v1/chat-messages",
        "/v1/workflows/run",
        "/api/v1/workflows/run",
        "/",
    ]
    
    for path in paths:
        url = f"http://localhost:80{path}"
        try:
            response = requests.get(url, timeout=5)
            print(f"   GET {path}: 状态码 {response.status_code}")
        except Exception as e:
            print(f"   GET {path}: {e}")
    
    print("\n--- 分析 ---")
    print("   端口 80 上有服务在运行，但返回 405 (Method Not Allowed)")
    print("   这可能是一个反向代理（如 nginx）")
    print("   需要确认 Dify API 的实际地址")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_dify_detailed()