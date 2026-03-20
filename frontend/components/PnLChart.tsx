'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { fetchPortfolioHistory, PortfolioSnapshot, formatCurrency } from '@/lib/api';

export default function PnLChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [chartReady, setChartReady] = useState(false);
  const [currentValue, setCurrentValue] = useState<number | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      const data = await fetchPortfolioHistory();
      setSnapshots(data);
      if (data.length > 0) {
        setCurrentValue(data[data.length - 1].total_value);
      }
    } catch {
      // Ignore
    }
  }, []);

  useEffect(() => {
    loadHistory();
    const interval = setInterval(loadHistory, 15000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    let chart: IChartApi | null = null;
    let cleanup: (() => void) | undefined;

    import('lightweight-charts').then((lc) => {
      if (!containerRef.current) return;

      chart = lc.createChart(containerRef.current, {
        layout: {
          background: { type: lc.ColorType.Solid, color: '#1a1a2e' },
          textColor: '#8b949e',
        },
        grid: {
          vertLines: { color: '#21262d' },
          horzLines: { color: '#21262d' },
        },
        rightPriceScale: {
          borderColor: '#30363d',
        },
        timeScale: {
          borderColor: '#30363d',
          timeVisible: true,
        },
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });

      const series = chart.addSeries(lc.AreaSeries, {
        lineColor: '#209dd7',
        topColor: '#209dd740',
        bottomColor: '#209dd700',
        lineWidth: 2,
        priceLineVisible: false,
      });

      chartRef.current = chart;
      seriesRef.current = series as ISeriesApi<'Area'>;
      setChartReady(true);

      const resizeObserver = new ResizeObserver(() => {
        if (containerRef.current && chart) {
          chart.resize(containerRef.current.clientWidth, containerRef.current.clientHeight);
        }
      });

      if (containerRef.current) {
        resizeObserver.observe(containerRef.current);
      }

      cleanup = () => resizeObserver.disconnect();
    });

    return () => {
      cleanup?.();
      if (chart) {
        chart.remove();
        chartRef.current = null;
        seriesRef.current = null;
        setChartReady(false);
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update chart data
  useEffect(() => {
    if (!seriesRef.current || !chartReady || snapshots.length === 0) return;

    try {
      const seen = new Map<number, number>();
      for (const snap of snapshots) {
        const time = Math.floor(new Date(snap.recorded_at).getTime() / 1000);
        seen.set(time, snap.total_value);
      }

      const sorted = Array.from(seen.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([time, value]) => ({ time: time as number, value }));

      if (sorted.length > 0) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        seriesRef.current.setData(sorted as any);
      }
    } catch {
      // Ignore
    }
  }, [snapshots, chartReady]);

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: '#1a1a2e' }}>
      <div
        className="flex items-center justify-between px-3 py-1.5 border-b flex-shrink-0"
        style={{ borderColor: '#30363d' }}
      >
        <span className="text-xs font-bold uppercase tracking-wider" style={{ color: '#8b949e' }}>
          Portfolio P&amp;L
        </span>
        {currentValue !== null && (
          <span className="text-sm font-mono font-bold" style={{ color: '#209dd7' }}>
            {formatCurrency(currentValue)}
          </span>
        )}
      </div>

      {snapshots.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-sm" style={{ color: '#6e7681' }}>No history yet — make a trade!</div>
        </div>
      ) : (
        <div className="flex-1 relative">
          <div ref={containerRef} className="w-full h-full" />
        </div>
      )}
    </div>
  );
}
