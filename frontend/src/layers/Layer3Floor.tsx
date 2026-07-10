import { useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { api } from '../api/client';
import type { LoopCycle, ChainEntry } from '../api/types';
import { useCycleStore } from '../stores/useCycleStore';
import LedgerChain from '../components/LedgerChain';
import MetricCard from '../components/MetricCard';

export default function Layer3Floor() {
  const { scenarioSeeded, seedScenario } = useCycleStore();
  const [running, setRunning] = useState(false);
  const [cycle, setCycle] = useState<LoopCycle | null>(null);
  const [chain, setChain] = useState<ChainEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const runCycle = useCallback(async () => {
    setRunning(true);
    setError(null);
    setCycle(null);
    setChain([]);

    try {
      if (!scenarioSeeded) {
        const meta = await api.seedScenario('inference_fleet_spike', 42);
        seedScenario('inference_fleet_spike', 42, meta);
      }

      const step = await api.getScenarioStep(1);
      const response = await api.runCycle(step.signals);
      const [full, chainEntries] = await Promise.all([
        api.getCycle(response.cycle_id),
        api.getChain(response.cycle_id),
      ]);
      setCycle(full);
      setChain(chainEntries);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [scenarioSeeded, seedScenario]);

  const objective = cycle?.objective ?? null;
  const committedStep =
    cycle?.action_plan?.steps[cycle.action_plan.committed_step_index] ?? null;

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
          The Floor: The creative part never touches the safety-critical lever
        </h2>
        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginTop: 8,
            lineHeight: 1.6,
          }}
        >
          Frame the problem with intuition, execute it with discipline.
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
          Running cycle and building ledger chain...
        </motion.div>
      )}

      {cycle && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          style={{ display: 'flex', flexDirection: 'column', gap: 24 }}
        >
          {/* Two-column layout */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 24,
              alignItems: 'start',
            }}
          >
            {/* Left column: Honesty Boundary */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              <div
                style={{
                  fontFamily: "'Red Hat Display', sans-serif",
                  fontSize: 16,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                }}
              >
                Honesty Boundary
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                {/* Box 1: LLM / ObjectiveInterpreter */}
                <motion.div
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 }}
                  style={{
                    flex: 1,
                    background: 'var(--surface-1)',
                    borderLeft: '3px solid var(--rh-purple)',
                    borderRadius: '0 8px 8px 0',
                    padding: 14,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "'Red Hat Mono', monospace",
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--rh-purple)',
                      textTransform: 'uppercase',
                    }}
                  >
                    ObjectiveInterpreter (LLM)
                  </div>
                  {objective && (
                    <>
                      <div
                        style={{
                          fontSize: 12,
                          color: 'var(--text-secondary)',
                          fontFamily: "'Red Hat Mono', monospace",
                        }}
                      >
                        terms: [{objective.terms.join(', ')}]
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: 'var(--text-dim)',
                          lineHeight: 1.4,
                        }}
                      >
                        {objective.rationale}
                      </div>
                    </>
                  )}
                </motion.div>

                {/* Arrow */}
                <motion.div
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4 }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 4,
                    flexShrink: 0,
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 2,
                      background: 'var(--text-disabled)',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        position: 'absolute',
                        right: -1,
                        top: -4,
                        width: 0,
                        height: 0,
                        borderLeft: '6px solid var(--text-disabled)',
                        borderTop: '5px solid transparent',
                        borderBottom: '5px solid transparent',
                      }}
                    />
                  </div>
                  <div
                    style={{
                      fontFamily: "'Red Hat Mono', monospace",
                      fontSize: 8,
                      color: 'var(--text-disabled)',
                      textAlign: 'center',
                      lineHeight: 1.3,
                      maxWidth: 60,
                    }}
                  >
                    objective only, never actions
                  </div>
                </motion.div>

                {/* Box 2: Controller (deterministic) */}
                <motion.div
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 }}
                  style={{
                    flex: 1,
                    background: 'var(--surface-1)',
                    borderLeft: '3px solid var(--rh-green)',
                    borderRadius: '0 8px 8px 0',
                    padding: 14,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "'Red Hat Mono', monospace",
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--rh-green)',
                      textTransform: 'uppercase',
                    }}
                  >
                    Controller (deterministic)
                  </div>
                  {committedStep && (
                    <>
                      <div
                        style={{
                          fontSize: 12,
                          color: 'var(--text-secondary)',
                          fontFamily: "'Red Hat Mono', monospace",
                        }}
                      >
                        action: {committedStep.action_type}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: 'var(--text-dim)',
                          fontFamily: "'Red Hat Mono', monospace",
                          lineHeight: 1.4,
                        }}
                      >
                        {Object.entries(committedStep.parameters)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(', ')}
                      </div>
                    </>
                  )}
                </motion.div>
              </div>
            </div>

            {/* Right column: Ledger Chain */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
              }}
            >
              <div
                style={{
                  fontFamily: "'Red Hat Display', sans-serif",
                  fontSize: 16,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                }}
              >
                Ledger Chain
              </div>
              {chain.length > 0 ? (
                <LedgerChain entries={chain} />
              ) : (
                <div
                  style={{
                    fontSize: 13,
                    color: 'var(--text-dim)',
                    padding: 16,
                  }}
                >
                  No chain entries loaded.
                </div>
              )}
            </div>
          </div>

          {/* MetricCards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: 12,
            }}
          >
            <MetricCard
              label="Ledger Entries"
              value={chain.length}
              color="var(--rh-teal)"
            />
            <MetricCard
              label="Objective Terms"
              value={objective?.terms.join(', ') ?? '--'}
              color="var(--rh-purple)"
            />
            <MetricCard
              label="Action Type"
              value={committedStep?.action_type ?? '--'}
              color="var(--rh-green)"
            />
          </div>

          {/* Turn callout */}
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
            It separates the creative framing from the guaranteed execution
            and keeps the receipt.
          </div>
        </motion.div>
      )}
    </motion.section>
  );
}
