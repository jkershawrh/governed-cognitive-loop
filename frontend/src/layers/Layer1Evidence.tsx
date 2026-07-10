import { useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { api } from '../api/client';
import type { LoopCycle } from '../api/types';
import { useCycleStore } from '../stores/useCycleStore';
import ConstraintBadge from '../components/ConstraintBadge';
import MetricCard from '../components/MetricCard';

export default function Layer1Evidence() {
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

      const step = await api.getScenarioStep(0);
      const response = await api.runCycle(step.signals);
      const full = await api.getCycle(response.cycle_id);
      setCycle(full);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [scenarioSeeded, seedScenario]);

  const constraints = cycle?.constraints_snapshot ?? [];
  const deterministicCount = constraints.filter(
    (c) => c.source === 'deterministic',
  ).length;
  const avgConfidence =
    constraints.length > 0
      ? Math.round(
          (constraints.reduce((sum, c) => sum + c.confidence, 0) /
            constraints.length) *
            100,
        )
      : 0;

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
          The Evidence: It reads the situation, not a stale rulebook
        </h2>
        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginTop: 8,
            lineHeight: 1.6,
          }}
        >
          A good expert derives the real constraints from what is in front of them.
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
          Classifying constraints from evidence...
        </motion.div>
      )}

      {cycle && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          {constraints.map((constraint, i) => (
            <ConstraintBadge
              key={constraint.id}
              constraint={constraint}
              index={i}
            />
          ))}

          {/* Ghost card: dropped constraint */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.4 }}
            transition={{ delay: constraints.length * 0.08 + 0.2 }}
            style={{
              border: '1px dashed var(--text-disabled)',
              borderRadius: 8,
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--text-disabled)',
                flexShrink: 0,
              }}
            />
            <div>
              <div
                style={{
                  fontFamily: "'Red Hat Mono', monospace",
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--text-disabled)',
                  textTransform: 'uppercase',
                }}
              >
                dropped
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'var(--text-disabled)',
                  marginTop: 4,
                  fontFamily: "'Red Hat Mono', monospace",
                }}
              >
                No justifying evidence, dropped.
              </div>
            </div>
          </motion.div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 12,
              marginTop: 8,
            }}
          >
            <MetricCard
              label="Constraints Found"
              value={constraints.length}
              color="var(--rh-teal)"
            />
            <MetricCard
              label="Deterministic"
              value={deterministicCount}
              color="var(--rh-blue)"
            />
            <MetricCard
              label="Confidence"
              value={`${avgConfidence}%`}
              color="var(--rh-purple)"
            />
          </div>

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
            A human's rules are often habit and stale policy.
            These constraints carry the evidence that justifies them.
          </div>
        </motion.div>
      )}
    </motion.section>
  );
}
