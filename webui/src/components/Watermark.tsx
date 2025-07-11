import React from 'react';

const Watermark: React.FC<{ text: string }> = ({ text }) => {
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 24,
        right: 32,
        zIndex: 3,
        opacity: 0.22,
        fontSize: '2.2rem',
        fontWeight: 700,
        color: '#ff6600',
        pointerEvents: 'none',
        userSelect: 'none',
        textShadow: '0 2px 8px #181c24',
        transform: 'rotate(-8deg)',
      }}
      aria-hidden="true"
      tabIndex={-1}
    >
      {text}
    </div>
  );
};

export default Watermark;
