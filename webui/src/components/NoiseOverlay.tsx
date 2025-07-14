import React, { useEffect, useRef } from 'react';

const NoiseOverlay: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let running = true;
    const drawNoise = () => {
      if (!ctx) return;
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w;
      canvas.height = h;
      const imageData = ctx.createImageData(w, h);
      for (let i = 0; i < imageData.data.length; i += 4) {
        const shade = Math.floor(Math.random() * 60);
        imageData.data[i] = shade;
        imageData.data[i+1] = shade;
        imageData.data[i+2] = shade;
        imageData.data[i+3] = Math.random() > 0.98 ? 32 : 12;
      }
      ctx.putImageData(imageData, 0, 0);
      if (running) requestAnimationFrame(drawNoise);
    };
    drawNoise();
    return () => { running = false; };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 1,
        opacity: 0.18,
        mixBlendMode: 'screen',
      }}
      aria-hidden="true"
      tabIndex={-1}
    />
  );
};

export default NoiseOverlay;
