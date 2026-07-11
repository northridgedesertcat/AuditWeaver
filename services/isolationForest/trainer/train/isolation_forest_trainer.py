import os
import sys
import pandas as pd
import pickle
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split

# 计算项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
trainer_dir = os.path.dirname(current_dir)
isolation_forest_dir = os.path.dirname(trainer_dir)

# 添加项目根目录到Python路径
sys.path.append(isolation_forest_dir)

class IsolationForestTrainer:
    def __init__(self, features_path, model_path, model_config_path):
        """初始化训练器
        
        Args:
            features_path: 特征文件路径
            model_path: 模型保存路径
            model_config_path: 模型配置保存路径
        """
        self.features_path = features_path
        self.model_path = model_path
        self.model_config_path = model_config_path
    
    def load_features(self):
        """加载特征数据
        
        Returns:
            pd.DataFrame: 特征数据
        """
        try:
            df = pd.read_csv(self.features_path)
            print(f"Loaded features from {self.features_path}")
            print(f"Shape: {df.shape}")
            return df
        except Exception as e:
            print(f"Error loading features: {e}")
            return None
    
    def prepare_data(self, df):
        """准备训练数据
        
        Args:
            df: 特征数据
        
        Returns:
            tuple: (X_train, X_test)
        """
        # 提取特征列（排除Class列）
        feature_columns = [col for col in df.columns if col != 'Class']
        X = df[feature_columns]
        
        # 分割数据
        X_train, X_test = train_test_split(X, test_size=0.2, random_state=42)
        print(f"Training data shape: {X_train.shape}")
        print(f"Testing data shape: {X_test.shape}")
        return X_train, X_test
    
    def train_model(self, X_train):
        """训练模型
        
        Args:
            X_train: 训练数据
        
        Returns:
            IsolationForest: 训练好的模型
        """
        # 配置模型参数
        config = {
            'n_estimators': 100,
            'contamination': 0.1,
            'random_state': 42
        }
        
        print(f"Training model with config: {config}")
        
        # 创建并训练模型
        model = IsolationForest(
            n_estimators=config['n_estimators'],
            contamination=config['contamination'],
            random_state=config['random_state']
        )
        model.fit(X_train)
        
        print("Model training completed")
        return model, config
    
    def save_model(self, model, config):
        """保存模型和配置
        
        Args:
            model: 训练好的模型
            config: 模型配置
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            # 保存模型
            with open(self.model_path, 'wb') as f:
                pickle.dump(model, f)
            
            # 保存配置
            with open(self.model_config_path, 'wb') as f:
                pickle.dump(config, f)
            
            print(f"Model saved to {self.model_path}")
            print(f"Config saved to {self.model_config_path}")
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def run(self):
        """运行整个训练流程
        """
        # 加载特征
        df = self.load_features()
        if df is None:
            return
        
        # 准备数据
        X_train, X_test = self.prepare_data(df)
        
        # 训练模型
        model, config = self.train_model(X_train)
        
        # 保存模型
        self.save_model(model, config)

if __name__ == "__main__":
    # 路径设置
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    features_path = os.path.join(base_dir, "trainer", "datas", "extracted_features.csv")
    model_path = os.path.join(base_dir, "models", "isolation_forest_model.pkl")
    model_config_path = os.path.join(base_dir, "models", "isolation_forest_model_config.pkl")
    
    # 创建训练器
    trainer = IsolationForestTrainer(features_path, model_path, model_config_path)
    
    # 运行训练
    trainer.run()
