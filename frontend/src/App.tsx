import { useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import Header from './components/Header';
import LayerNav from './components/LayerNav';
import Layer0Hook from './layers/Layer0Hook';
import Layer1Evidence from './layers/Layer1Evidence';
import Layer2Lookahead from './layers/Layer2Lookahead';
import Layer3Floor from './layers/Layer3Floor';
import Close from './layers/Close';
import { useDemoStore } from './stores/useDemoStore';
import { useCycleStore } from './stores/useCycleStore';
import { api } from './api/client';

const LAYERS = [Layer0Hook, Layer1Evidence, Layer2Lookahead, Layer3Floor, Close] as const;

export default function App() {
  const mode = useDemoStore((s) => s.mode);
  const setMode = useDemoStore((s) => s.setMode);
  const layerIndex = useDemoStore((s) => s.layerIndex);
  const setLayerIndex = useDemoStore((s) => s.setLayerIndex);
  const resetAll = useCycleStore((s) => s.resetAll);

  const handleReset = useCallback(() => {
    api.reset().catch(() => {});
    resetAll();
    setMode('intro');
    setLayerIndex(0);
  }, [resetAll, setMode, setLayerIndex]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (mode === 'intro') {
        if (e.key === 'Enter') {
          setMode('layers');
        }
        return;
      }

      if (e.key === 'ArrowRight') {
        setLayerIndex(Math.min(layerIndex + 1, 4) as 0 | 1 | 2 | 3 | 4);
      } else if (e.key === 'ArrowLeft') {
        setLayerIndex(Math.max(layerIndex - 1, 0) as 0 | 1 | 2 | 3 | 4);
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [mode, layerIndex, setMode, setLayerIndex]);

  return (
    <div>
      <Header onReset={handleReset} />

      <main
        style={{
          maxWidth: 1200,
          margin: '0 auto',
          padding: 24,
        }}
      >
        <AnimatePresence mode="wait">
          {mode === 'intro' ? (
            <motion.div
              key="intro"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.35 }}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 'calc(100vh - 160px)',
                textAlign: 'center',
                gap: 16,
              }}
            >
              <h2
                style={{
                  fontFamily: "'Red Hat Display', sans-serif",
                  fontWeight: 700,
                  fontSize: 36,
                  color: 'var(--text-primary)',
                }}
              >
                Governed Cognitive Loop
              </h2>
              <p
                style={{
                  fontFamily: "'Red Hat Text', sans-serif",
                  fontSize: 16,
                  color: 'var(--text-secondary)',
                  maxWidth: 600,
                  lineHeight: 1.6,
                }}
              >
                It makes hard calls the way a careful expert does, and it never
                skips the step where it tries to prove itself wrong.
              </p>
              <p
                style={{
                  fontSize: 13,
                  color: 'var(--text-disabled)',
                  marginTop: 24,
                }}
              >
                Press Enter to begin
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="layers"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.35 }}
            >
              <LayerNav activeIndex={layerIndex} onSelect={setLayerIndex} />

              <AnimatePresence mode="wait">
                <motion.div
                  key={layerIndex}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.25 }}
                  style={{ marginTop: 24 }}
                >
                  {(() => {
                    const Layer = LAYERS[layerIndex];
                    return <Layer />;
                  })()}
                </motion.div>
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
