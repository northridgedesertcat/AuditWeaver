import pandas as pd
import numpy as np
import joblib
import os
import sys

# 添加项目路径到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trainer.features.features_extractor import FeaturesExtractor

class ModelLaucher:
    def __init__(self, model_path=None):
        self.model = None
        self.config = None
        self.feature_columns = None
        
        if model_path:
            self.load_model(model_path)
    
    def load_model(self, model_path):
        """加载训练好的模型
        
        Args:
            model_path: 模型文件路径
        """
        print(f"Loading model from {model_path}...")
        try:
            self.model = joblib.load(model_path)
            
            # 加载模型配置
            config_path = model_path.replace('.pkl', '_config.pkl')
            if os.path.exists(config_path):
                self.config = joblib.load(config_path)
                self.feature_columns = self.config.get('feature_columns')
                print(f"Model config loaded: contamination={self.config.get('contamination')}, "
                      f"n_estimators={self.config.get('n_estimators')}")
            print("Model loaded successfully")
            return self.model
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    
    def extract_features(self, log_entry):
        """从日志条目中提取特征
        
        Args:
            log_entry: 包含日志信息的字典
            
        Returns:
            pd.DataFrame: 提取的特征
        """
        features = FeaturesExtractor.extract_features(log_entry)
        features_df = pd.DataFrame([features])
        
        # 确保特征列顺序与模型训练时一致
        if self.feature_columns:
            features_df = features_df[self.feature_columns]
        
        return features_df
    
    def predict(self, features):
        """使用模型进行预测
        
        Args:
            features: 特征数据
            
        Returns:
            tuple: (预测结果, 异常分数)
        """
        if self.model is None:
            print("No model loaded!")
            return None, None
        
        predictions = self.model.predict(features)
        scores = self.model.score_samples(features)
        
        return predictions, scores
    
    def process_log_entry(self, log_entry):
        """处理单个日志条目
        
        Args:
            log_entry: 包含日志信息的字典
            
        Returns:
            dict: 包含预测结果的字典
        """
        # 提取特征
        features = self.extract_features(log_entry)
        
        # 预测
        predictions, scores = self.predict(features)
        
        if predictions is not None:
            is_anomaly = predictions[0] == -1  # -1 表示异常
            anomaly_score = scores[0]  # 分数越低越异常
            
            return {
                'is_anomaly': is_anomaly,
                'anomaly_score': anomaly_score,
                'log_entry': log_entry
            }
        return None
    
    def process_log_file(self, log_file_path, output_path=None):
        """处理日志文件
        
        Args:
            log_file_path: 日志文件路径
            output_path: 输出结果路径
            
        Returns:
            pd.DataFrame: 包含预测结果的数据
        """
        print(f"Processing log file: {log_file_path}")
        
        # 加载日志文件
        try:
            # 假设日志文件是CSV格式
            df = pd.read_csv(log_file_path)
            print(f"Loaded {len(df)} log entries")
        except Exception as e:
            print(f"Error loading log file: {e}")
            return None
        
        # 处理每一行日志
        results = []
        total = len(df)
        
        for i, (_, row) in enumerate(df.iterrows()):
            if (i + 1) % 100 == 0:
                print(f"Processing log entry {i + 1}/{total}")
            
            # 构建日志条目字典
            log_entry = {
                'method': str(row.get('Method', '')),
                'uri': str(row.get('URI', '')),
                'query': str(row.get('GET-Query', '')),
                'post_data': str(row.get('POST-Data', '')),
                'content': str(row.get('Content-Length', '')),
                'cookie': str(row.get('Cookie', '')),
                'user_agent': str(row.get('User-Agent', ''))
            }
            
            # 处理日志条目
            result = self.process_log_entry(log_entry)
            if result:
                results.append(result)
        
        # 转换为DataFrame
        results_df = pd.DataFrame(results)
        print(f"Processed {len(results_df)} log entries")
        
        # 保存结果
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            results_df.to_csv(output_path, index=False)
            print(f"Results saved to {output_path}")
        
        return results_df
    
    def analyze_results(self, results_df):
        """分析预测结果
        
        Args:
            results_df: 包含预测结果的数据
        """
        if results_df is None or len(results_df) == 0:
            print("No results to analyze")
            return
        
        # 统计异常和正常的数量
        anomaly_count = results_df['is_anomaly'].sum()
        normal_count = len(results_df) - anomaly_count
        
        print("\n" + "=" * 60)
        print("PREDICTION ANALYSIS")
        print("=" * 60)
        print(f"Total log entries: {len(results_df)}")
        print(f"Anomaly count: {anomaly_count} ({anomaly_count/len(results_df)*100:.2f}%)")
        print(f"Normal count: {normal_count} ({normal_count/len(results_df)*100:.2f}%)")
        
        # 显示最异常的前10个日志
        if anomaly_count > 0:
            print("\n" + "-" * 40)
            print("TOP 10 MOST ANOMALOUS LOGS")
            print("-" * 40)
            top_anomalies = results_df[results_df['is_anomaly']].sort_values('anomaly_score').head(10)
            
            for i, (_, row) in enumerate(top_anomalies.iterrows(), 1):
                print(f"{i}. Score: {row['anomaly_score']:.4f}")
                log_entry = row['log_entry']
                print(f"   Method: {log_entry.get('method')}")
                print(f"   URI: {log_entry.get('uri')}")
                print(f"   Query: {log_entry.get('query')[:50]}...")
                print()


def main():
    # 默认路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "models", "isolation_forest_model.pkl")
    log_file_path = os.path.join(base_dir, "trainer", "datas", "csic_final.csv")
    output_path = os.path.join(base_dir, "results", "log_analysis_results.csv")
    
    # 创建启动器
    laucher = ModelLaucher(model_path)
    
    # 处理日志文件
    results_df = laucher.process_log_file(log_file_path, output_path)
    
    # 分析结果
    laucher.analyze_results(results_df)


if __name__ == "__main__":
    main()
