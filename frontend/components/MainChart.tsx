'use client';

import { useEffect, useRef, useState } from 'react';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { SparklinePoint } from '@/hooks/useMarketData';
import { formatCurrency, formatPercent } from '@/lib/api';

interface MainChartProps {
  ticker: string | null;
  history: SparklinePoint[];
  currentPrice?: number;
  changePercent?: number;
  direction?: 'up' | 'down' | 'neutral';
}

export default function MainChart({
  ticker,
  history,
  currentPrice,
  changePercent = 0,
  direction = 'neutral',
}: MainChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [chartReady, setChartReady] = useState(false);

  const getLineColor = (dir: 'up' | 'down' | 'neutral') => {
    if (dir === 'up') return '#26a641';
    if (dir === 'down') return '#f85149';
    return '#209dd7';
  };

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
        crosshair: {
          vertLine: { color: '#30363d', width: 1 },
          horzLine: { color: '#30363d', width: 1 },
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

      const lineColor = getLineColor(direction);

      const series = chart.addSeries(lc.AreaSeries, {
        lineColor,
        topColor: lineColor + '40',
        bottomColor: lineColor + '00',
        lineWidth: 2,
        priceLineVisible: true,
        priceLineColor: lineColor,
        priceLineWidth: 1,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
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

  // Update series data when history changes
  useEffect(() => {
    if (!seriesRef.current || !chartReady || history.length === 0) return;

    try {
      const seen = new Map<number, number>();
      for (const point of history) {
        seen.set(point.time, point.value);
      }
      const sorted = Array.from(seen.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([time, value]) => ({ time: time as number, value }));

      if (sorted.length > 0) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        seriesRef.current.setData(sorted as any);
      }
    } catch {
      // Ignore chart errors
    }
  }, [history, chartReady]);

  // Update line color when direction changes
  useEffect(() => {
    if (!seriesRef.current || !chartReady) return;
    const lineColor = getLineColor(direction);
    try {
      seriesRef.current.applyOptions({
        lineColor,
        topColor: lineColor + '40',
        bottomColor: lineColor + '00',
        priceLineColor: lineColor,
      });
    } catch {
      // Ignore
    }
  }, [direction, chartReady]);

  if (!ticker) {
    return (
      <div
        className="h-full flex items-center justify-center"
        style={{ backgroundColor: '#1a1a2e' }}
      >
        <div className="text-center">
          <div className="text-4xl mb-3" style={{ color: '#30363d' }}>◈</div>
          <div style={{ color: '#6e7681' }}>Select a ticker to view chart</div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: '#1a1a2e' }}>
      {/* Chart Header */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b flex-shrink-0"
        style={{ borderColor: '#30363d' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold" style={{ color: '#ecad0a' }}>
            {ticker}
          </span>
          {currentPrice !== undefined && (
            <span className="text-lg font-mono font-bold" style={{ color: '#e6edf3' }}>
              {formatCurrency(currentPrice)}
            </span>
          )}
        </div>
        <div
          className="text-sm font-mono font-bold"
          style={{
            color: direction === 'up' ? '#26a641' : direction === 'down' ? '#f85149' : '#8b949e',
          }}
        >
          {changePercent !== undefined && formatPercent(changePercent)}
        </div>
      </div>

      {/* Chart Container */}
      <div className="flex-1 relative">
        {history.length < 2 && (
          <div
            className="absolute inset-0 flex items-center justify-center z-10"
            style={{ backgroundColor: '#1a1a2e' }}
          >
            <div style={{ color: '#6e7681' }}>Waiting for price data...</div>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  );
}
