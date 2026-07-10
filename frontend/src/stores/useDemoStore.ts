import { create } from 'zustand';

type Mode = 'intro' | 'layers';
type LayerIndex = 0 | 1 | 2 | 3 | 4;

interface DemoState {
  mode: Mode;
  layerIndex: LayerIndex;
  setMode: (mode: Mode) => void;
  setLayerIndex: (index: LayerIndex) => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  mode: 'intro',
  layerIndex: 0,
  setMode: (mode) => set({ mode }),
  setLayerIndex: (index) => set({ layerIndex: index }),
}));
