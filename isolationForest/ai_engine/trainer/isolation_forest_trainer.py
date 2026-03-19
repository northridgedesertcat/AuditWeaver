# -*- coding: utf-8 -*-
"""
Isolation Forest 训练器

功能：使用Isolation Forest算法训练Web应用攻击检测模型
"""

import os
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import matplotlib.pyplot as plt
from pathlib import Path

# 导入特征提取器
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../features/prototype_features'))
from feature_extractor import FeatureExtractor


class IsolationForestTrainer:
    """
    Isolation Forest 训练器类
    
    功能：训练Isolation Forest模型用于Web应用攻击检测
    """
    
    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        """
        初始化训练器
        
        参数:
            contamination: float - 异常值比例估计，默认0.1
            random_state: int - 随机种子
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model = None
        self.feature_extractor = FeatureExtractor()
        self.model_path = os.path.join(os.path.dirname(__file__), 'models')
        
        # 创建模型保存目录
        os.makedirs(self.model_path, exist_ok=True)
    
    def load_dataset(self, csv_path: str, sample_size: int = None) -> pd.DataFrame:
        """
        加载CSIC/ECML数据集
        
        参数:
            csv_path: str - CSV文件路径
            sample_size: int - 采样数量（用于测试）
        
        返回:
            pd.DataFrame - 数据集
        """
        print(f"正在加载数据集: {csv_path}")
        
        # 读取CSV文件
        df = pd.read_csv(csv_path)
        
        # 采样（用于快速测试）
        if sample_size and sample_size < len(df):
            df = df.sample(sample_size, random_state=self.random_state)
        
        print(f"数据集加载完成，共 {len(df)} 条记录")
        print(f"数据列: {df.columns.tolist()}")
        print(f"Class分布:\n{df['Class'].value_counts()}")
        
        return df
    
    def preprocess_data(self, df: pd.DataFrame) -> tuple:
        """
        预处理数据，提取URL特征
        
        参数:
            df: pd.DataFrame - 原始数据集
        
        返回:
            tuple - (特征矩阵, 标签数组)
        """
        print("开始预处理数据...")
        
        features_list = []
        labels = []
        
        for idx, row in df.iterrows():
            # 构建完整的URL（URI + GET参数 + POST数据）
            url_parts = [row['URI']]
            
            # 添加GET参数
            if pd.notna(row['GET-Query']) and row['GET-Query']:
                url_parts.append(f"?{row['GET-Query']}")
            
            # 添加POST数据（如果是POST请求）
            if row['Method'] == 'POST' and pd.notna(row['POST-Data']) and row['POST-Data']:
                url_parts.append(f"?{row['POST-Data']}")
            
            url = ''.join(url_parts)
            
            # 提取特征
            try:
                features = self.feature_extractor.extract(url)
                features_list.append(features)
                
                # 标签处理：Valid为正常(1)，Anomalous为异常(-1)
                if row['Class'] == 'Valid':
                    labels.append(1)  # 正常
                else:
                    labels.append(-1)  # 异常
                    
            except Exception as e:
                print(f"处理第 {idx} 条记录时出错: {e}")
                continue
        
        X = np.array(features_list)
        y = np.array(labels)
        
        print(f"特征提取完成，特征矩阵形状: {X.shape}")
        print(f"标签分布: 正常={np.sum(y == 1)}, 异常={np.sum(y == -1)}")
        
        return X, y
    
    def train(self, X: np.ndarray, y: np.ndarray = None, save_model: bool = True) -> dict:
        """
        训练Isolation Forest模型
        
        参数:
            X: np.ndarray - 特征矩阵
            y: np.ndarray - 标签数组（可选，用于评估）
            save_model: bool - 是否保存模型
        
        返回:
            dict - 训练结果
        """
        print("开始训练Isolation Forest模型...")
        
        # 创建Isolation Forest模型
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
            max_samples='auto'
        )
        
        # 训练模型
        self.model.fit(X)
        
        # 预测训练集
        y_pred = self.model.predict(X)
        
        # 计算异常分数
        anomaly_scores = self.model.decision_function(X)
        
        # 准备结果
        results = {
            'model_trained': True,
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'anomaly_ratio': np.sum(y_pred == -1) / len(y_pred),
            'anomaly_scores_stats': {
                'mean': np.mean(anomaly_scores),
                'std': np.std(anomaly_scores),
                'min': np.min(anomaly_scores),
                'max': np.max(anomaly_scores)
            }
        }
        
        # 如果有真实标签，计算评估指标
        if y is not None:
            results['evaluation'] = self.evaluate_model(X, y)
        
        # 保存模型
        if save_model:
            model_file = os.path.join(self.model_path, 'isolation_forest_model.pkl')
            joblib.dump(self.model, model_file)
            results['model_saved'] = model_file
            print(f"模型已保存到: {model_file}")
        
        print("模型训练完成!")
        return results
    
    def evaluate_model(self, X: np.ndarray, y_true: np.ndarray) -> dict:
        """
        评估模型性能
        
        参数:
            X: np.ndarray - 特征矩阵
            y_true: np.ndarray - 真实标签
        
        返回:
            dict - 评估结果
        """
        if self.model is None:
            raise ValueError("模型尚未训练，请先调用train方法")
        
        # 预测
        y_pred = self.model.predict(X)
        
        # 计算评估指标
        report = classification_report(y_true, y_pred, output_dict=True)
        cm = confusion_matrix(y_true, y_pred)
        
        return {
            'classification_report': report,
            'confusion_matrix': cm.tolist(),
            'accuracy': (y_pred == y_true).mean()
        }
    
    def plot_results(self, X: np.ndarray, y_true: np.ndarray = None, save_path: str = None):
        """
        可视化训练结果
        
        参数:
            X: np.ndarray - 特征矩阵
            y_true: np.ndarray - 真实标签（可选）
            save_path: str - 图片保存路径
        """
        if self.model is None:
            raise ValueError("模型尚未训练")
        
        # 计算异常分数
        anomaly_scores = self.model.decision_function(X)
        
        # 创建可视化
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # 1. 异常分数分布
        axes[0, 0].hist(anomaly_scores, bins=50, alpha=0.7, color='skyblue')
        axes[0, 0].set_title('异常分数分布')
        axes[0, 0].set_xlabel('异常分数')
        axes[0, 0].set_ylabel('频次')
        
        # 2. 预测结果
        y_pred = self.model.predict(X)
        if y_true is not None:
            axes[0, 1].scatter(anomaly_scores, y_true, alpha=0.5, c=y_pred, cmap='coolwarm')
            axes[0, 1].set_title('预测结果 vs 真实标签')
            axes[0, 1].set_xlabel('异常分数')
            axes[0, 1].set_ylabel('真实标签')
        
        # 3. 特征重要性（前2个特征）
        if X.shape[1] >= 2:
            axes[1, 0].scatter(X[:, 0], X[:, 1], c=anomaly_scores, cmap='viridis', alpha=0.6)
            axes[1, 0].set_title('特征空间分布（前2个特征）')
            axes[1, 0].set_xlabel('特征1')
            axes[1, 0].set_ylabel('特征2')
            plt.colorbar(axes[1, 0].collections[0], ax=axes[1, 0])
        
        # 4. 混淆矩阵（如果有真实标签）
        if y_true is not None:
            cm = confusion_matrix(y_true, y_pred)
            im = axes[1, 1].imshow(cm, cmap='Blues', interpolation='nearest')
            axes[1, 1].set_title('混淆矩阵')
            axes[1, 1].set_xlabel('预测标签')
            axes[1, 1].set_ylabel('真实标签')
            
            # 添加数值标签
            for i in range(cm.shape[0]):
                for j in range(cm.shape[1]):
                    axes[1, 1].text(j, i, str(cm[i, j]), 
                                   ha='center', va='center', 
                                   color='white' if cm[i, j] > cm.max()/2 else 'black')
            
            plt.colorbar(im, ax=axes[1, 1])
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"可视化结果已保存到: {save_path}")
        
        plt.show()
    
    def save_training_report(self, results: dict, save_path: str = None):
        """
        保存训练报告
        
        参数:
            results: dict - 训练结果
            save_path: str - 保存路径
        """
        if save_path is None:
            save_path = os.path.join(self.model_path, 'training_report.json')
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"训练报告已保存到: {save_path}")


def main():
    """主函数：完整的训练流程"""
    # 创建训练器
    trainer = IsolationForestTrainer(contamination=0.1)
    
    # 数据集路径
    dataset_path = os.path.join(
        os.path.dirname(__file__), 
        '../../logs/Web-Application-Attack-Datasets/CSVData/csic_ecml_final.csv'
    )
    
    try:
        # 1. 加载数据集
        df = trainer.load_dataset(dataset_path, sample_size=1000)  # 采样1000条用于测试
        
        # 2. 预处理数据
        X, y = trainer.preprocess_data(df)
        
        # 3. 训练模型
        results = trainer.train(X, y, save_model=True)
        
        # 4. 保存训练报告
        trainer.save_training_report(results)
        
        # 5. 可视化结果
        trainer.plot_results(X, y, save_path=os.path.join(trainer.model_path, 'training_results.png'))
        
        print("\n=== 训练完成 ===")
        print(f"模型文件: {results.get('model_saved', 'N/A')}")
        print(f"异常比例: {results['anomaly_ratio']:.3f}")
        
        if 'evaluation' in results:
            print(f"准确率: {results['evaluation']['accuracy']:.3f}")
        
    except Exception as e:
        print(f"训练过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()