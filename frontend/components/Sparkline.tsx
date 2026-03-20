'use client';

import { useEffect, useRef } from 'react';
import { SparklinePoint } from '@/hooks/useMarketData';

interface SparklineProps {
  data: SparklinePoint[];
  direction?: 'up' | 'down' | 'neutral';
  width?: number;
  height?: number;
}

export default function Sparkline({
  data,
  direction = 'neutral',
  width = 80,
  height = 28,
}: SparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // High-DPI support
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const values = data.map(p => p.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;

    const color = direction === 'up' ? '#26a641' : direction === 'down' ? '#f85149' : '#8b949e';

    const xStep = width / (data.length - 1);

    // Draw gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + '40');
    gradient.addColorStop(1, color + '00');

    ctx.beginPath();
    data.forEach((point, i) => {
      const x = i * xStep;
      const y = height - ((point.value - minVal) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    // Close path for fill
    const lastX = (data.length - 1) * xStep;
    ctx.lineTo(lastX, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    data.forEach((point, i) => {
      const x = i * xStep;
      const y = height - ((point.value - minVal) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.stroke();
  }, [data, direction, width, height]);

  if (data.length < 2) {
    return (
      <div
        style={{ width, height }}
        className="flex items-center justify-center"
      >
        <div className="skeleton" style={{ width: width * 0.8, height: 2 }} />
      </div>
    );
  }

  return <canvas ref={canvasRef} style={{ width, height }} />;
}
