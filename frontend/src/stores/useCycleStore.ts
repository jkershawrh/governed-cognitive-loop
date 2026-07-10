import { create } from 'zustand';
import type { ScenarioMeta, LoopCycle } from '../api/types';

interface CycleEntry {
  stepIndex: number;
  cycleId: string;
  cycle: LoopCycle;
}

interface CycleState {
  scenarioSeeded: boolean;
  scenarioMeta: ScenarioMeta | null;
  cycles: CycleEntry[];
  seedScenario: (scenario: string, seed: number, meta: ScenarioMeta) => void;
  addCycle: (entry: CycleEntry) => void;
  resetAll: () => void;
}

export const useCycleStore = create<CycleState>((set) => ({
  scenarioSeeded: false,
  scenarioMeta: null,
  cycles: [],

  seedScenario: (_scenario, _seed, meta) =>
    set({
      scenarioSeeded: true,
      scenarioMeta: meta,
      cycles: [],
    }),

  addCycle: (entry) =>
    set((state) => ({
      cycles: [...state.cycles, entry],
    })),

  resetAll: () =>
    set({
      scenarioSeeded: false,
      scenarioMeta: null,
      cycles: [],
    }),
}));
