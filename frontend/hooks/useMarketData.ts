'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

export interface PriceData {
  ticker: string;
  price: number;
  previousPrice: number;
  changePercent: number;
  direction: 'up' | 'down' | 'neutral';
  timestamp: string;
}

export interface SparklinePoint {
  time: number;
  value: number;
}

export interface MarketDataState {
  prices: Record<string, PriceData>;
  history: Record<string, SparklinePoint[]>;
  flashState: Record<string, 'up' | 'down' | null>;
  connectionStatus: 'connected' | 'reconnecting' | 'disconnected';
}

const MAX_HISTORY_POINTS = 100;

export function useMarketData(): MarketDataState {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [history, setHistory] = useState<Record<string, SparklinePoint[]>>({});
  const [flashState, setFlashState] = useState<Record<string, 'up' | 'down' | null>>({});
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'reconnecting' | 'disconnected'>('reconnecting');

  const flashTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      // Backend sends a dict of all tickers: {"AAPL": {ticker, price, ...}, "AMZN": {...}}
      // Normalise to an array so we can handle both formats.
      const items: Array<{
        ticker: string;
        price: number;
        previous_price?: number;
        change_percent?: number;
        direction?: string;
        timestamp?: number | string;
      }> = data && typeof data === 'object' && !('ticker' in data)
        ? Object.values(data)
        : [data];

      for (const item of items) {
        const { ticker, price, previous_price, change_percent, direction, timestamp } = item;
        if (!ticker || price === undefined) continue;

        const priceData: PriceData = {
          ticker,
          price,
          previousPrice: previous_price ?? price,
          changePercent: change_percent ?? 0,
          direction: (direction as 'up' | 'down' | 'neutral') ?? 'neutral',
          timestamp: String(timestamp ?? new Date().toISOString()),
        };

        // Update prices
        setPrices(prev => ({ ...prev, [ticker]: priceData }));

        // Update history — use epoch seconds for lightweight-charts
        const ts = typeof timestamp === 'number' ? timestamp : Date.now() / 1000;
        const timeValue = Math.floor(ts);
        setHistory(prev => {
          const existing = prev[ticker] ?? [];
          const newPoint: SparklinePoint = { time: timeValue, value: price };
          const filtered = existing.filter(p => p.time !== timeValue);
          const updated = [...filtered, newPoint].slice(-MAX_HISTORY_POINTS);
          return { ...prev, [ticker]: updated };
        });

        // Flash state
        if (direction && direction !== 'neutral' && direction !== 'flat') {
          setFlashState(prev => ({ ...prev, [ticker]: direction as 'up' | 'down' }));
          if (flashTimersRef.current[ticker]) clearTimeout(flashTimersRef.current[ticker]);
          flashTimersRef.current[ticker] = setTimeout(() => {
            setFlashState(prev => ({ ...prev, [ticker]: null }));
          }, 600);
        }
      }
    } catch {
      // Ignore parse errors
    }
  }, []);

  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (eventSource) {
        eventSource.close();
      }

      setConnectionStatus('reconnecting');
      eventSource = new EventSource('/api/stream/prices');

      eventSource.onopen = () => {
        setConnectionStatus('connected');
      };

      eventSource.onmessage = handleMessage;

      eventSource.onerror = () => {
        setConnectionStatus('reconnecting');
        // EventSource will auto-retry, but we track the state
      };
    };

    connect();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      // Clear all flash timers
      Object.values(flashTimersRef.current).forEach(timer => clearTimeout(timer));
    };
  }, [handleMessage]);

  return { prices, history, flashState, connectionStatus };
}
