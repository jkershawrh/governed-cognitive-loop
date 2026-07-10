import { useState, useCallback, useRef } from 'react';
import { motion } from 'motion/react';
import { api } from '../api/client';
import type { LoopCycle } from '../api/types';
import { useCycleStore } from '../stores/useCycleStore';
import HorizonPlot from '../components/HorizonPlot';
import MetricCard from '../components/MetricCard';

interface HistoryPoint {
  step: number;
  value: number;
}

const TOTAL_STEPS = 8;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function Layer2Lookahead() {
  const { scenarioSeeded, scenarioMeta, seedScenario, addCycle } =
    useCycleStore();
  const [running, setRunning] = useState(false);
  const [step, setStep] = useState(0);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [latestCycle, setLatestCycle] = useState<LoopCycle | null>(null);
  const [plotKey, setPlotKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const disturbanceStep = scenarioMeta?.disturbance_step ?? 4;

  const runScenario = useCallback(async () => {
    setRunning(true);
    setError(null);
    setHistory([]);
    setLatestCycle(null);
    setStep(0);
    abortRef.current = false;

    try {
      let meta = scenarioMeta;
      if (!scenarioSeeded) {
        meta = await api.seedScenario('inference_fleet_spike', 42);
        seedScenario('inference_fleet_spike', 42, meta);
      }

      const distStep = meta?.disturbance_step ?? 4;
      const accumulatedHistory: HistoryPoint[] = [];

      for (let i = 0; i < TOTAL_STEPS; i++) {
        if (abortRef.current) break;

        setStep(i);

        const scenarioStep = await api.getScenarioStep(i);
        const response = await api.runCycle(scenarioStep.signals);
        const full = await api.getCycle(response.cycle_id);

        addCycle({ stepIndex: i, cycleId: full.cycle_id, cycle: full });

        // Extract average latency_ms from the signals
        const latencySignals = scenarioStep.signals.filter(
          (s) => s.metric === 'latency_ms',
        );
        const avgLatency =
          latencySignals.length > 0
            ? latencySignals.reduce((sum, s) => sum + s.value, 0) /
              latencySignals.length
            : 0;

        const point: HistoryPoint = { step: i, value: avgLatency };
        accumulatedHistory.push(point);
        setHistory([...accumulatedHistory]);
        setLatestCycle(full);

        if (i === distStep) {
          setPlotKey((prev) => prev + 1);
        }

        if (i < TOTAL_STEPS - 1) {
          await delay(400);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [scenarioSeeded, scenarioMeta, seedScenario, addCycle]);

  const predictionPoints =
    latestCycle?.trajectory.points.map((p) => ({
      step: p.step,
      value: p.value,
      lower: p.lower,
      upper: p.upper,
    })) ?? [];

  const constraintBands =
    latestCycle?.constraints_snapshot.map((c) => ({
      type: c.type,
      bound: c.bound,
      hard: c.hard,
      label: c.type,
    })) ?? [];

  const committedStepIndex = latestCycle?.committed
    ? latestCycle.action_plan?.committed_step_index ?? null
    : null;

  const rejection =
    latestCycle?.falsification?.verdict === 'fails'
      ? {
          step: 0,
          reason: latestCycle.falsification.failed_check ?? 'falsified',
        }
      : null;

  const trajectoryConfidence = latestCycle?.trajectory.confidence
    ? `${Math.round(latestCycle.trajectory.confidence * 100)}%`
    : '--';

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
          The Lookahead: Think ahead, commit one step, re-check
        </h2>
        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginTop: 8,
            lineHeight: 1.6,
          }}
        >
          A careful expert thinks several moves ahead but does not lock
          in the whole plan.
        </p>
      </div>

      {/* Hero: HorizonPlot */}
      <HorizonPlot
        history={history}
        prediction={predictionPoints}
        constraints={constraintBands}
        committedStep={committedStepIndex}
        rejection={rejection}
        nowStep={history.length}
        animateRedraw={step === disturbanceStep}
        plotKey={plotKey}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {!running ? (
          <button
            onClick={runScenario}
            style={{
              background: 'var(--rh-red)',
              color: '#fff',
              border: 'none',
              padding: 12,
              borderRadius: 8,
              fontFamily: "'Red Hat Text', sans-serif",
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Run Scenario
          </button>
        ) : (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '8px 16px',
              background: 'var(--surface-2)',
              borderRadius: 8,
            }}
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
              style={{
                width: 16,
                height: 16,
                border: '2px solid var(--rh-blue)',
                borderTopColor: 'transparent',
                borderRadius: '50%',
              }}
            />
            <span
              style={{
                fontFamily: "'Red Hat Mono', monospace",
                fontSize: 13,
                color: 'var(--text-secondary)',
              }}
            >
              Step {step + 1}/{TOTAL_STEPS}
            </span>
          </div>
        )}
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

      {history.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr 1fr',
              gap: 12,
            }}
          >
            <MetricCard
              label="Current Step"
              value={step + 1}
              color="var(--rh-blue)"
            />
            <MetricCard
              label="Trajectory Confidence"
              value={trajectoryConfidence}
              color="var(--rh-purple)"
            />
            <MetricCard
              label="Committed"
              value={latestCycle?.committed ? 'Yes' : 'No'}
              color={
                latestCycle?.committed
                  ? 'var(--rh-green)'
                  : 'var(--rh-red)'
              }
            />
            <MetricCard
              label="Horizon"
              value={`${latestCycle?.trajectory.horizon_steps ?? 10} steps`}
              color="var(--text-dim)"
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
            A human overcommits to sunk-cost plans. This one commits only the
            next step and re-checks every cycle.
          </div>
        </motion.div>
      )}
    </motion.section>
  );
}
