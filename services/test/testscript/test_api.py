import requests

def test_api():
    print("Testing API endpoints...")
    base_url = "http://localhost:8000/api/v1"
    
    endpoints = [
        "/health/",
        "/dashboard/stats/",
        "/logs/",
        "/logs/stats/",
        "/alerts/",
        "/incidents/",
        "/anomalies/",
        "/infrastructure/servers/",
        "/threats/",
        "/ai/models/",
    ]
    
    for endpoint in endpoints:
        try:
            url = base_url + endpoint
            response = requests.get(url)
            print(f"{endpoint}: Status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    if 'data' in data:
                        print(f"  - 返回数据条数: {len(data['data'])}")
                    elif 'total' in data:
                        print(f"  - 总数: {data.get('total', 0)}")
                    else:
                        print(f"  - 包含字段: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"  - 返回数据条数: {len(data)}")
                else:
                    print(f"  - 返回: {data}")
        except Exception as e:
            print(f"{endpoint}: Error - {e}")

if __name__ == "__main__":
    test_api()