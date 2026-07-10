import { motion } from 'motion/react';
import type { FalsificationResult, ActionStep } from '../api/types';

interface FalsificationCardProps {
  action: ActionStep;
  result: FalsificationResult;
}

export default function FalsificationCard({ action, result }: FalsificationCardProps) {
  const failed = result.verdict === 'fails';
  const color = failed ? 'var(--rh-red)' : 'var(--rh-green)';

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      style={{
        background: 'var(--surface-1)',
        border: `2px solid ${color}`,
        borderRadius: 10,
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: failed ? 'var(--rh-red-dim)' : 'var(--rh-green-dim)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16,
            fontWeight: 700,
            color,
          }}
        >
          {failed ? '✗' : '✓'}
        </div>
        <div>
          <div
            style={{
              fontFamily: "'Red Hat Display', sans-serif",
              fontSize: 18,
              fontWeight: 700,
              color,
            }}
          >
            {failed ? 'REJECTED' : 'SURVIVES'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            Falsification Gate
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        <div
          style={{
            flex: 1,
            background: 'var(--surface-2)',
            borderRadius: 8,
            padding: 12,
          }}
        >
          <div style={{ fontSize: 10, color: 'var(--text-dim)', marginBottom: 6, fontFamily: "'Red Hat Mono', monospace" }}>
            PROPOSED ACTION
          </div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{action.action_type}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, fontFamily: "'Red Hat Mono', monospace" }}>
            {Object.entries(action.parameters)
              .map(([k, v]) => `${k}: ${v}`)
              .join(', ')}
          </div>
        </div>

        {failed && result.failed_check && (
          <div
            style={{
              flex: 1,
              background: 'var(--rh-red-dim)',
              borderRadius: 8,
              padding: 12,
            }}
          >
            <div style={{ fontSize: 10, color: 'var(--rh-red)', marginBottom: 6, fontFamily: "'Red Hat Mono', monospace" }}>
              FAILED CHECK
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--rh-red)' }}>
              {result.failed_check}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
              {result.reasoning}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
