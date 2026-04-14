import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, precision_score, recall_score, f1_score
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class IsolationForestTrainer:
    def __init__(self, contamination=0.1, n_estimators=100, random_state=42):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model = None
        self.feature_columns = None

    def load_data(self, data_path):
        print(f"Loading data from {data_path}...")
        df = pd.read_csv(data_path)
        print(f"Loaded {len(df)} samples with {len(df.columns)} features")
        return df

    def prepare_data(self, df, label_column='Class'):
        print("Preparing data...")
        if label_column in df.columns:
            labels = df[label_column].map({'Valid': 0, 'Anomaly': 1, 'Anomalous': 1})
            features = df.drop(columns=[label_column])
        else:
            labels = None
            features = df

        # 移除标签为 NaN 的样本
        if labels is not None:
            mask = labels.notna()
            if not mask.all():
                print(f"Removing {len(labels) - mask.sum()} samples with NaN labels")
                features = features[mask]
                labels = labels[mask]

        self.feature_columns = features.columns.tolist()
        print(f"Using {len(self.feature_columns)} features for training")

        if labels is not None:
            print(f"Label distribution:\n{labels.value_counts()}")
            return features, labels
        return features, None

    def train(self, features, labels=None):
        print(f"\nTraining Isolation Forest model...")
        print(f"Parameters: contamination={self.contamination}, n_estimators={self.n_estimators}")

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1
        )

        if labels is not None:
            # 检查是否只有一个类别
            if len(labels.unique()) > 1:
                X_train, X_test, y_train, y_test = train_test_split(
                    features, labels, test_size=0.2, random_state=self.random_state, stratify=labels
                )
            else:
                print("Warning: Only one class found in labels. Skipping stratification.")
                X_train, X_test, y_train, y_test = train_test_split(
                    features, labels, test_size=0.2, random_state=self.random_state
                )
            print(f"Training set size: {len(X_train)}, Test set size: {len(X_test)}")

            self.model.fit(X_train)
            predictions = self.model.predict(X_test)
            predictions_binary = (predictions == -1).astype(int)

            print("\n" + "=" * 60)
            print("MODEL EVALUATION RESULTS")
            print("=" * 60)

            print("\nConfusion Matrix:")
            print(confusion_matrix(y_test, predictions_binary))

            print("\nClassification Report:")
            print(classification_report(y_test, predictions_binary, target_names=['Normal', 'Anomaly']))

            try:
                scores = self.model.score_samples(X_test)
                auc = roc_auc_score(y_test, scores)
                print(f"ROC-AUC Score: {auc:.4f}")
            except Exception as e:
                print(f"Could not calculate ROC-AUC: {e}")

            precision = precision_score(y_test, predictions_binary, zero_division=0)
            recall = recall_score(y_test, predictions_binary, zero_division=0)
            f1 = f1_score(y_test, predictions_binary, zero_division=0)
            print(f"\nKey Metrics:")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall: {recall:.4f}")
            print(f"  F1-Score: {f1:.4f}")

            return X_test, y_test, predictions_binary
        else:
            self.model.fit(features)
            print("Training completed (no labels provided)")
            return None, None, None

    def save_model(self, model_path):
        if self.model is None:
            print("No model to save!")
            return

        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(self.model, model_path)
        print(f"\nModel saved to {model_path}")

        config_path = model_path.replace('.pkl', '_config.pkl')
        config = {
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'random_state': self.random_state,
            'feature_columns': self.feature_columns
        }
        joblib.dump(config, config_path)
        print(f"Model config saved to {config_path}")

    def load_model(self, model_path):
        print(f"Loading model from {model_path}...")
        self.model = joblib.load(model_path)
        config_path = model_path.replace('.pkl', '_config.pkl')
        if os.path.exists(config_path):
            config = joblib.load(config_path)
            self.feature_columns = config.get('feature_columns')
        print("Model loaded successfully")
        return self.model

    def predict(self, features):
        if self.model is None:
            print("No model loaded!")
            return None
        predictions = self.model.predict(features)
        scores = self.model.score_samples(features)
        return predictions, scores

    def predict_anomalies(self, features, threshold=None):
        predictions, scores = self.predict(features)
        if predictions is None:
            return None, None

        if threshold is None:
            threshold = np.percentile(scores, self.contamination * 100)

        anomalies = scores < threshold
        return anomalies, scores


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "datas", "split/train_data.csv")
    model_path = os.path.join(base_dir, "models", "isolation_forest_model.pkl")

    contamination = 0.45
    n_estimators = 100

    trainer = IsolationForestTrainer(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=42
    )

    df = trainer.load_data(data_path)
    features, labels = trainer.prepare_data(df)

    if labels is not None:
        X_test, y_test, predictions = trainer.train(features, labels)
        trainer.save_model(model_path)
        print("\nTraining completed successfully!")
    else:
        trainer.train(features)
        trainer.save_model(model_path)
        print("\nTraining completed successfully!")