#!/usr/bin/env python
"""检查网络配置和 Docker 网络"""

import subprocess
import socket

def check_network():
    print("=" * 70)
    print("检查网络配置")
    print("=" * 70)
    
    # 获取本机 IP
    print("\n--- 本机网络信息 ---")
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        print(f"   主机名: {hostname}")
        print(f"   本地 IP: {ip}")
    except Exception as e:
        print(f"   ❌ 获取网络信息失败: {e}")
    
    # 检查 Docker 网络
    print("\n--- Docker 网络 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker network ls"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"   Docker 网络列表:")
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    print(f"     {line.strip()}")
    except Exception as e:
        print(f"   ❌ 检查 Docker 网络失败: {e}")
    
    # 检查所有运行中的容器
    print("\n--- 运行中的容器 ---")
    try:
        result = subprocess.run(
            ["powershell", "-Command", "docker ps --format '{{{{.Names}}}}\\t{{{{.Ports}}}}\\t{{{{.Networks}}}}'"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            print(f"   {'容器名称':<30} {'端口映射':<60} {'网络'}")
            print(f"   {'-'*30:<30} {'-'*60:<60} {'-'*20}")
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 3:
                    name, ports, network = parts[0], parts[1], parts[2]
                    print(f"   {name:<30} {ports:<60} {network}")
    except Exception as e:
        print(f"   ❌ 检查容器失败: {e}")
    
    # 测试使用宿主机 IP 访问 Dify
    print("\n--- 测试使用宿主机 IP 访问 Dify ---")
    try:
        import requests
        response = requests.post(
            f"http://{ip}:80/v1/workflows/run",
            json={"test": "data"},
            headers={"Authorization": "Bearer test-token"},
            timeout=10
        )
        print(f"   http://{ip}:80/v1/workflows/run: 状态码 {response.status_code}")
    except Exception as e:
        print(f"   ❌ 使用宿主机 IP 访问失败: {e}")
    
    print("\n--- 问题分析 ---")
    print("   如果 agent 运行在 Docker 容器中:")
    print("     - 容器内的 'localhost' 指向容器自身")
    print("     - 需要使用宿主机 IP 或 Docker 网络别名")
    print("     - 例如: http://host.docker.internal:80/v1")
    print("     - 或: http://宿主机IP:80/v1")
    print("\n   当前配置:")
    print("     base_url: http://localhost/v1")
    print("     agent 实际请求: http://localhost:80/v1/workflows/run")
    print("\n   解决方案:")
    print("     将 base_url 改为 http://宿主机IP:80/v1")
    print("     或 http://host.docker.internal:80/v1")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_network()