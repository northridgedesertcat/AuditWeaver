import pandas as pd
import os
import sys
from sklearn.model_selection import train_test_split

class DataSplitter:
    @staticmethod
    def load_data(data_path):
        """加载特征数据
        
        Args:
            data_path: 特征数据文件路径
            
        Returns:
            pd.DataFrame: 加载的数据
        """
        print(f"Loading data from {data_path}...")
        df = pd.read_csv(data_path)
        print(f"Loaded {len(df)} samples with {len(df.columns)} features")
        return df
    
    @staticmethod
    def split_data(df, test_size=0.3, random_state=42, stratify=None):
        """拆分数据为训练集和测试集
        
        Args:
            df: 输入数据
            test_size: 测试集比例
            random_state: 随机种子
            stratify: 分层抽样的标签列
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test) 或 (X_train, X_test) 如果没有标签
        """
        print(f"Splitting data with test size: {test_size}")
        
        # 检查是否有标签列
        if 'Class' in df.columns:
            labels = df['Class'].map({'Valid': 0, 'Anomaly': 1, 'Anomalous': 1})
            features = df.drop(columns=['Class'])
            
            # 移除标签为 NaN 的样本
            mask = labels.notna()
            if not mask.all():
                print(f"Removing {len(labels) - mask.sum()} samples with NaN labels")
                features = features[mask]
                labels = labels[mask]
            
            # 分层抽样
            stratify_param = labels if stratify else None
            
            X_train, X_test, y_train, y_test = train_test_split(
                features, labels, test_size=test_size, random_state=random_state, stratify=stratify_param
            )
            
            print(f"Training set size: {len(X_train)}")
            print(f"Test set size: {len(X_test)}")
            
            if stratify:
                print("\nTraining set label distribution:")
                print(y_train.value_counts())
                print("\nTest set label distribution:")
                print(y_test.value_counts())
            
            return X_train, X_test, y_train, y_test
        else:
            # 无标签数据
            X_train, X_test = train_test_split(
                df, test_size=test_size, random_state=random_state
            )
            
            print(f"Training set size: {len(X_train)}")
            print(f"Test set size: {len(X_test)}")
            
            return X_train, X_test
    
    @staticmethod
    def save_split_data(X_train, X_test, y_train=None, y_test=None, output_dir=None):
        """保存拆分后的数据
        
        Args:
            X_train: 训练集特征
            X_test: 测试集特征
            y_train: 训练集标签
            y_test: 测试集标签
            output_dir: 输出目录
        """
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存训练集
            if y_train is not None:
                train_df = X_train.copy()
                train_df['Class'] = y_train.map({0: 'Valid', 1: 'Anomaly'})
                train_path = os.path.join(output_dir, 'train_data.csv')
                train_df.to_csv(train_path, index=False)
                print(f"Training data saved to {train_path}")
            else:
                train_path = os.path.join(output_dir, 'train_data.csv')
                X_train.to_csv(train_path, index=False)
                print(f"Training data saved to {train_path}")
            
            # 保存测试集
            if y_test is not None:
                test_df = X_test.copy()
                test_df['Class'] = y_test.map({0: 'Valid', 1: 'Anomaly'})
                test_path = os.path.join(output_dir, 'test_data.csv')
                test_df.to_csv(test_path, index=False)
                print(f"Test data saved to {test_path}")
            else:
                test_path = os.path.join(output_dir, 'test_data.csv')
                X_test.to_csv(test_path, index=False)
                print(f"Test data saved to {test_path}")
    
    @staticmethod
    def load_split_data(train_path, test_path):
        """加载拆分后的数据
        
        Args:
            train_path: 训练集路径
            test_path: 测试集路径
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test) 或 (X_train, X_test) 如果没有标签
        """
        # 加载训练集
        print(f"Loading training data from {train_path}...")
        train_df = pd.read_csv(train_path)
        
        # 加载测试集
        print(f"Loading test data from {test_path}...")
        test_df = pd.read_csv(test_path)
        
        # 检查是否有标签列
        if 'Class' in train_df.columns and 'Class' in test_df.columns:
            y_train = train_df['Class'].map({'Valid': 0, 'Anomaly': 1, 'Anomalous': 1})
            X_train = train_df.drop(columns=['Class'])
            
            y_test = test_df['Class'].map({'Valid': 0, 'Anomaly': 1, 'Anomalous': 1})
            X_test = test_df.drop(columns=['Class'])
            
            print(f"Loaded {len(X_train)} training samples and {len(X_test)} test samples")
            return X_train, X_test, y_train, y_test
        else:
            X_train = train_df
            X_test = test_df
            print(f"Loaded {len(X_train)} training samples and {len(X_test)} test samples")
            return X_train, X_test


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "datas", "extracted_features.csv")
    output_dir = os.path.join(base_dir, "datas", "split")
    
    # 加载数据
    df = DataSplitter.load_data(data_path)
    
    # 拆分数据（70%训练，30%测试）
    X_train, X_test, y_train, y_test = DataSplitter.split_data(
        df, test_size=0.3, random_state=42, stratify=True
    )
    
    # 保存拆分后的数据
    DataSplitter.save_split_data(X_train, X_test, y_train, y_test, output_dir)
    
    print("\nData splitting completed successfully!")