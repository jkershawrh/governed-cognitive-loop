import { motion } from 'motion/react';

const LAYER_PILLS: { label: string; color: string }[] = [
  { label: 'Falsification', color: 'var(--rh-red)' },
  { label: 'Evidence-grounded', color: 'var(--rh-teal)' },
  { label: 'Receding horizon', color: 'var(--rh-blue)' },
  { label: 'Honesty boundary', color: 'var(--rh-purple)' },
];

export default function Close() {
  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 32,
        maxWidth: 700,
        margin: '0 auto',
        textAlign: 'center',
        padding: '40px 0',
      }}
    >
      {/* Belief sentence */}
      <motion.p
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.6, ease: 'easeOut' }}
        style={{
          fontFamily: "'Red Hat Display', sans-serif",
          fontSize: 24,
          fontWeight: 700,
          lineHeight: 1.4,
          color: 'var(--text-primary)',
          margin: 0,
        }}
      >
        It makes hard calls the way a careful expert does: reads the real
        constraints from evidence, thinks ahead but commits only the next
        step, and tries to prove its own plan wrong before acting.
      </motion.p>

      {/* Layer pills */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.5, ease: 'easeOut' }}
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: 10,
        }}
      >
        {LAYER_PILLS.map((pill, i) => (
          <motion.span
            key={pill.label}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{
              delay: 0.6 + i * 0.12,
              type: 'spring',
              stiffness: 400,
              damping: 25,
            }}
            style={{
              background: pill.color,
              color: '#fff',
              padding: '6px 14px',
              borderRadius: 20,
              fontFamily: "'Red Hat Text', sans-serif",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {pill.label}
          </motion.span>
        ))}
      </motion.div>

      {/* Honesty disclaimer */}
      <motion.p
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1, duration: 0.5, ease: 'easeOut' }}
        style={{
          fontSize: 14,
          color: 'var(--text-dim)',
          lineHeight: 1.6,
          margin: 0,
          maxWidth: 600,
        }}
      >
        It does not promise to be right. It promises to stay inside the
        limits and to have tried to prove itself wrong first. That is the
        sentence they repeat.
      </motion.p>
    </motion.section>
  );
}
