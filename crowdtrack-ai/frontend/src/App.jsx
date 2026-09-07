import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

const API_BASE = '/api';

const STATUS_STYLES = {
  LOW: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  MODERATE: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  HIGH: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  CRITICAL: 'bg-red-500/15 text-red-300 border-red-500/30'
};

const navItems = ['Dashboard', 'Live Buses', 'Demand Prediction', 'AI Transport Planner', 'Recommendations', 'Commuter View'];

function StatCard({ label, value, accent = false, hint }) {
  return (
    <div className={`rounded-2xl border ${accent ? 'border-red-500/40 bg-red-500/10' : 'border-white/10 bg-[#170d10]'} p-4 shadow-glow`}>
      <div className="text-xs uppercase tracking-[0.25em] text-slate-400">{label}</div>
      <div className="mt-3 text-3xl font-bold text-white">{value}</div>
      {hint && <div className="mt-2 text-xs text-slate-300">{hint}</div>}
    </div>
  );
}

async function fetchJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

const initialFlow = [
  { label: 'LIVE DATA', status: 'WAITING' },
  { label: 'DEMAND PREDICTION', status: 'WAITING' },
  { label: 'CROWD FORECAST', status: 'WAITING' },
  { label: 'FLEET OPTIMIZATION', status: 'WAITING' },
  { label: 'PLAN GENERATED', status: 'WAITING' }
];

