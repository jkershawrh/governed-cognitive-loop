import { motion } from 'motion/react';
import type { Constraint } from '../api/types';

const TYPE_COLORS: Record<string, string> = {
  latency: 'var(--rh-orange)',
  capacity: 'var(--rh-blue)',
  budget: 'var(--rh-yellow)',
  compliance: 'var(--rh-red)',
  priority: 'var(--rh-purple)',
  residency: 'var(--rh-teal)',
  custom: 'var(--text-dim)',
};

interface ConstraintBadgeProps {
  constraint: Constraint;
  index?: number;
}

export default function ConstraintBadge({ constraint, index = 0 }: ConstraintBadgeProps) {
  const color = TYPE_COLORS[constraint.type] ?? 'var(--text-dim)';

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25, delay: index * 0.08 }}
      style={{
        background: 'var(--surface-2)',
        border: `1px solid ${color}`,
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
          background: color,
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontFamily: "'Red Hat Mono', monospace",
              fontSize: 12,
              fontWeight: 600,
              color,
              textTransform: 'uppercase',
            }}
          >
            {constraint.type}
          </span>
          <span
            style={{
              fontSize: 10,
              padding: '1px 6px',
              borderRadius: 4,
              background: constraint.hard ? 'var(--rh-red-dim)' : 'var(--surface-1)',
              color: constraint.hard ? 'var(--rh-red)' : 'var(--text-dim)',
              fontFamily: "'Red Hat Mono', monospace",
            }}
          >
            {constraint.hard ? 'HARD' : 'SOFT'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: "'Red Hat Mono', monospace" }}>
            bound: {constraint.bound}
          </span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-disabled)', marginTop: 4, fontFamily: "'Red Hat Mono', monospace" }}>
          confidence: {(constraint.confidence * 100).toFixed(0)}%
          {' | '}source: {constraint.source}
          {' | '}evidence: {constraint.justification_evidence_ids.length} item{constraint.justification_evidence_ids.length !== 1 ? 's' : ''}
        </div>
      </div>
    </motion.div>
  );
}
