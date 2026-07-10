import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { api } from '../api/client';

interface HeaderProps {
  onReset?: () => void;
}

export default function Header({ onReset }: HeaderProps) {
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = () => {
      api
        .health()
        .then(() => {
          if (!cancelled) setHealthy(true);
        })
        .catch(() => {
          if (!cancelled) setHealthy(false);
        });
    };

    check();
    const id = setInterval(check, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        background: 'var(--surface-1)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <h1
        style={{
          fontFamily: "'Red Hat Display', sans-serif",
          fontWeight: 700,
          fontSize: 18,
          color: 'var(--text-primary)',
          margin: 0,
        }}
      >
        Governed Cognitive Loop
      </h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <motion.div
          animate={{
            scale: healthy ? [1, 1.3, 1] : 1,
            opacity: healthy ? [1, 0.6, 1] : 1,
          }}
          transition={{
            duration: 1.4,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: healthy ? 'var(--rh-green)' : 'var(--rh-red)',
          }}
          title={healthy ? 'Backend healthy' : 'Backend unreachable'}
        />

        <button
          onClick={onReset}
          style={{
            padding: '4px 12px',
            fontSize: 12,
            fontFamily: "'Red Hat Text', sans-serif",
            color: 'var(--text-secondary)',
            background: 'transparent',
            border: '1px solid var(--border)',
            borderRadius: 6,
            cursor: 'pointer',
          }}
        >
          Reset
        </button>
      </div>
    </header>
  );
}
