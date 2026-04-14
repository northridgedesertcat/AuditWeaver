import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from features_extractor import FeaturesExtractor

class DataProcessor:
    @staticmethod
    def load_csv(csv_path):
        """加载CSV文件
        
        Args:
            csv_path: CSV文件路径
        
        Returns:
            pd.DataFrame: 加载的数据
        """
        try:
            df = pd.read_csv(csv_path)
            print(f"Loaded {len(df)} rows from {csv_path}")
            return df
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return None
    
    @staticmethod
    def process_row(row):
        """处理单行数据
        
        Args:
            row: 数据行
        
        Returns:
            dict: 提取的特征
        """
        log_entry = {
            'method': str(row.get('Method', '')),
            'uri': str(row.get('URI', '')),
            'query': str(row.get('GET-Query', '')),
            'post_data': str(row.get('POST-Data', '')),
            'content': str(row.get('Content-Length', '')),
            'cookie': str(row.get('Cookie', '')),
            'user_agent': str(row.get('User-Agent', ''))
        }
        return FeaturesExtractor.extract_features(log_entry)
    
    @staticmethod
    def process_data(df):
        """处理数据集
        
        Args:
            df: 输入数据
        
        Returns:
            pd.DataFrame: 提取的特征（包含Class标签）
        """
        features_list = []
        total_rows = len(df)
        
        for i, (_, row) in enumerate(df.iterrows()):
            if (i + 1) % 1000 == 0:
                print(f"Processing row {i + 1}/{total_rows}")
            
            features = DataProcessor.process_row(row)
            # 保留原始标签
            if 'Class' in row:
                class_val = row['Class']
                # 只保留 Valid 或 Anomaly 标签
                if pd.notna(class_val) and class_val in ['Valid', 'Anomalous']:
                    features['Class'] = class_val
            features_list.append(features)
        
        features_df = pd.DataFrame(features_list)
        # 删除没有标签的行
        features_df = features_df.dropna(subset=['Class'])
        print(f"Extracted features for {len(features_df)} rows (with valid labels)")
        return features_df
    
    @staticmethod
    def save_features(features_df, output_path):
        """保存特征到文件
        
        Args:
            features_df: 特征数据
            output_path: 输出路径
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            features_df.to_csv(output_path, index=False)
            print(f"Features saved to {output_path}")
        except Exception as e:
            print(f"Error saving features: {e}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "datas", "csic_final.csv")
    output_path = os.path.join(base_dir, "datas", "extracted_features.csv")
    
    df = DataProcessor.load_csv(csv_path)
    if df is not None:
        features_df = DataProcessor.process_data(df)
        DataProcessor.save_features(features_df, output_path)