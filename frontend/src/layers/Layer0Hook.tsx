import { useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { api } from '../api/client';
import type { LoopCycle } from '../api/types';
import { useCycleStore } from '../stores/useCycleStore';
import FalsificationCard from '../components/FalsificationCard';
import MetricCard from '../components/MetricCard';

export default function Layer0Hook() {
  const { scenarioSeeded, seedScenario } = useCycleStore();
  const [running, setRunning] = useState(false);
  const [cycle, setCycle] = useState<LoopCycle | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runCycle = useCallback(async () => {
    setRunning(true);
    setError(null);
    setCycle(null);

    try {
      if (!scenarioSeeded) {
        const meta = await api.seedScenario('inference_fleet_spike', 42);
        seedScenario('inference_fleet_spike', 42, meta);
      }

      const step = await api.getScenarioStep(4);
      const response = await api.runCycle(step.signals);
      const full = await api.getCycle(response.cycle_id);
      setCycle(full);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [scenarioSeeded, seedScenario]);

  const committedStep =
    cycle?.action_plan?.steps[cycle.action_plan.committed_step_index] ?? null;
  const falsification = cycle?.falsification ?? null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      style={{ display: 'flex', flexDirection: 'column', gap: 24 }}
    >
      <div>
        <h2
          style={{
            fontFamily: "'Red Hat Display', sans-serif",
            fontSize: 28,
            fontWeight: 700,
            color: 'var(--text-primary)',
            margin: 0,
          }}
        >
          The Hook: It tries to prove its own plan wrong
        </h2>
        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginTop: 8,
            lineHeight: 1.6,
          }}
        >
          The difference between a novice and an expert is not speed.
          The expert pauses and asks what would make this the wrong call.
        </p>
      </div>

      <div>
        <button
          onClick={runCycle}
          disabled={running}
          style={{
            background: running ? 'var(--surface-2)' : 'var(--rh-red)',
            color: running ? 'var(--text-dim)' : '#fff',
            border: 'none',
            padding: 12,
            borderRadius: 8,
            fontFamily: "'Red Hat Text', sans-serif",
            fontSize: 14,
            fontWeight: 600,
            cursor: running ? 'not-allowed' : 'pointer',
          }}
        >
          {running ? 'Running...' : 'Run Cycle'}
        </button>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{
            background: 'var(--rh-red-dim)',
            color: 'var(--rh-red)',
            padding: 12,
            borderRadius: 8,
            fontSize: 13,
            fontFamily: "'Red Hat Mono', monospace",
          }}
        >
          {error}
        </motion.div>
      )}

      {running && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{
            color: 'var(--text-dim)',
            fontSize: 14,
            padding: 24,
            textAlign: 'center',
          }}
        >
          Running falsification cycle...
        </motion.div>
      )}

      {cycle && committedStep && falsification && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          style={{ display: 'flex', flexDirection: 'column', gap: 20 }}
        >
          <FalsificationCard action={committedStep} result={falsification} />

          <div
            style={{
              background: 'var(--surface-2)',
              borderLeft: '3px solid var(--rh-red)',
              borderRadius: '0 8px 8px 0',
              padding: '14px 18px',
              fontSize: 14,
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
            }}
          >
            A human does this on a good day. This one does it every cycle
            and never talks itself out of the check.
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <MetricCard
              label="Verdict"
              value={falsification.verdict === 'survives' ? 'Survives' : 'Fails'}
              color={
                falsification.verdict === 'survives'
                  ? 'var(--rh-green)'
                  : 'var(--rh-red)'
              }
            />
            <MetricCard
              label="Failed Check"
              value={falsification.failed_check ?? 'None'}
              color={
                falsification.failed_check ? 'var(--rh-red)' : 'var(--text-dim)'
              }
            />
          </div>
        </motion.div>
      )}
    </motion.section>
  );
}
