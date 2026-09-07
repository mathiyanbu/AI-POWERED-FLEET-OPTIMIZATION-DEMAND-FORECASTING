from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.model_service import predict_route_demand, train_model_if_needed

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'

ROUTES = {
    'A': {'name': 'Route A', 'base_demand': 720, 'capacity': 90, 'base_buses': 5, 'priority': 1},
    'B': {'name': 'Route B', 'base_demand': 310, 'capacity': 90, 'base_buses': 7, 'priority': 4},
    'C': {'name': 'Route C', 'base_demand': 540, 'capacity': 90, 'base_buses': 6, 'priority': 3},
    'D': {'name': 'Route D', 'base_demand': 670, 'capacity': 90, 'base_buses': 6, 'priority': 2},
}


def _status_for_occupancy(occupancy):
    if occupancy >= 91:
        return 'CRITICAL'
    if occupancy >= 76:
        return 'HIGH'
    if occupancy >= 51:
        return 'MODERATE'
    return 'LOW'


def _risk_level_for_occupancy(occupancy):
    return _status_for_occupancy(occupancy)


def _occupancy_for_route(route_id, demand, buses):
    route = ROUTES[route_id]
    return min(100.0, max(0.0, (demand / max(1, buses * route['capacity'])) * 100.0))


def _route_snapshot():
    route_rows = []
    for route_id, meta in ROUTES.items():
        if route_id == 'A':
            current_demand = 730
            predicted_demand = 940
        elif route_id == 'B':
            current_demand = 320
            predicted_demand = 360
        elif route_id == 'C':
            current_demand = 520
            predicted_demand = 590
        else:
            current_demand = 680
            predicted_demand = 860

        current_occupancy = _occupancy_for_route(route_id, current_demand, meta['base_buses'])
        predicted_occupancy = _occupancy_for_route(route_id, predicted_demand, meta['base_buses'])
        route_rows.append({
            'route_id': route_id,
            'route_name': meta['name'],
            'current_buses': meta['base_buses'],
            'predicted_demand': round(predicted_demand),
            'current_demand': round(current_demand),
            'current_occupancy': round(current_occupancy, 1),
            'predicted_occupancy': round(predicted_occupancy, 1),
            'status': _status_for_occupancy(predicted_occupancy),
            'risk': _risk_level_for_occupancy(predicted_occupancy),
            'capacity': meta['capacity'],
            'peak_window': '17:00-18:00',
            'history': [max(180, int(meta['base_demand'] * (0.7 + idx * 0.12))) for idx in range(6)]
        })
    return route_rows


def _generate_buses():
    buses = []
    route_order = ['A', 'B', 'C', 'D']
    route_counts = {'A': 5, 'B': 7, 'C': 6, 'D': 6}
    idx = 1
    for route_id in route_order:
        for bus_number in range(1, route_counts[route_id] + 1):
            passengers = {
                'A': [28, 33, 41, 25, 38],
                'B': [18, 22, 14, 17, 20, 24, 16],
                'C': [26, 31, 37, 29, 34, 28],
                'D': [24, 32, 39, 28, 36, 31],
            }[route_id][min(bus_number - 1, 6)]
            occupancy = min(100, round((passengers / 40) * 100, 1))
            buses.append({
                'bus_id': f'BUS-{idx:03d}',
                'route_id': route_id,
                'route': ROUTES[route_id]['name'],
                'capacity': 40,
                'current_passengers': passengers,
                'occupancy_percent': occupancy,
                'crowd_level': _status_for_occupancy(occupancy),
                'status': 'ACTIVE',
                'timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
            })
            idx += 1
    return buses


def build_transport_plan():
    route_data = _route_snapshot()
    current = {r['route_id']: r['current_buses'] for r in route_data}
    predicted = {r['route_id']: r['predicted_demand'] for r in route_data}
    recommended = dict(current)

    recommended['A'] = 7
    recommended['B'] = 5
    recommended['C'] = 6
    recommended['D'] = 6

    plan_lines = []
    for route in route_data:
        rid = route['route_id']
        delta = recommended[rid] - current[rid]
        after_occupancy = _occupancy_for_route(rid, predicted[rid], recommended[rid])
        plan_lines.append({
            'route_id': rid,
            'route_name': route['route_name'],
            'current_buses': current[rid],
            'recommended_buses': recommended[rid],
            'delta': delta,
            'before_occupancy': route['current_occupancy'],
            'after_occupancy': round(after_occupancy, 1),
            'before_status': route['status'],
            'after_status': _status_for_occupancy(after_occupancy),
        })

    return {
        'current_plan': dict(current),
        'recommended_plan': dict(recommended),
        'plan_lines': plan_lines,
        'facility_total': 24,
        'high_risk_routes': [r['route_id'] for r in route_data if r['status'] in ['HIGH', 'CRITICAL']],
    }


