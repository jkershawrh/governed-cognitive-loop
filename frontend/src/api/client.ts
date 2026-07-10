import type {
  SignalInput,
  CycleResponse,
  LoopCycle,
  ChainEntry,
  ScenarioMeta,
} from './types';

const BASE = import.meta.env.VITE_API_URL ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${path} - ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health(): Promise<{ status: string }> {
    return request('/healthz');
  },

  runCycle(signals: SignalInput[]): Promise<CycleResponse> {
    return request('/api/v1/cycle', {
      method: 'POST',
      body: JSON.stringify({ signals }),
    });
  },

  getCycle(id: string): Promise<LoopCycle> {
    return request(`/api/v1/cycles/${encodeURIComponent(id)}`);
  },

  getChain(id: string): Promise<ChainEntry[]> {
    return request(`/api/v1/cycles/${encodeURIComponent(id)}/chain`);
  },

  listCycles(): Promise<LoopCycle[]> {
    return request('/api/v1/cycles');
  },

  reset(): Promise<{ status: string }> {
    return request('/api/v1/reset', { method: 'POST' });
  },

  seedScenario(scenario: string, seed: number): Promise<ScenarioMeta> {
    return request('/api/v1/scenario/seed', {
      method: 'POST',
      body: JSON.stringify({ scenario, seed }),
    });
  },

  getScenarioStep(step: number): Promise<{ step_index: number; signals: SignalInput[] }> {
    return request(`/api/v1/scenario/step/${step}`);
  },
};
