import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, 
    precision_score, recall_score, f1_score, roc_curve, 
    precision_recall_curve, average_precision_score
)
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False
    print("Warning: seaborn not installed. Using matplotlib for visualization.")

class ModelEvaluator:
    def __init__(self, model_path=None):
        self.model = None
        self.config = None
        self.feature_columns = None
        
        if model_path:
            self.load_model(model_path)
    
    def load_model(self, model_path):
        print(f"Loading model from {model_path}...")
        self.model = joblib.load(model_path)
        
        config_path = model_path.replace('.pkl', '_config.pkl')
        if os.path.exists(config_path):
            self.config = joblib.load(config_path)
            self.feature_columns = self.config.get('feature_columns')
            print(f"Model config loaded: contamination={self.config.get('contamination')}, "
                  f"n_estimators={self.config.get('n_estimators')}")
        print("Model loaded successfully")
        return self.model
    
    def load_data(self, data_path, label_column='Class'):
        print(f"Loading data from {data_path}...")
        df = pd.read_csv(data_path)
        print(f"Loaded {len(df)} samples")
        
        if label_column in df.columns:
            labels = df[label_column].map({'Valid': 0, 'Anomaly': 1, 'Anomalous': 1})
            features = df.drop(columns=[label_column])
            
            # 移除标签为 NaN 的样本
            mask = labels.notna()
            if not mask.all():
                print(f"Removing {len(labels) - mask.sum()} samples with NaN labels")
                features = features[mask]
                labels = labels[mask]
        else:
            labels = None
            features = df
            
        if self.feature_columns:
            missing_cols = set(self.feature_columns) - set(features.columns)
            if missing_cols:
                print(f"Warning: Missing columns: {missing_cols}")
            features = features[self.feature_columns]
            
        return features, labels
    
    def evaluate(self, features, labels, output_dir=None):
        print("\n" + "=" * 60)
        print("MODEL EVALUATION")
        print("=" * 60)
        
        if self.model is None:
            print("No model loaded!")
            return None
        
        predictions = self.model.predict(features)
        predictions_binary = (predictions == -1).astype(int)
        scores = self.model.score_samples(features)
        
        results = {
            'predictions': predictions_binary,
            'scores': scores,
            'true_labels': labels
        }
        
        if labels is not None:
            print("\n1. CONFUSION MATRIX")
            print("-" * 40)
            cm = confusion_matrix(labels, predictions_binary)
            print(cm)
            
            tn, fp, fn, tp = cm.ravel()
            print(f"\nTrue Negatives (Normal correctly classified): {tn}")
            print(f"False Positives (Normal misclassified as Anomaly): {fp}")
            print(f"False Negatives (Anomaly misclassified as Normal): {fn}")
            print(f"True Positives (Anomaly correctly classified): {tp}")
            
            print("\n2. CLASSIFICATION REPORT")
            print("-" * 40)
            print(classification_report(labels, predictions_binary, 
                                      target_names=['Normal', 'Anomaly']))
            
            print("\n3. DETAILED METRICS")
            print("-" * 40)
            precision = precision_score(labels, predictions_binary, zero_division=0)
            recall = recall_score(labels, predictions_binary, zero_division=0)
            f1 = f1_score(labels, predictions_binary, zero_division=0)
            
            try:
                auc = roc_auc_score(labels, scores)
                print(f"ROC-AUC Score: {auc:.4f}")
            except:
                auc = None
                print("Could not calculate ROC-AUC")
            
            try:
                avg_precision = average_precision_score(labels, -scores)
                print(f"Average Precision Score: {avg_precision:.4f}")
            except:
                avg_precision = None
            
            print(f"\nPrecision: {precision:.4f}")
            print(f"Recall: {recall:.4f}")
            print(f"F1-Score: {f1:.4f}")
            print(f"Accuracy: {(tp + tn) / (tp + tn + fp + fn):.4f}")
            print(f"Specificity (TNR): {tn / (tn + fp):.4f}" if (tn + fp) > 0 else "Specificity: N/A")
            print(f"Sensitivity (TPR): {tp / (tp + fn):.4f}" if (tp + fn) > 0 else "Sensitivity: N/A")
            
            results['metrics'] = {
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'accuracy': (tp + tn) / (tp + tn + fp + fn),
                'roc_auc': auc,
                'avg_precision': avg_precision
            }
            
            if output_dir:
                self._plot_results(features, labels, predictions_binary, scores, output_dir)
        
        return results
    
    def _plot_results(self, features, labels, predictions, scores, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Confusion Matrix Heatmap
        plt.figure(figsize=(8, 6))
        cm = confusion_matrix(labels, predictions)
        
        if HAS_SEABORN:
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                       xticklabels=['Normal', 'Anomaly'],
                       yticklabels=['Normal', 'Anomaly'])
        else:
            plt.imshow(cm, interpolation='nearest', cmap='Blues')
            plt.colorbar()
            thresh = cm.max() / 2.
            for i in range(cm.shape[0]):
                for j in range(cm.shape[1]):
                    plt.text(j, i, format(cm[i, j], 'd'),
                            ha="center", va="center",
                            color="white" if cm[i, j] > thresh else "black")
            plt.xticks([0, 1], ['Normal', 'Anomaly'])
            plt.yticks([0, 1], ['Normal', 'Anomaly'])
        
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'confusion_matrix.png'), dpi=300)
        plt.close()
        print(f"\nConfusion matrix saved to {output_dir}/confusion_matrix.png")
        
        # 2. ROC Curve
        plt.figure(figsize=(8, 6))
        fpr, tpr, _ = roc_curve(labels, -scores)
        try:
            roc_auc = roc_auc_score(labels, scores)
            plt.plot(fpr, tpr, color='darkorange', lw=2, 
                    label=f'ROC curve (AUC = {roc_auc:.4f})')
        except:
            plt.plot(fpr, tpr, color='darkorange', lw=2, label='ROC curve')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'roc_curve.png'), dpi=300)
        plt.close()
        print(f"ROC curve saved to {output_dir}/roc_curve.png")
        
        # 3. Precision-Recall Curve
        plt.figure(figsize=(8, 6))
        precision_vals, recall_vals, _ = precision_recall_curve(labels, -scores)
        try:
            avg_precision = average_precision_score(labels, -scores)
            plt.plot(recall_vals, precision_vals, color='blue', lw=2,
                    label=f'PR curve (AP = {avg_precision:.4f})')
        except:
            plt.plot(recall_vals, precision_vals, color='blue', lw=2, label='PR curve')
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.legend(loc="lower left")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'precision_recall_curve.png'), dpi=300)
        plt.close()
        print(f"Precision-Recall curve saved to {output_dir}/precision_recall_curve.png")
        
        # 4. Score Distribution
        plt.figure(figsize=(10, 6))
        normal_scores = scores[labels == 0]
        anomaly_scores = scores[labels == 1] if 1 in labels.unique() else np.array([])
        
        plt.hist(normal_scores, bins=50, alpha=0.7, label='Normal', color='green', density=True)
        if len(anomaly_scores) > 0:
            plt.hist(anomaly_scores, bins=50, alpha=0.7, label='Anomaly', color='red', density=True)
        plt.xlabel('Anomaly Score')
        plt.ylabel('Density')
        plt.title('Distribution of Anomaly Scores')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'score_distribution.png'), dpi=300)
        plt.close()
        print(f"Score distribution saved to {output_dir}/score_distribution.png")
    
    def analyze_predictions(self, features, labels, original_data_path=None):
        print("\n" + "=" * 60)
        print("DETAILED PREDICTION ANALYSIS")
        print("=" * 60)
        
        if self.model is None:
            print("No model loaded!")
            return
        
        predictions = self.model.predict(features)
        predictions_binary = (predictions == -1).astype(int)
        scores = self.model.score_samples(features)
        
        # False Positives (Normal classified as Anomaly)
        fp_indices = np.where((labels == 0) & (predictions_binary == 1))[0]
        print(f"\nFalse Positives (Normal → Anomaly): {len(fp_indices)}")
        if len(fp_indices) > 0:
            print(f"  Score range: [{scores[fp_indices].min():.4f}, {scores[fp_indices].max():.4f}]")
            print(f"  Mean score: {scores[fp_indices].mean():.4f}")
        
        # False Negatives (Anomaly classified as Normal)
        fn_indices = np.where((labels == 1) & (predictions_binary == 0))[0]
        print(f"\nFalse Negatives (Anomaly → Normal): {len(fn_indices)}")
        if len(fn_indices) > 0:
            print(f"  Score range: [{scores[fn_indices].min():.4f}, {scores[fn_indices].max():.4f}]")
            print(f"  Mean score: {scores[fn_indices].mean():.4f}")
        
        # True Positives (Correctly identified anomalies)
        tp_indices = np.where((labels == 1) & (predictions_binary == 1))[0]
        print(f"\nTrue Positives (Anomaly → Anomaly): {len(tp_indices)}")
        if len(tp_indices) > 0:
            print(f"  Score range: [{scores[tp_indices].min():.4f}, {scores[tp_indices].max():.4f}]")
            print(f"  Mean score: {scores[tp_indices].mean():.4f}")
        
        # Top anomalies
        print("\n" + "-" * 40)
        print("TOP 10 MOST ANOMALOUS SAMPLES")
        print("-" * 40)
        top_anomaly_indices = np.argsort(scores)[:10]
        for i, idx in enumerate(top_anomaly_indices, 1):
            true_label = "Anomaly" if labels[idx] == 1 else "Normal"
            pred_label = "Anomaly" if predictions_binary[idx] == 1 else "Normal"
            print(f"{i}. Index {idx}: Score={scores[idx]:.4f}, "
                  f"True={true_label}, Pred={pred_label}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(base_dir, "models", "isolation_forest_model.pkl")
    data_path = os.path.join(base_dir, "datas", "split/test_data.csv")
    output_dir = os.path.join(base_dir, "evaluation_results")
    
    evaluator = ModelEvaluator(model_path)
    features, labels = evaluator.load_data(data_path)
    
    if labels is not None:
        results = evaluator.evaluate(features, labels, output_dir)
        evaluator.analyze_predictions(features, labels, data_path)
        print("\n" + "=" * 60)
        print("Evaluation completed!")
        print(f"Results saved to: {output_dir}")
        print("=" * 60)
    else:
        print("No labels found in data. Cannot perform evaluation.")