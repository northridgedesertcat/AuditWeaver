# -*- coding: utf-8 -*-
"""
训练器测试脚本
"""

import os
import sys
import io

# 设置标准输出编码为UTF-8
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../features/prototype_features'))

from isolation_forest_trainer import IsolationForestTrainer


def test_feature_extractor():
    """测试特征提取器"""
    print("=== 测试特征提取器 ===")
    
    from feature_extractor import FeatureExtractor
    
    extractor = FeatureExtractor()
    
    # 测试URL
    test_urls = [
        "/tienda1/publico/anadir.jsp?id=1 OR 1=1",
        "/search?q=<script>alert('xss')</script>",
        "/api?cmd=whoami",
        "/files/../../../etc/passwd",
        "/normal/path/to/resource"
    ]
    
    for url in test_urls:
        features = extractor.extract(url)
        print(f"URL: {url[:50]}...")
        print(f"特征: {features}")
        print()


def test_data_loading():
    """测试数据加载"""
    print("=== 测试数据加载 ===")
    
    trainer = IsolationForestTrainer()
    
    # 数据集路径
    dataset_path = os.path.join(
        os.path.dirname(__file__), 
        '../../logs/Web-Application-Attack-Datasets/CSVData/csic_ecml_final.csv'
    )
    
    # 加载少量数据进行测试
    df = trainer.load_dataset(dataset_path, sample_size=100)
    print(f"数据加载成功，样本数: {len(df)}")
    
    # 测试特征提取
    X, y = trainer.preprocess_data(df)
    print(f"特征矩阵形状: {X.shape}")
    print(f"标签分布: 正常={sum(y == 1)}, 异常={sum(y == -1)}")
    
    return X, y


def test_training():
    """测试模型训练"""
    print("=== 测试模型训练 ===")
    
    X, y = test_data_loading()
    
    trainer = IsolationForestTrainer(contamination=0.1)
    
    # 训练模型
    results = trainer.train(X, y, save_model=True)
    
    print("训练结果:")
    print(f"样本数: {results['n_samples']}")
    print(f"特征数: {results['n_features']}")
    print(f"异常比例: {results['anomaly_ratio']:.3f}")
    
    if 'evaluation' in results:
        print(f"准确率: {results['evaluation']['accuracy']:.3f}")


def main():
    """主测试函数"""
    print("开始测试孤独森林训练器...\n")
    
    try:
        # 测试特征提取器
        test_feature_extractor()
        
        # 测试数据加载
        test_data_loading()
        
        # 测试模型训练
        test_training()
        
        print("\n=== 所有测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()