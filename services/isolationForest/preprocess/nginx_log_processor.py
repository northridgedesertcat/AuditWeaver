import re
import os
import sys
import pandas as pd

# 添加项目路径到Python路径
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from trainer.features.features_extractor import FeaturesExtractor

class NginxLogProcessor:
    def __init__(self):
        # Nginx日志格式的正则表达式
        self.log_pattern = re.compile(
            r'(?P<ip>\S+) - - \[(?P<timestamp>[^\]]+)\] "(?P<request>[^"]*)" '  
            r'(?P<status>\d+) (?P<size>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
        )
    
    def parse_log_line(self, line):
        """解析单行Nginx日志
        
        Args:
            line: 日志行
            
        Returns:
            dict: 解析后的日志信息
        """
        match = self.log_pattern.match(line)
        if not match:
            return None
        
        groups = match.groupdict()
        
        # 解析请求行
        request = groups['request']
        request_parts = request.split(' ', 2)
        
        if len(request_parts) >= 2:
            method = request_parts[0]
            uri = request_parts[1]
        else:
            method = 'GET'
            uri = request
        
        # 构建日志条目字典
        log_entry = {
            'ip': groups.get('ip', ''),
            'timestamp': groups.get('timestamp', ''),
            'method': method,
            'uri': uri,
            'status': groups.get('status', '200'),
            'size': groups.get('size', '0'),
            'referrer': groups.get('referrer', ''),
            'user_agent': groups.get('user_agent', '')
        }
        
        return log_entry
    
    def process_log_file(self, input_path, output_path):
        """处理Nginx日志文件
        
        Args:
            input_path: 输入日志文件路径
            output_path: 输出特征文件路径
        
        Returns:
            pd.DataFrame: 提取的特征
        """
        print(f"Processing Nginx log file: {input_path}")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        features_list = []
        
        try:
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        log_entry = self.parse_log_line(line)
                        if log_entry:
                            # 提取特征
                            features = FeaturesExtractor.extract_features(log_entry)
                            # 添加原始信息
                            features['ip'] = log_entry['ip']
                            features['timestamp'] = log_entry['timestamp']
                            features['size'] = log_entry['size']
                            features['referrer'] = log_entry['referrer']
                            features_list.append(features)
                        
                        if line_num % 1000 == 0:
                            print(f"Processed {line_num} lines")
        except Exception as e:
            print(f"Error reading log file: {e}")
            return None
        
        print(f"Total processed lines: {len(features_list)}")
        
        # 保存特征
        if features_list:
            features_df = pd.DataFrame(features_list)
            features_df.to_csv(output_path, index=False)
            print(f"Features saved to: {output_path}")
            print(f"Extracted {len(features_df.columns)} features")
            return features_df
        else:
            print("No valid log entries found")
            return None

if __name__ == "__main__":
    # 路径设置
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "datas", "raw", "nginx", "腾讯云_nginx-all.log")
    output_dir = os.path.join(base_dir, "datas", "features", "nginx")
    output_path = os.path.join(output_dir, "nginx_features.csv")
    
    # 创建处理器实例
    processor = NginxLogProcessor()
    
    # 处理日志文件
    processor.process_log_file(input_path, output_path)