def get_route_explanation(route_id):
    risk_by_route = {
        'A': 'Current occupancy is high, historical demand peaks during 5–6 PM, and the weekday commute is pushing demand above the recommended threshold.',
        'B': 'Route B remains below target load and has spare capacity that can be reallocated without reducing service quality.',
        'C': 'Route C is stable but should be monitored as evening demand begins to increase.',
        'D': 'Route D is seeing elevated commuter traffic and should be supported with extra coverage during the peak window.'
    }
    return risk_by_route.get(route_id, 'Demand is within a stable operating range.')


def generate_live_snapshot():
    train_model_if_needed()
    prediction = predict_route_demand()
    current_routes = _route_snapshot()
    plan = build_transport_plan()

    route_snapshot = []
    for route in current_routes:
        rid = route['route_id']
        pred = prediction['by_route'][rid]
        predicted_demand = float(pred['predicted_demand'])
        predicted_occupancy = min(100.0, max(0.0, pred['predicted_occupancy']))
        route_snapshot.append({
            'route_id': rid,
            'route_name': route['route_name'],
            'current_demand': route['current_demand'],
            'predicted_demand': round(predicted_demand),
            'current_occupancy': route['current_occupancy'],
            'predicted_occupancy': round(predicted_occupancy, 1),
            'status': _status_for_occupancy(predicted_occupancy),
            'risk': _risk_level_for_occupancy(predicted_occupancy),
            'current_buses': route['current_buses'],
            'recommended_buses': max(1, plan['recommended_plan'][rid]),
            'explanation': get_route_explanation(rid),
            'peak_window': '17:00-18:00'
        })

    high_risk = [r for r in route_snapshot if r['status'] in ['HIGH', 'CRITICAL']]
    buses = _generate_buses()

    recommendations = [
        {
            'priority': 'HIGH PRIORITY',
            'route_id': 'A',
            'route_name': 'Route A',
            'message': 'Route A is predicted to reach 94% occupancy during the evening peak.',
            'action': 'Deploy 2 additional buses from Route B to support the peak demand window.'
        },
        {
            'priority': 'REALLOCATION',
            'route_id': 'B',
            'route_name': 'Route B',
            'message': 'Route B is predicted to operate at 36% occupancy and has spare capacity.',
            'action': 'Reallocate 2 buses to Route A and keep Route B above 1 bus per segment.'
        },
        {
            'priority': 'STABLE',
            'route_id': 'C',
            'route_name': 'Route C',
            'message': 'Route C is predicted to remain below 70%.',
            'action': 'Maintain the current allocation and monitor headway stability.'
        }
    ]

    overcrowded_before = len([r for r in route_snapshot if r['current_occupancy'] >= 76])
    overcrowded_after = len([r for r in route_snapshot if r['predicted_occupancy'] >= 76])
    fleet_util_before = round((sum(r['current_demand'] for r in route_snapshot) / (len(route_snapshot) * 90 * 5)) * 100, 1)
    fleet_util_after = round((sum(r['predicted_demand'] for r in route_snapshot) / (len(route_snapshot) * 90 * 6)) * 100, 1)

    plan_summary = {
        'data_source': 'SIMULATION DATA',
        'total_buses': 24,
        'active_routes': len(route_snapshot),
        'total_current_demand': int(sum(r['current_demand'] for r in route_snapshot)),
        'predicted_peak_demand': int(sum(r['predicted_demand'] for r in route_snapshot)),
        'high_risk_routes': len(high_risk),
        'buses_recommended': sum(max(0, plan['recommended_plan'][r['route_id']] - r['current_buses']) for r in route_snapshot),
        'current_plan': {r['route_id']: r['current_buses'] for r in route_snapshot},
        'recommended_plan': {r['route_id']: plan['recommended_plan'][r['route_id']] for r in route_snapshot},
        'before_after': {
            'overcrowded_before': overcrowded_before,
            'overcrowded_after': overcrowded_after,
            'fleet_utilization_before': fleet_util_before,
            'fleet_utilization_after': fleet_util_after,
        },
        'route_risk': route_snapshot,
        'plan_lines': plan['plan_lines'],
        'recommendations': recommendations,
        'ai_plan': plan,
    }

    return {
        'data_source': 'SIMULATION DATA',
        'buses': buses,
        'routes': route_snapshot,
        'route_risk': route_snapshot,
        'recommendations': recommendations,
        'plan_summary': plan_summary,
        'ai_plan': plan,
        'simulation_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    }
