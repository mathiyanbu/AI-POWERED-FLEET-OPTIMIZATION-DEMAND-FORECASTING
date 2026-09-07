from __future__ import annotations
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'
MODEL_PATH = BASE_DIR / 'ml' / 'model.pkl'


def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    if not (DATA_DIR / 'routes.csv').exists():
        pd.DataFrame([
            {'route_id': 'A', 'route_name': 'Route A', 'base_capacity': 90, 'base_buses': 5, 'lat': 40.7128, 'lng': -74.0060},
            {'route_id': 'B', 'route_name': 'Route B', 'base_capacity': 90, 'base_buses': 7, 'lat': 40.7240, 'lng': -73.9890},
            {'route_id': 'C', 'route_name': 'Route C', 'base_capacity': 90, 'base_buses': 4, 'lat': 40.7310, 'lng': -74.0130},
            {'route_id': 'D', 'route_name': 'Route D', 'base_capacity': 90, 'base_buses': 4, 'lat': 40.7440, 'lng': -73.9900},
        ]).to_csv(DATA_DIR / 'routes.csv', index=False)
    if not (DATA_DIR / 'buses.csv').exists():
        buses = []
        for route in ['A', 'B', 'C', 'D']:
            for idx in range(1, 7):
                buses.append({
                    'bus_id': f'{route}-{idx}',
                    'route_id': route,
                    'capacity': 90,
                    'occupancy_pct': 42 + (idx * 8),
                    'status': 'LOW' if idx < 3 else 'MODERATE'
                })
        pd.DataFrame(buses).to_csv(DATA_DIR / 'buses.csv', index=False)


def generate_synthetic_dataset():
    ensure_data_files()
    rng = np.random.default_rng(42)
    rows = []
    route_ids = ['A', 'B', 'C', 'D']
    for day in range(1, 181):
        for hour in range(0, 24):
            for route in route_ids:
                base = {'A': 520, 'B': 380, 'C': 470, 'D': 460}[route]
                peak = 1 if 7 <= hour <= 9 or 16 <= hour <= 19 else 0
                weekly = 1 if day % 7 in [1, 2, 3, 4, 5] else 0.75
                trend = 1 + (np.sin((hour / 24) * 2 * np.pi) * 0.4)
                load = base * (1 + 0.5 * peak + 0.2 * weekly) * trend
                current_occupancy = min(100, max(10, (load / 90) * 0.75 + rng.normal(0, 12)))
                previous_interval = max(80, load * (0.9 + rng.random() * 0.35))
                available_buses = 3 + (route == 'A') * 2 + (route == 'B') * 3 + (route == 'C') * 1 + (route == 'D') * 1
                passenger_demand = max(80, load + rng.normal(0, 45) + peak * 110)
                rows.append({
                    'timestamp': f'2026-01-{(day % 28) + 1:02d} {hour:02d}:00:00',
                    'route_id': route,
                    'hour': hour,
                    'day_of_week': (day % 7) + 1,
                    'peak_period': peak,
                    'historical_demand': round(max(50, load * (0.75 + rng.random() * 0.35))),
                    'current_occupancy': round(float(current_occupancy), 2),
                    'previous_interval_demand': round(float(previous_interval), 2),
                    'available_buses': int(available_buses),
                    'passenger_demand': round(float(passenger_demand), 2)
                })
    df = pd.DataFrame(rows)
    data_path = DATA_DIR / 'passenger_demand.csv'
    df.to_csv(data_path, index=False)
    return df


def load_or_create_dataset():
    csv_path = DATA_DIR / 'passenger_demand.csv'
    if not csv_path.exists():
        return generate_synthetic_dataset()
    return pd.read_csv(csv_path)


def train_model_if_needed():
    MODEL_PATH.parent.mkdir(exist_ok=True, parents=True)
    if not MODEL_PATH.exists():
        df = load_or_create_dataset()
        return train_model(df)
    return load_model()


