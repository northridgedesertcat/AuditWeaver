import os
import sys
import pandas as pd
import pickle
import numpy as np

# 计算项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
isolation_forest_dir = os.path.dirname(current_dir)

# 添加项目根目录到Python路径
sys.path.append(isolation_forest_dir)

class ModelLauncher:
    def __init__(self, model_path, model_config_path):
        """初始化模型加载器
        
        Args:
            model_path: 模型文件路径
            model_config_path: 模型配置文件路径
        """
        self.model_path = model_path
        self.model_config_path = model_config_path
        self.model = None
        self.config = None
    
    def load_model(self):
        """加载模型和配置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            # 加载模型
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            
            # 加载配置
            with open(self.model_config_path, 'rb') as f:
                self.config = pickle.load(f)
            
            print(f"Model loaded successfully from {self.model_path}")
            print(f"Model config: {self.config}")
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def load_features(self, features_path):
        """加载特征数据
        
        Args:
            features_path: 特征文件路径
        
        Returns:
            pd.DataFrame: 特征数据
        """
        try:
            df = pd.read_csv(features_path)
            print(f"Loaded features from {features_path}")
            print(f"Shape: {df.shape}")
            return df
        except Exception as e:
            print(f"Error loading features: {e}")
            return None
    
    def preprocess_features(self, df):
        """预处理特征数据
        
        Args:
            df: 原始特征数据
        
        Returns:
            pd.DataFrame: 预处理后的特征数据
        """
        # 保留与模型训练时相同的特征
        # 移除可能存在的非特征列
        features_to_keep = [
            'method_is_get', 'method_is_post',
            'uri_length', 'uri_depth', 'has_query', 'query_length', 'special_char_count', 'digit_ratio',
            'url_encoded_count', 'has_double_encoding',
            'path_traversal_count', 'has_sensitive_file',
            'has_cmd_keyword', 'has_sql_keyword',
            'is_binary_request',
            'status_code', 'is_4xx', 'is_5xx',
            'user_agent_length', 'is_empty_user_agent', 'is_bot_user_agent'
        ]
        
        # 确保所有特征都存在
        for feature in features_to_keep:
            if feature not in df.columns:
                df[feature] = 0
        
        # 只保留需要的特征
        df = df[features_to_keep]
        return df
    
    def detect_anomalies(self, features_df):
        """检测异常
        
        Args:
            features_df: 特征数据
        
        Returns:
            tuple: (预测结果, 异常分数)
        """
        try:
            # 预测异常
            predictions = self.model.predict(features_df)
            # 获取异常分数
            scores = self.model.score_samples(features_df)
            return predictions, scores
        except Exception as e:
            print(f"Error detecting anomalies: {e}")
            return None, None
    
    def save_results(self, features_df, predictions, scores, output_path):
        """保存检测结果
        
        Args:
            features_df: 原始特征数据
            predictions: 预测结果
            scores: 异常分数
            output_path: 输出文件路径
        """
        try:
            # 创建结果DataFrame
            results_df = features_df.copy()
            results_df['anomaly'] = predictions
            results_df['anomaly_score'] = scores
            
            # 将-1转换为1（异常），1转换为0（正常）
            results_df['anomaly'] = results_df['anomaly'].apply(lambda x: 1 if x == -1 else 0)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存结果
            results_df.to_csv(output_path, index=False)
            print(f"Results saved to {output_path}")
            
            # 统计异常数量
            anomaly_count = results_df['anomaly'].sum()
            total_count = len(results_df)
            print(f"Anomaly detection completed:")
            print(f"Total samples: {total_count}")
            print(f"Anomalies detected: {anomaly_count}")
            print(f"Anomaly ratio: {anomaly_count/total_count:.2f}")
            
            return results_df
        except Exception as e:
            print(f"Error saving results: {e}")
            return None
    
    def run(self, features_path, output_path):
        """运行整个检测流程
        
        Args:
            features_path: 特征文件路径
            output_path: 输出文件路径
        """
        # 加载模型
        if not self.load_model():
            return
        
        # 加载特征
        features_df = self.load_features(features_path)
        if features_df is None:
            return
        
        # 预处理特征
        processed_features = self.preprocess_features(features_df)
        
        # 检测异常
        predictions, scores = self.detect_anomalies(processed_features)
        if predictions is None or scores is None:
            return
        
        # 保存结果
        self.save_results(features_df, predictions, scores, output_path)

if __name__ == "__main__":
    # 路径设置
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "models", "isolation_forest_model.pkl")
    model_config_path = os.path.join(base_dir, "models", "isolation_forest_model_config.pkl")
    features_path = os.path.join(base_dir, "datas", "features", "nginx", "nginx_features.csv")
    output_dir = os.path.join(base_dir, "datas", "result", "nginx")
    output_path = os.path.join(output_dir, "nginx_anomaly_results.csv")
    
    # 创建模型加载器
    launcher = ModelLauncher(model_path, model_config_path)
    
    # 运行检测
    launcher.run(features_path, output_path)
