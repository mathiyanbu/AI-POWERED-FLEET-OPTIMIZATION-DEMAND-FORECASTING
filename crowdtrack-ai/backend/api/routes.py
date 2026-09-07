from pathlib import Path

import pandas as pd
from fastapi import APIRouter

from services.model_service import get_model_metrics, predict_route_demand, train_model_if_needed
from services.simulator import build_transport_plan, generate_live_snapshot

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'


def load_routes():
    return pd.read_csv(DATA_DIR / 'routes.csv')


def load_buses():
    return pd.read_csv(DATA_DIR / 'buses.csv')


@router.get('/buses')
def get_buses():
    snapshot = generate_live_snapshot()
    return {'buses': snapshot['buses'], 'data_source': 'SIMULATION DATA'}


@router.get('/bus/{bus_id}/status')
def get_bus_status(bus_id: str):
    snapshot = generate_live_snapshot()
    for bus in snapshot['buses']:
        if bus['bus_id'] == bus_id.upper():
            return {
                'bus_id': bus['bus_id'],
                'route': bus['route'],
                'capacity': bus['capacity'],
                'current_passengers': bus['current_passengers'],
                'occupancy_percent': bus['occupancy_percent'],
                'crowd_level': bus['crowd_level'],
                'status': bus['status'],
                'timestamp': bus['timestamp'],
                'data_source': 'SIMULATION DATA',
            }
    return {'error': 'bus not found', 'data_source': 'SIMULATION DATA'}


@router.get('/routes')
def get_routes():
    routes = load_routes().to_dict(orient='records')
    return {'routes': routes, 'data_source': 'SIMULATION DATA'}


@router.get('/demand/current')
def get_current_demand():
    snapshot = generate_live_snapshot()
    return {
        'data_source': 'SIMULATION DATA',
        'routes': snapshot['routes'],
        'total_current_demand': snapshot['plan_summary']['total_current_demand'],
        'generated_at': snapshot['simulation_timestamp'],
    }


@router.get('/demand/prediction')
def get_demand_prediction():
    train_model_if_needed()
    prediction = predict_route_demand()
    return {
        'data_source': 'SIMULATION DATA',
        'generated_at': prediction['generated_at'],
        'by_route': prediction['by_route'],
        'total_predicted_demand': prediction['total_predicted_demand'],
        'current_demand': prediction['current_demand'],
    }


@router.get('/occupancy')
def get_occupancy():
    data = generate_live_snapshot()
    return data


@router.get('/risk')
def get_risk():
    snapshot = generate_live_snapshot()
    return {'data_source': 'SIMULATION DATA', 'route_risk': snapshot['route_risk']}


@router.get('/predictions')
def get_predictions():
    return get_demand_prediction()


@router.get('/recommendations')
def get_recommendations():
    snapshot = generate_live_snapshot()
    return {
        'data_source': 'SIMULATION DATA',
        'recommendations': snapshot['recommendations'],
        'route_risk': snapshot['route_risk'],
        'ai_plan': snapshot['ai_plan'],
    }


@router.get('/transport-plan')
def get_transport_plan():
    snapshot = generate_live_snapshot()
    return snapshot['plan_summary']


@router.get('/metrics')
def get_metrics():
    return {
        'data_source': 'SIMULATION DATA',
        'model': get_model_metrics(),
        'generated_at': generate_live_snapshot()['simulation_timestamp'],
    }


@router.get('/model-performance')
def get_model_performance():
    return get_model_metrics()


@router.post('/simulate')
def simulate():
    train_model_if_needed()
    snapshot = generate_live_snapshot()
    return snapshot


@router.post('/run-ai')
def run_ai_pipeline():
    train_model_if_needed()
    snapshot = generate_live_snapshot()
    plan = build_transport_plan()
    return {
        'data_source': 'SIMULATION DATA',
        'status': 'AI SIMULATION COMPLETE',
        'simulation_timestamp': snapshot['simulation_timestamp'],
        'plan_summary': snapshot['plan_summary'],
        'route_risk': snapshot['route_risk'],
        'recommendations': snapshot['recommendations'],
        'buses': snapshot['buses'],
        'predictions': get_demand_prediction(),
        'transport_plan': plan,
    }


@router.post('/optimize')
def optimize():
    snapshot = generate_live_snapshot()
    return {
        'data_source': 'SIMULATION DATA',
        'current_plan': snapshot['plan_summary']['current_plan'],
        'optimized_plan': snapshot['plan_summary']['recommended_plan'],
        'plan_lines': snapshot['plan_summary']['plan_lines'],
        'recommendations': snapshot['recommendations'],
        'improvement': {
            'overcrowding_reduction': max(0, snapshot['plan_summary']['before_after']['overcrowded_before'] - snapshot['plan_summary']['before_after']['overcrowded_after']),
            'fleet_utilization_improvement': round(snapshot['plan_summary']['before_after']['fleet_utilization_after'] - snapshot['plan_summary']['before_after']['fleet_utilization_before'], 1),
        },
    }