def train_model(df):
    df = df.copy()
    features = ['route_id', 'hour', 'day_of_week', 'peak_period', 'historical_demand', 'current_occupancy', 'previous_interval_demand', 'available_buses']
    df['route_id'] = df['route_id'].astype(str)
    encoded = pd.get_dummies(df[features], columns=['route_id'])
    X = encoded
    y = df['passenger_demand']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=200, random_state=42, max_depth=12)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    metrics = {
        'r2': round(float(r2_score(y_test, preds)), 4),
        'mae': round(float(mean_absolute_error(y_test, preds)), 2),
        'rmse': round(float(np.sqrt(mean_squared_error(y_test, preds))), 2)
    }
    payload = {'model': model, 'feature_columns': list(X.columns), 'metrics': metrics}
    joblib.dump(payload, MODEL_PATH)
    return payload


def load_model():
    if not MODEL_PATH.exists():
        df = load_or_create_dataset()
        return train_model(df)
    payload = joblib.load(MODEL_PATH)
    if isinstance(payload, dict) and 'model' in payload:
        return payload
    raise ValueError('Model file is invalid or not trained yet')


def predict_route_demand():
    model_payload = load_model()
    model = model_payload['model']
    feature_columns = model_payload['feature_columns']
    df = load_or_create_dataset()
    latest = df.tail(1).copy()
    current_occupancy = latest['current_occupancy'].iloc[0]
    route_map = {'A': {'current_occupancy': 91, 'historical_demand': 620, 'previous_interval_demand': 480, 'available_buses': 5},
                 'B': {'current_occupancy': 42, 'historical_demand': 330, 'previous_interval_demand': 290, 'available_buses': 7},
                 'C': {'current_occupancy': 72, 'historical_demand': 500, 'previous_interval_demand': 430, 'available_buses': 4},
                 'D': {'current_occupancy': 78, 'historical_demand': 440, 'previous_interval_demand': 390, 'available_buses': 4}}

    results = {}
    for route_id, values in route_map.items():
        feature_row = pd.DataFrame([{
            'route_id': route_id,
            'hour': 17,
            'day_of_week': 2,
            'peak_period': 1,
            'historical_demand': values['historical_demand'],
            'current_occupancy': values['current_occupancy'],
            'previous_interval_demand': values['previous_interval_demand'],
            'available_buses': values['available_buses']
        }])
        encoded = pd.get_dummies(feature_row, columns=['route_id'])
        missing_cols = [c for c in feature_columns if c not in encoded.columns]
        for c in missing_cols:
            encoded[c] = 0
        encoded = encoded[feature_columns]
        pred = float(model.predict(encoded)[0])
        occupancy = min(100, max(0, (pred / (values['available_buses'] * 90)) * 100))
        results[route_id] = {
            'predicted_demand': round(pred, 1),
            'predicted_occupancy': round(occupancy, 1),
            'status': 'CRITICAL' if occupancy >= 91 else 'HIGH' if occupancy >= 76 else 'MODERATE' if occupancy >= 51 else 'LOW',
            'current_demand': values['historical_demand'],
            'route_name': f'Route {route_id}'
        }

    total_predicted = sum(r['predicted_demand'] for r in results.values())
    return {
        'generated_at': '2026-09-06 17:30:00',
        'total_predicted_demand': round(total_predicted, 1),
        'by_route': results,
        'current_demand': 1240,
    }


def get_model_metrics():
    df = load_or_create_dataset()
    model_payload = load_model()
    model = model_payload['model']
    features = ['route_id', 'hour', 'day_of_week', 'peak_period', 'historical_demand', 'current_occupancy', 'previous_interval_demand', 'available_buses']
    encoded = pd.get_dummies(df[features], columns=['route_id'])
    X = encoded
    y = df['passenger_demand']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    preds = model.predict(X_test)
    return {
        'r2': round(float(r2_score(y_test, preds)), 4),
        'mae': round(float(mean_absolute_error(y_test, preds)), 2),
        'rmse': round(float(np.sqrt(mean_squared_error(y_test, preds))), 2),
        'dataset_size': len(df),
        'test_size': len(X_test)
    }
