import { motion } from 'motion/react';

interface MetricCardProps {
  label: string;
  value: string | number;
  color?: string;
  detail?: string;
}

export default function MetricCard({ label, value, color, detail }: MetricCardProps) {
  return (
    <motion.div
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: 16,
      }}
    >
      <div
        style={{
          fontFamily: "'Red Hat Mono', monospace",
          fontSize: 28,
          fontWeight: 700,
          color: color ?? 'var(--text-primary)',
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontFamily: "'Red Hat Text', sans-serif",
          fontSize: 12,
          color: 'var(--text-dim)',
          marginTop: 4,
        }}
      >
        {label}
      </div>
      {detail != null && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--text-disabled)',
            marginTop: 2,
          }}
        >
          {detail}
        </div>
      )}
    </motion.div>
  );
}
