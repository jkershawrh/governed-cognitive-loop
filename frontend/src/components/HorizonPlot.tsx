import { useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';

interface HistoryPoint {
  step: number;
  value: number;
}

interface PredictionPoint {
  step: number;
  value: number;
  lower: number | null;
  upper: number | null;
}

interface ConstraintBand {
  type: string;
  bound: number;
  hard: boolean;
  label: string;
}

interface HorizonPlotProps {
  history: HistoryPoint[];
  prediction: PredictionPoint[];
  constraints: ConstraintBand[];
  committedStep: number | null;
  rejection: { step: number; reason: string } | null;
  nowStep: number;
  animateRedraw?: boolean;
  plotKey?: number;
}

const PADDING = { top: 32, right: 120, bottom: 40, left: 60 };
const WIDTH = 900;
const HEIGHT = 320;
const INNER_W = WIDTH - PADDING.left - PADDING.right;
const INNER_H = HEIGHT - PADDING.top - PADDING.bottom;

function scaleX(step: number, minStep: number, maxStep: number): number {
  if (maxStep === minStep) return PADDING.left + INNER_W / 2;
  return PADDING.left + ((step - minStep) / (maxStep - minStep)) * INNER_W;
}

function scaleY(value: number, minVal: number, maxVal: number): number {
  if (maxVal === minVal) return PADDING.top + INNER_H / 2;
  return PADDING.top + INNER_H - ((value - minVal) / (maxVal - minVal)) * INNER_H;
}

function pointsToPath(
  pts: { step: number; value: number }[],
  minStep: number,
  maxStep: number,
  minVal: number,
  maxVal: number,
): string {
  return pts
    .map((p, i) => {
      const x = scaleX(p.step, minStep, maxStep);
      const y = scaleY(p.value, minVal, maxVal);
      return `${i === 0 ? 'M' : 'L'}${x},${y}`;
    })
    .join(' ');
}

export default function HorizonPlot({
  history,
  prediction,
  constraints,
  committedStep,
  rejection,
  nowStep,
  animateRedraw = false,
  plotKey = 0,
}: HorizonPlotProps) {
  const { minStep, maxStep, minVal, maxVal } = useMemo(() => {
    const allSteps = [
      ...history.map((p) => p.step),
      ...prediction.map((p) => p.step + nowStep),
    ];
    const allValues = [
      ...history.map((p) => p.value),
      ...prediction.map((p) => p.value),
      ...prediction.filter((p) => p.lower != null).map((p) => p.lower!),
      ...prediction.filter((p) => p.upper != null).map((p) => p.upper!),
      ...constraints.map((c) => c.bound),
    ];

    const mn = allSteps.length ? Math.min(...allSteps) : 0;
    const mx = allSteps.length ? Math.max(...allSteps) : 10;
    const mnV = allValues.length ? Math.min(...allValues) * 0.9 : 0;
    const mxV = allValues.length ? Math.max(...allValues) * 1.1 : 10000;

    return { minStep: mn, maxStep: mx, minVal: mnV, maxVal: mxV };
  }, [history, prediction, constraints, nowStep]);

  const nowX = scaleX(nowStep, minStep, maxStep);

  const historyPath = useMemo(
    () => (history.length > 1 ? pointsToPath(history, minStep, maxStep, minVal, maxVal) : ''),
    [history, minStep, maxStep, minVal, maxVal],
  );

  const predictionPath = useMemo(() => {
    if (prediction.length < 2) return '';
    const shifted = prediction.map((p) => ({ step: p.step + nowStep, value: p.value }));
    return pointsToPath(shifted, minStep, maxStep, minVal, maxVal);
  }, [prediction, nowStep, minStep, maxStep, minVal, maxVal]);

  const envelopePath = useMemo(() => {
    const withBounds = prediction.filter((p) => p.lower != null && p.upper != null);
    if (withBounds.length < 2) return '';
    const upper = withBounds.map((p) => ({
      x: scaleX(p.step + nowStep, minStep, maxStep),
      y: scaleY(p.upper!, minVal, maxVal),
    }));
    const lower = [...withBounds].reverse().map((p) => ({
      x: scaleX(p.step + nowStep, minStep, maxStep),
      y: scaleY(p.lower!, minVal, maxVal),
    }));
    const all = [...upper, ...lower];
    return all.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.x},${pt.y}`).join(' ') + 'Z';
  }, [prediction, nowStep, minStep, maxStep, minVal, maxVal]);

  const yTicks = useMemo(() => {
    const range = maxVal - minVal;
    const step = Math.pow(10, Math.floor(Math.log10(range))) || 1000;
    const ticks: number[] = [];
    let t = Math.ceil(minVal / step) * step;
    while (t <= maxVal) {
      ticks.push(t);
      t += step;
    }
    return ticks;
  }, [minVal, maxVal]);

  return (
    <div
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: 8,
        overflow: 'hidden',
      }}
    >
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ width: '100%', height: 320 }}>
        {/* Y-axis grid lines and labels */}
        {yTicks.map((t) => {
          const y = scaleY(t, minVal, maxVal);
          return (
            <g key={t}>
              <line
                x1={PADDING.left}
                y1={y}
                x2={WIDTH - PADDING.right}
                y2={y}
                stroke="var(--border)"
                strokeWidth={0.5}
              />
              <text
                x={PADDING.left - 8}
                y={y + 4}
                textAnchor="end"
                fill="var(--text-disabled)"
                fontSize={10}
                fontFamily="'Red Hat Mono', monospace"
              >
                {t >= 1000 ? `${(t / 1000).toFixed(1)}k` : t}
              </text>
            </g>
          );
        })}

        {/* Constraint boundary bands */}
        {constraints.map((c, i) => {
          const y = scaleY(c.bound, minVal, maxVal);
          return (
            <g key={`c-${i}`}>
              <rect
                x={PADDING.left}
                y={c.hard ? y : y - 2}
                width={INNER_W}
                height={c.hard ? HEIGHT - PADDING.bottom - y : 4}
                fill={c.hard ? 'var(--rh-red-dim)' : 'rgba(255, 204, 23, 0.08)'}
              />
              <line
                x1={PADDING.left}
                y1={y}
                x2={WIDTH - PADDING.right}
                y2={y}
                stroke={c.hard ? 'var(--rh-red)' : 'var(--rh-yellow)'}
                strokeWidth={1.5}
                strokeDasharray="6 4"
                opacity={0.6}
              />
              <text
                x={WIDTH - PADDING.right + 6}
                y={y + 4}
                fill={c.hard ? 'var(--rh-red)' : 'var(--rh-yellow)'}
                fontSize={9}
                fontFamily="'Red Hat Mono', monospace"
              >
                {c.label} ({c.bound >= 1000 ? `${(c.bound / 1000).toFixed(0)}k` : c.bound})
              </text>
            </g>
          );
        })}

        {/* Confidence envelope */}
        {envelopePath && (
          <motion.path
            key={`env-${plotKey}`}
            d={envelopePath}
            fill="var(--rh-blue-dim)"
            initial={animateRedraw ? { opacity: 0 } : false}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          />
        )}

        {/* History line */}
        {historyPath && (
          <path
            d={historyPath}
            fill="none"
            stroke="var(--text-secondary)"
            strokeWidth={2}
          />
        )}
        {history.map((p) => (
          <circle
            key={`h-${p.step}`}
            cx={scaleX(p.step, minStep, maxStep)}
            cy={scaleY(p.value, minVal, maxVal)}
            r={3}
            fill="var(--text-secondary)"
          />
        ))}

        {/* Prediction line */}
        {predictionPath && (
          <motion.path
            key={`pred-${plotKey}`}
            d={predictionPath}
            fill="none"
            stroke="var(--rh-blue)"
            strokeWidth={2}
            strokeDasharray="6 4"
            initial={animateRedraw ? { pathLength: 0, opacity: 0 } : false}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.8, type: 'spring', stiffness: 100, damping: 20 }}
          />
        )}

        {/* NOW vertical line */}
        <line
          x1={nowX}
          y1={PADDING.top}
          x2={nowX}
          y2={HEIGHT - PADDING.bottom}
          stroke="var(--text-disabled)"
          strokeWidth={1}
          strokeDasharray="4 4"
        />
        <text
          x={nowX}
          y={PADDING.top - 8}
          textAnchor="middle"
          fill="var(--text-disabled)"
          fontSize={10}
          fontFamily="'Red Hat Mono', monospace"
          fontWeight={600}
        >
          NOW
        </text>

        {/* Committed step marker */}
        {committedStep != null && prediction.length > committedStep && (
          <g>
            <motion.circle
              cx={scaleX(prediction[committedStep].step + nowStep, minStep, maxStep)}
              cy={scaleY(prediction[committedStep].value, minVal, maxVal)}
              r={7}
              fill="none"
              stroke="var(--rh-green)"
              strokeWidth={2}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20, delay: 0.5 }}
            />
            <motion.circle
              cx={scaleX(prediction[committedStep].step + nowStep, minStep, maxStep)}
              cy={scaleY(prediction[committedStep].value, minVal, maxVal)}
              r={3}
              fill="var(--rh-green)"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20, delay: 0.5 }}
            />
            <text
              x={scaleX(prediction[committedStep].step + nowStep, minStep, maxStep)}
              y={scaleY(prediction[committedStep].value, minVal, maxVal) + 18}
              textAnchor="middle"
              fill="var(--rh-green)"
              fontSize={9}
              fontFamily="'Red Hat Mono', monospace"
              fontWeight={600}
            >
              COMMITTED
            </text>
          </g>
        )}

        {/* Rejection marker */}
        {rejection && prediction.length > rejection.step && (
          <g>
            <motion.g
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20, delay: 0.3 }}
            >
              {(() => {
                const cx = scaleX(prediction[rejection.step].step + nowStep, minStep, maxStep);
                const cy = scaleY(prediction[rejection.step].value, minVal, maxVal);
                const s = 6;
                return (
                  <>
                    <line x1={cx - s} y1={cy - s} x2={cx + s} y2={cy + s} stroke="var(--rh-red)" strokeWidth={2.5} />
                    <line x1={cx + s} y1={cy - s} x2={cx - s} y2={cy + s} stroke="var(--rh-red)" strokeWidth={2.5} />
                    <text
                      x={cx}
                      y={cy - 12}
                      textAnchor="middle"
                      fill="var(--rh-red)"
                      fontSize={8}
                      fontFamily="'Red Hat Mono', monospace"
                      fontWeight={600}
                    >
                      {rejection.reason}
                    </text>
                  </>
                );
              })()}
            </motion.g>
          </g>
        )}

        {/* X-axis label */}
        <text
          x={WIDTH / 2}
          y={HEIGHT - 6}
          textAnchor="middle"
          fill="var(--text-disabled)"
          fontSize={10}
          fontFamily="'Red Hat Mono', monospace"
        >
          Horizon Steps
        </text>
      </svg>
    </div>
  );
}