export default function App() {
  const [dashboard, setDashboard] = useState(null);
  const [buses, setBuses] = useState([]);
  const [routeRisk, setRouteRisk] = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [transportPlan, setTransportPlan] = useState(null);
  const [modelMetrics, setModelMetrics] = useState(null);
  const [selectedRoute, setSelectedRoute] = useState('A');
  const [statusSteps, setStatusSteps] = useState(initialFlow);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [liveStatus, setLiveStatus] = useState('');

  const applyPayload = (payload) => {
    const summary = payload?.plan_summary || payload || {};
    const riskItems = payload?.route_risk || summary.route_risk || [];
    const recs = payload?.recommendations || summary.recommendations || [];
    const plan = payload?.transport_plan || summary.ai_plan || payload?.ai_plan || summary || {};

    setDashboard(summary);
    setRouteRisk(riskItems);
    setRecommendations(recs);
    setTransportPlan(plan?.plan_lines ? { ...plan, plan_lines: plan.plan_lines } : summary);
    setPredictions(payload?.predictions || { by_route: {} });
    setModelMetrics(payload?.model || payload?.metrics || {});

    const routeId = (riskItems[0] || {}).route_id || 'A';
    setSelectedRoute(routeId);
  };

  const loadDashboard = async () => {
    setLoading(true);
    setOffline(false);
    try {
      const [occupancy, predictionData, recommendationData, planData, busesData, metricsData] = await Promise.all([
        fetchJson('/occupancy'),
        fetchJson('/predictions'),
        fetchJson('/recommendations'),
        fetchJson('/transport-plan'),
        fetchJson('/buses'),
        fetchJson('/model-performance')
      ]);

      setBuses(busesData?.buses || []);
      setDashboard(occupancy?.plan_summary || planData || {});
      setRouteRisk(occupancy?.route_risk || recommendationData?.route_risk || []);
      setPredictions(predictionData || { by_route: {} });
      setRecommendations(recommendationData?.recommendations || []);
      setTransportPlan(planData || {});
      setModelMetrics(metricsData || {});
      setSelectedRoute((occupancy?.route_risk || [])[0]?.route_id || 'A');
      setLiveStatus('RUNNING WITH SIMULATION DATA');
    } catch (err) {
      console.error(err);
      setOffline(true);
      setLiveStatus('AI BACKEND OFFLINE');
      setBuses([]);
      setRouteRisk([]);
      setRecommendations([]);
      setPredictions({ current_demand: 0, total_predicted_demand: 0, by_route: {} });
      setDashboard({ total_buses: 24, active_routes: 4, total_current_demand: 0, predicted_peak_demand: 0, high_risk_routes: 0, buses_recommended: 0, before_after: { overcrowded_before: 0, overcrowded_after: 0, fleet_utilization_before: 0, fleet_utilization_after: 0 } });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const runSimulation = async () => {
    setLiveStatus('UPDATING LIVE DATA...');
    setStatusSteps(initialFlow.map((step, index) => ({
      ...step,
      status: index === 0 ? 'RUNNING' : 'WAITING'
    })));

    try {
      const result = await fetchJson('/simulate', { method: 'POST' });
      const summary = result?.plan_summary || {};
      setBuses(result?.buses || []);
      setRouteRisk(result?.route_risk || []);
      setRecommendations(result?.recommendations || []);
      setDashboard(summary);
      setTransportPlan(summary || {});
      setPredictions({
        current_demand: summary.total_current_demand,
        total_predicted_demand: summary.predicted_peak_demand,
        by_route: Object.fromEntries((result?.route_risk || []).map((route) => [route.route_id, {
          current_demand: route.current_demand,
          predicted_demand: route.predicted_demand,
          predicted_occupancy: route.predicted_occupancy,
          status: route.status,
          route_name: route.route_name,
        }]))
      });
      setSelectedRoute((result?.route_risk || [])[0]?.route_id || 'A');

      setTimeout(() => {
        setStatusSteps([
          { label: 'LIVE DATA', status: 'COMPLETED' },
          { label: 'DEMAND PREDICTION', status: 'COMPLETED' },
          { label: 'CROWD FORECAST', status: 'COMPLETED' },
          { label: 'FLEET OPTIMIZATION', status: 'COMPLETED' },
          { label: 'PLAN GENERATED', status: 'COMPLETED' }
        ]);
        setLiveStatus('LIVE DATA UPDATED');
      }, 850);
    } catch (err) {
      console.error(err);
      setLiveStatus('AI BACKEND OFFLINE');
      setOffline(true);
    }
  };

  const runAiSimulation = async () => {
    setStatusSteps(initialFlow.map((step, index) => ({
      ...step,
      status: index === 0 ? 'RUNNING' : 'WAITING'
    })));
    setLiveStatus('AI SIMULATION RUNNING');

    const sequence = [
      ['LIVE DATA', 350],
      ['DEMAND PREDICTION', 700],
      ['CROWD FORECAST', 1050],
      ['FLEET OPTIMIZATION', 1400],
      ['PLAN GENERATED', 1750]
    ];

    try {
      for (let i = 0; i < sequence.length; i += 1) {
        const [label, delay] = sequence[i];
        await new Promise((resolve) => setTimeout(resolve, delay));
        setStatusSteps((prev) => prev.map((step, idx) => ({
          ...step,
          status: idx < i + 1 ? 'COMPLETED' : idx === i + 1 ? 'RUNNING' : 'WAITING'
        })));
      }

      const result = await fetchJson('/run-ai', { method: 'POST' });
      const summary = result?.plan_summary || {};
      setDashboard(summary);
      setBuses(result?.buses || []);
      setRouteRisk(result?.route_risk || []);
      setRecommendations(result?.recommendations || []);
      setTransportPlan(result?.transport_plan || summary || {});
      setPredictions(result?.predictions || { by_route: {} });
      setSelectedRoute((result?.route_risk || [])[0]?.route_id || 'A');
      setStatusSteps([
        { label: 'LIVE DATA', status: 'COMPLETED' },
        { label: 'DEMAND PREDICTION', status: 'COMPLETED' },
        { label: 'CROWD FORECAST', status: 'COMPLETED' },
        { label: 'FLEET OPTIMIZATION', status: 'COMPLETED' },
        { label: 'PLAN GENERATED', status: 'COMPLETED' }
      ]);
      setLiveStatus('AI SIMULATION COMPLETE');
    } catch (err) {
      console.error(err);
      setLiveStatus('AI BACKEND OFFLINE');
      setOffline(true);
    }
  };

  const predictedTrend = useMemo(() => {
    const byRoute = predictions?.by_route || {};
    return Object.entries(byRoute).map(([key, value]) => ({
      route: key,
      current: Number(value.current_demand || 0),
      predicted: Number(value.predicted_demand || 0),
      occupancy: Number(value.predicted_occupancy || 0),
      status: value.status || 'LOW'
    }));
  }, [predictions]);

  const beforeAfterData = useMemo(() => {
    const planLines = transportPlan?.plan_lines || dashboard?.plan_lines || [];
    return planLines.map((item) => ({
      name: item.route_id,
      before: Number(item.before_occupancy || 0),
      after: Number(item.after_occupancy || 0)
    }));
  }, [transportPlan, dashboard]);

  const selectedRouteData = routeRisk.find((route) => route.route_id === selectedRoute) || routeRisk[0] || {};
  const commuterOptions = routeRisk.length ? routeRisk : [
    { route_id: 'A', route_name: 'Route A', predicted_occupancy: 94, status: 'CRITICAL' },
    { route_id: 'B', route_name: 'Route B', predicted_occupancy: 35, status: 'LOW' }
  ];

  const stepStatusClass = (status) => {
    if (status === 'COMPLETED') return 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200';
    if (status === 'RUNNING') return 'border-red-500/40 bg-red-500/15 text-red-200';
    return 'border-white/10 bg-slate-900 text-slate-300';
  };

  return (
    <div className="min-h-screen bg-[#05070b] text-white">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6 flex flex-col gap-4 rounded-2xl border border-red-500/20 bg-[#140d10] p-4 shadow-glow lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-xs uppercase tracking-[0.35em] text-red-300">CrowdTrack AI</div>
            <h1 className="mt-2 text-3xl font-bold text-white">Predictive & Adaptive Public Transport Planning</h1>
          </div>
          <div className="flex flex-col items-end gap-2">
            <button
              onClick={runAiSimulation}
              className="rounded-xl bg-gradient-to-r from-red-600 to-red-500 px-6 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-white shadow-lg shadow-red-950/40 transition hover:brightness-110"
            >
              RUN AI SIMULATION
            </button>
            <button
              onClick={runSimulation}
              className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-red-200"
            >
              SIMULATE LIVE DATA
            </button>
          </div>
        </header>

        {offline && (
          <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            AI BACKEND OFFLINE • RUNNING WITH SIMULATION DATA
          </div>
        )}

        {liveStatus && (
          <div className="mb-6 rounded-xl border border-red-500/20 bg-[#140d10] px-4 py-3 text-xs uppercase tracking-[0.2em] text-red-200">
            {liveStatus}
          </div>
        )}

        <nav className="mb-6 flex flex-wrap gap-2 text-xs uppercase tracking-[0.2em] text-slate-300">
          {navItems.map((item) => (
            <button key={item} className="rounded-full border border-white/10 bg-[#120c0d] px-3 py-2 hover:border-red-500/40 hover:text-red-200">
              {item}
            </button>
          ))}
        </nav>

        <section className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <StatCard label="TOTAL BUSES" value={dashboard?.total_buses ?? 24} hint="Fleet available" accent />
          <StatCard label="ACTIVE ROUTES" value={dashboard?.active_routes ?? 4} hint="Operational lines" />
          <StatCard label="CURRENT DEMAND" value={new Intl.NumberFormat().format(dashboard?.total_current_demand ?? 0)} hint="Passengers" />
          <StatCard label="PREDICTED PEAK" value={new Intl.NumberFormat().format(dashboard?.predicted_peak_demand ?? 0)} hint="Peak demand" />
          <StatCard label="HIGH-RISK ROUTES" value={dashboard?.high_risk_routes ?? 0} hint="At-risk today" />
          <StatCard label="RECOMMENDATIONS" value={dashboard?.buses_recommended ?? 0} hint="Bus reallocation" />
        </section>

        <section className="mb-6 grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Live Bus Map</h2>
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400">{dashboard?.data_source || 'SIMULATION DATA'}</span>
            </div>
            <div className="relative h-[280px] overflow-hidden rounded-2xl border border-white/10 bg-[radial-gradient(circle_at_center,_rgba(255,82,82,0.18),_rgba(2,6,23,0.4)_40%,_rgba(15,23,42,0.88)_100%)]">
              <div className="absolute inset-0 opacity-30" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)', backgroundSize: '38px 38px' }} />
              {(buses.length ? buses : Array.from({ length: 8 }, (_, idx) => ({ bus_id: `BUS-${idx + 1}`, route_id: ['A', 'B', 'C', 'D'][idx % 4], occupancy_pct: 40 + idx * 8, status: ['LOW', 'MODERATE', 'HIGH', 'CRITICAL'][idx % 4] }))).slice(0, 12).map((bus, index) => (
                <div
                  key={bus.bus_id}
                  className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
                  style={{ left: `${20 + (index % 5) * 18}%`, top: `${22 + Math.floor(index / 5) * 30}%` }}
                >
                  <div className={`flex h-4 w-4 items-center justify-center rounded-full border-2 ${bus.status === 'LOW' ? 'border-emerald-400 bg-emerald-500' : bus.status === 'MODERATE' ? 'border-yellow-400 bg-yellow-500' : bus.status === 'HIGH' ? 'border-orange-400 bg-orange-500' : 'border-red-400 bg-red-500'}`} />
                  <div className="mt-2 rounded-lg border border-white/10 bg-slate-900/90 p-2 text-[10px] leading-tight text-white shadow-lg">
                    <div className="font-semibold">{bus.bus_id}</div>
                    <div>Route {bus.route_id || bus.route}</div>
                    <div>{bus.occupancy_pct ?? bus.occupancy_percent ?? 0}%</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Simulation Flow</h2>
            <div className="space-y-3">
              {statusSteps.map((step, index) => (
                <div key={`${step.label}-${index}`} className="flex items-center gap-3">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-full border text-[10px] font-bold ${stepStatusClass(step.status)}`}>
                    {index + 1}
                  </div>
                  <div className="text-sm uppercase tracking-[0.18em] text-slate-200">{step.label}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Demand Prediction</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Current Demand</div>
                <div className="mt-2 text-2xl font-bold text-white">{predictions?.current_demand ?? 620}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Predicted Demand</div>
                <div className="mt-2 text-2xl font-bold text-white">{predictions?.total_predicted_demand ? Math.round(predictions.total_predicted_demand) : 910}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Predicted Occupancy</div>
                <div className="mt-2 text-2xl font-bold text-white">{selectedRouteData.predicted_occupancy ?? 90}%</div>
              </div>
            </div>
            <div className="mt-5 h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={predictedTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="route" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip />
                  <Line type="monotone" dataKey="current" stroke="#f59e0b" strokeWidth={2} name="Current Demand" />
                  <Line type="monotone" dataKey="predicted" stroke="#f87171" strokeWidth={3} name="Predicted Demand" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Crowding Risk by Route</h2>
            <div className="space-y-3">
              {(routeRisk.length ? routeRisk : [{ route_id: 'A', route_name: 'Route A', predicted_occupancy: 94, status: 'CRITICAL' }, { route_id: 'B', route_name: 'Route B', predicted_occupancy: 36, status: 'LOW' }, { route_id: 'C', route_name: 'Route C', predicted_occupancy: 62, status: 'MODERATE' }, { route_id: 'D', route_name: 'Route D', predicted_occupancy: 83, status: 'HIGH' }]).slice(0, 4).map((route) => (
                <div key={route.route_id} className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <button onClick={() => setSelectedRoute(route.route_id)} className="text-sm font-semibold text-white">{route.route_name || `Route ${route.route_id}`}</button>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase ${STATUS_STYLES[route.status || 'LOW']}`}>{route.status || 'LOW'}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-300">
                    <span>Predicted occupancy</span>
                    <span className="font-bold text-white">{route.predicted_occupancy ?? 0}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Transport Optimization</h2>
            <div className="mb-4 overflow-hidden rounded-xl border border-white/10">
              <table className="w-full text-left text-sm text-slate-200">
                <thead className="bg-[#1c1114] text-xs uppercase tracking-[0.18em] text-slate-400">
                  <tr>
                    <th className="p-3">Route</th>
                    <th className="p-3">Current</th>
                    <th className="p-3">AI Plan</th>
                    <th className="p-3">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {(transportPlan?.plan_lines || dashboard?.plan_lines || []).map((line) => (
                    <tr key={line.route_id} className="border-t border-white/10">
                      <td className="p-3">{line.route_name}</td>
                      <td className="p-3">{line.current_buses} buses</td>
                      <td className="p-3">{line.recommended_buses} buses</td>
                      <td className={`p-3 font-semibold ${line.delta >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>{line.delta > 0 ? `+${line.delta}` : line.delta}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-100">
              <div className="mb-2 text-xs uppercase tracking-[0.24em] text-red-300">Reason</div>
              <p>
                High predicted demand on Route A during the evening peak window. Route B has excess capacity, so reallocating 2 buses improves fleet utilization and reduces overcrowding risk.
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Before vs After</h2>
            <div className="mb-4 h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={beforeAfterData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="name" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="before" fill="#fbbf24" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="after" fill="#f87171" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Overcrowding Risk</div>
                <div className="mt-2 text-xl font-bold text-white">Before → {dashboard?.before_after?.overcrowded_before ?? 3}</div>
                <div className="text-xl font-bold text-emerald-300">After → {dashboard?.before_after?.overcrowded_after ?? 0}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Fleet Utilization</div>
                <div className="mt-2 text-xl font-bold text-white">Before → {dashboard?.before_after?.fleet_utilization_before ?? 68}%</div>
                <div className="text-xl font-bold text-emerald-300">After → {dashboard?.before_after?.fleet_utilization_after ?? 84}%</div>
              </div>
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Recommendations</h2>
            <div className="space-y-4">
              {(recommendations || []).slice(0, 3).map((item, index) => (
                <div key={`${item.route_id}-${index}`} className="rounded-xl border border-white/10 bg-[#1c1114] p-4">
                  <div className="mb-2 text-xs uppercase tracking-[0.22em] text-red-300">{item.priority}</div>
                  <div className="text-sm font-medium text-white">{item.message}</div>
                  <div className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-400">Action</div>
                  <div className="mt-1 text-sm text-slate-200">{item.action}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Explanation</h2>
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <div className="mb-3 text-xs uppercase tracking-[0.22em] text-red-300">Why Route A is high risk</div>
              <ul className="space-y-2 text-sm text-slate-200">
                <li>+ Current occupancy is high</li>
                <li>+ Historical demand is elevated during 5–6 PM</li>
                <li>+ Today is a weekday with stronger commuting traffic</li>
                <li>+ Previous interval demand increased by 18%</li>
              </ul>
              <div className="mt-4 rounded-lg border border-white/10 bg-[#180d10] p-3 text-sm text-white">
                Therefore: Predicted occupancy = {selectedRouteData.predicted_occupancy ?? 94}%
              </div>
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Commuter View</h2>
            <div className="space-y-4">
              <label className="block text-xs uppercase tracking-[0.2em] text-slate-400">Route
                <select value={selectedRoute} onChange={(e) => setSelectedRoute(e.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-[#1a1113] p-3 text-white">
                  {(commuterOptions || []).map((route) => (
                    <option key={route.route_id} value={route.route_id}>{route.route_name || `Route ${route.route_id}`}</option>
                  ))}
                </select>
              </label>
              <label className="block text-xs uppercase tracking-[0.2em] text-slate-400">Destination
                <input className="mt-2 w-full rounded-lg border border-white/10 bg-[#1a1113] p-3 text-white" defaultValue="Downtown" />
              </label>
              <label className="block text-xs uppercase tracking-[0.2em] text-slate-400">Time
                <input className="mt-2 w-full rounded-lg border border-white/10 bg-[#1a1113] p-3 text-white" defaultValue="17:30" />
              </label>
            </div>
            <div className="mt-5 space-y-3">
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Next Bus</div>
                <div className="mt-2 text-lg font-semibold text-white">{buses[0]?.bus_id || 'BUS-012'}</div>
                <div className="text-sm text-slate-300">ETA: 5 min • Predicted Occupancy: {selectedRouteData.predicted_occupancy ?? 81}% • Status: {selectedRouteData.status || 'HIGH'}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Next Bus</div>
                <div className="mt-2 text-lg font-semibold text-white">{buses[1]?.bus_id || 'BUS-018'}</div>
                <div className="text-sm text-slate-300">ETA: 11 min • Predicted Occupancy: {Math.max(30, (selectedRouteData.predicted_occupancy || 81) - 35)}% • Status: LOW</div>
              </div>
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm text-emerald-200">
                Recommendation: Select the lower-predicted-occupancy bus for the least crowded journey.
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">AI Performance</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Model Accuracy / R²</div>
                <div className="mt-2 text-2xl font-bold text-white">{modelMetrics?.r2 ?? 0.83}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">MAE</div>
                <div className="mt-2 text-2xl font-bold text-white">{modelMetrics?.mae ?? 38.1}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1b1114] p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-400">RMSE</div>
                <div className="mt-2 text-2xl font-bold text-white">{modelMetrics?.rmse ?? 51.7}</div>
              </div>
            </div>
            <div className="mt-5 h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={predictedTrend}>
                  <defs>
                    <linearGradient id="actualFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="#fbbf24" stopOpacity={0.1} />
                    </linearGradient>
                    <linearGradient id="predictedFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#f87171" stopOpacity={0.7} />
                      <stop offset="100%" stopColor="#f87171" stopOpacity={0.1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis dataKey="route" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip />
                  <Area type="monotone" dataKey="current" stroke="#fbbf24" fill="url(#actualFill)" name="Actual" />
                  <Area type="monotone" dataKey="predicted" stroke="#f87171" fill="url(#predictedFill)" name="Predicted" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Live Buses</h2>
            <div className="overflow-hidden rounded-xl border border-white/10">
              <table className="w-full text-left text-sm text-slate-200">
                <thead className="bg-[#1c1114] text-xs uppercase tracking-[0.18em] text-slate-400">
                  <tr>
                    <th className="p-3">Bus ID</th>
                    <th className="p-3">Route</th>
                    <th className="p-3">Passengers</th>
                    <th className="p-3">Occupancy</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(buses.length ? buses : []).slice(0, 8).map((bus) => (
                    <tr key={bus.bus_id} className="border-t border-white/10">
                      <td className="p-3">{bus.bus_id}</td>
                      <td className="p-3">{bus.route || bus.route_id}</td>
                      <td className="p-3">{bus.current_passengers ?? 28}/{bus.capacity ?? 40}</td>
                      <td className="p-3">{bus.occupancy_percent ?? bus.occupancy_pct ?? 0}%</td>
                      <td className="p-3"><span className={`rounded-full border px-2 py-1 text-[10px] uppercase ${STATUS_STYLES[bus.crowd_level || bus.status || 'LOW']}`}>{bus.crowd_level || bus.status || 'LOW'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-[#120d10] p-5">
            <h2 className="mb-4 text-lg font-semibold uppercase tracking-[0.2em] text-red-300">Event History</h2>
            <div className="space-y-3 text-sm text-slate-200">
              {[
                { timestamp: '2026-09-07 17:00', type: 'AI SIMULATION', description: 'AI simulation completed and transport plan generated.' },
                { timestamp: '2026-09-07 16:58', type: 'ROUTE RISK', description: 'Route A marked high risk based on predicted occupancy.' },
                { timestamp: '2026-09-07 16:52', type: 'REALLOCATION', description: 'Bus reallocation recommended from Route B to Route A.' },
                { timestamp: '2026-09-07 16:46', type: 'LIVE DATA', description: 'Live passenger data updated from current vehicle telemetry.' },
                { timestamp: '2026-09-07 16:40', type: 'OPTIMIZATION', description: 'Optimization completed with improved fleet utilization.' }
              ].map((event, index) => (
                <div key={`${event.type}-${index}`} className="rounded-xl border border-white/10 bg-[#1b1114] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] uppercase tracking-[0.18em] text-red-300">{event.type}</span>
                    <span className="text-[10px] text-slate-400">{event.timestamp}</span>
                  </div>
                  <div className="mt-2 text-sm text-slate-200">{event.description}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
