import { motion } from 'motion/react';

const LAYERS = ['0: Hook', '1: Evidence', '2: Lookahead', '3: Floor', 'Close'] as const;

interface LayerNavProps {
  activeIndex: number;
  onSelect: (index: 0 | 1 | 2 | 3 | 4) => void;
}

export default function LayerNav({ activeIndex, onSelect }: LayerNavProps) {
  return (
    <nav
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 24,
        padding: '12px 0',
      }}
    >
      {LAYERS.map((label, i) => {
        const active = i === activeIndex;
        return (
          <button
            key={label}
            onClick={() => onSelect(i as 0 | 1 | 2 | 3 | 4)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
            }}
          >
            <motion.div
              animate={{ scale: active ? 1.1 : 1 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: active ? 'var(--rh-red)' : 'var(--text-disabled)',
              }}
            />
            <span
              style={{
                fontSize: 10,
                fontFamily: "'Red Hat Text', sans-serif",
                color: active ? 'var(--rh-red)' : 'var(--text-disabled)',
                whiteSpace: 'nowrap',
              }}
            >
              {label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
