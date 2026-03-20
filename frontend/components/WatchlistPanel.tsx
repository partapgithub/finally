'use client';

import { useState, useEffect, useCallback } from 'react';
import { PriceData, SparklinePoint } from '@/hooks/useMarketData';
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, formatCurrency } from '@/lib/api';
import Sparkline from './Sparkline';

interface WatchlistPanelProps {
  prices: Record<string, PriceData>;
  history: Record<string, SparklinePoint[]>;
  flashState: Record<string, 'up' | 'down' | null>;
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
  onWatchlistChange?: () => void;
}

export default function WatchlistPanel({
  prices,
  history,
  flashState,
  selectedTicker,
  onSelectTicker,
  onWatchlistChange,
}: WatchlistPanelProps) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [addInput, setAddInput] = useState('');
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);

  const loadWatchlist = useCallback(async () => {
    try {
      const items = await fetchWatchlist();
      setTickers(items.map(item => item.ticker));
    } catch {
      console.error('Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  const handleAdd = async () => {
    const ticker = addInput.trim().toUpperCase();
    if (!ticker) return;
    if (tickers.includes(ticker)) {
      setAddError('Already in watchlist');
      setTimeout(() => setAddError(null), 2000);
      return;
    }

    try {
      await addToWatchlist(ticker);
      setTickers(prev => [...prev, ticker]);
      setAddInput('');
      setAddError(null);
      onWatchlistChange?.();
    } catch {
      setAddError('Failed to add ticker');
      setTimeout(() => setAddError(null), 2000);
    }
  };

  const handleRemove = async (ticker: string) => {
    try {
      await removeFromWatchlist(ticker);
      setTickers(prev => prev.filter(t => t !== ticker));
      if (selectedTicker === ticker) {
        onSelectTicker(tickers.find(t => t !== ticker) ?? '');
      }
      onWatchlistChange?.();
    } catch {
      console.error('Failed to remove ticker');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAdd();
    }
  };

  return (
    <div
      className="flex flex-col h-full border-r"
      style={{ backgroundColor: '#161b22', borderColor: '#30363d' }}
    >
      {/* Panel Header */}
      <div
        className="px-3 py-2 border-b text-xs font-bold uppercase tracking-wider"
        style={{ borderColor: '#30363d', color: '#8b949e' }}
      >
        Watchlist
      </div>

      {/* Ticker List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="skeleton h-12 rounded" />
            ))}
          </div>
        ) : (
          tickers.map(ticker => {
            const priceData = prices[ticker];
            const sparkData = history[ticker] ?? [];
            const flash = flashState[ticker];
            const isSelected = ticker === selectedTicker;
            const changePercent = priceData?.changePercent ?? 0;
            const direction = priceData?.direction ?? 'neutral';

            return (
              <div
                key={ticker}
                className={`relative px-3 py-2 cursor-pointer transition-colors border-b ${
                  flash === 'up' ? 'flash-green' : flash === 'down' ? 'flash-red' : ''
                }`}
                style={{
                  borderColor: '#30363d',
                  backgroundColor: isSelected ? '#21262d' : undefined,
                  borderLeft: isSelected ? '2px solid #ecad0a' : '2px solid transparent',
                }}
                onClick={() => onSelectTicker(ticker)}
                onMouseEnter={() => setHoveredTicker(ticker)}
                onMouseLeave={() => setHoveredTicker(null)}
              >
                <div className="flex items-center justify-between gap-2">
                  {/* Left: Ticker + Price */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span
                        className="text-sm font-bold"
                        style={{ color: isSelected ? '#ecad0a' : '#e6edf3' }}
                      >
                        {ticker}
                      </span>
                      <span
                        className="text-xs font-mono"
                        style={{
                          color: direction === 'up' ? '#26a641' : direction === 'down' ? '#f85149' : '#8b949e',
                        }}
                      >
                        {changePercent >= 0 ? '+' : ''}{changePercent.toFixed(2)}%
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span
                        className="text-sm font-mono font-bold"
                        style={{ color: '#e6edf3' }}
                      >
                        {priceData ? formatCurrency(priceData.price) : '---'}
                      </span>
                    </div>
                  </div>

                  {/* Right: Sparkline */}
                  <div className="flex-shrink-0">
                    <Sparkline
                      data={sparkData}
                      direction={direction}
                      width={56}
                      height={28}
                    />
                  </div>
                </div>

                {/* Remove button on hover */}
                {hoveredTicker === ticker && (
                  <button
                    className="absolute top-1 right-1 w-4 h-4 flex items-center justify-center rounded text-xs transition-colors"
                    style={{ color: '#8b949e', backgroundColor: '#21262d' }}
                    onClick={e => {
                      e.stopPropagation();
                      handleRemove(ticker);
                    }}
                    title="Remove from watchlist"
                  >
                    ×
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Add Ticker Input */}
      <div className="p-3 border-t" style={{ borderColor: '#30363d' }}>
        {addError && (
          <div className="text-xs mb-1" style={{ color: '#f85149' }}>
            {addError}
          </div>
        )}
        <div className="flex gap-1">
          <input
            type="text"
            value={addInput}
            onChange={e => setAddInput(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="Add ticker..."
            maxLength={10}
            className="flex-1 text-xs px-2 py-1.5 rounded outline-none font-mono"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              color: '#e6edf3',
            }}
          />
          <button
            onClick={handleAdd}
            className="px-3 py-1.5 rounded text-xs font-bold transition-all hover:brightness-110"
            style={{ backgroundColor: '#209dd7', color: '#0d1117' }}
          >
            +
          </button>
        </div>
      </div>
    </div>
  );
}
