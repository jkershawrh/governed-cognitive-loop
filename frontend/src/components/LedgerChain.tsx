import { useState } from 'react';
import { motion } from 'motion/react';
import type { ChainEntry } from '../api/types';

const ENTRY_COLORS: Record<string, string> = {
  'gcl.classify': 'var(--rh-teal)',
  'gcl.predict': 'var(--rh-blue)',
  'gcl.interpret': 'var(--rh-purple)',
  'gcl.plan': 'var(--rh-orange)',
  'gcl.falsify': 'var(--rh-yellow)',
  'gcl.commit': 'var(--rh-green)',
  'gcl.reject': 'var(--rh-red)',
};

interface LedgerChainProps {
  entries: ChainEntry[];
}

export default function LedgerChain({ entries }: LedgerChainProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, position: 'relative' }}>
      <div
        style={{
          position: 'absolute',
          left: 15,
          top: 20,
          bottom: 20,
          width: 2,
          background: 'var(--border)',
        }}
      />
      {entries.map((entry, i) => (
        <LedgerEntry key={entry.entry_id} entry={entry} index={i} />
      ))}
    </div>
  );
}

function LedgerEntry({ entry, index }: { entry: ChainEntry; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const color = ENTRY_COLORS[entry.entry_type] ?? 'var(--text-dim)';

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1, type: 'spring', stiffness: 400, damping: 25 }}
      style={{ display: 'flex', gap: 12, padding: '8px 0', cursor: 'pointer' }}
      onClick={() => setExpanded(!expanded)}
    >
      <div
        style={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          marginTop: 4,
          zIndex: 1,
          border: '2px solid var(--surface-1)',
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
            }}
          >
            {entry.entry_type}
          </span>
          <span style={{ fontSize: 10, color: 'var(--text-disabled)' }}>
            {expanded ? '(collapse)' : '(expand)'}
          </span>
        </div>
        {expanded && (
          <motion.pre
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            style={{
              fontFamily: "'Red Hat Mono', monospace",
              fontSize: 10,
              color: 'var(--text-secondary)',
              background: 'var(--surface-2)',
              borderRadius: 6,
              padding: 10,
              marginTop: 6,
              overflow: 'auto',
              maxHeight: 200,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {JSON.stringify(entry.content, null, 2)}
          </motion.pre>
        )}
      </div>
    </motion.div>
  );
}
