#!/usr/bin/env python
"""检查 Dify 服务运行状态和端口"""

import requests
import subprocess

def check_dify():
    print("=" * 70)
    print("检查 Dify 服务状态")
    print("=" * 70)
    
    # 测试常见的 Dify 端口
    ports = [8080, 80, 3000, 5000]
    
    for port in ports:
        url = f"http://localhost:{port}/v1/workflows/run"
        try:
            response = requests.get(url, timeout=5)
            print(f"   ✅ 端口 {port}: 有响应 (状态码: {response.status_code})")
            print(f"      URL: {url}")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ 端口 {port}: 连接被拒绝")
        except requests.exceptions.Timeout:
            print(f"   ⏱️ 端口 {port}: 连接超时")
        except Exception as e:
            print(f"   ❓ 端口 {port}: {e}")
    
    print("\n--- 检查 Docker 容器 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker ps --format '{{{{.Names}}}}\\t{{{{.Ports}}}}'"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'dify' in line.lower() or 'api' in line.lower():
                    print(f"   {line}")
    except Exception as e:
        print(f"   ❌ 检查 Docker 失败: {e}")
    
    print("\n--- 当前 Dify 配置 ---")
    print("   base_url: http://localhost/v1")
    print("   实际请求地址: http://localhost:80/v1/workflows/run")
    print("\n   ✅ 应该改为: http://localhost:8080/v1")
    print("   ✅ 实际请求地址: http://localhost:8080/v1/workflows/run")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_dify()