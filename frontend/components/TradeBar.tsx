'use client';

import { useState, useEffect } from 'react';
import { executeTrade, formatCurrency } from '@/lib/api';
import { PriceData } from '@/hooks/useMarketData';

interface TradeBarProps {
  selectedTicker: string | null;
  prices: Record<string, PriceData>;
  onTradeComplete?: () => void;
}

interface Toast {
  message: string;
  type: 'success' | 'error';
}

export default function TradeBar({ selectedTicker, prices, onTradeComplete }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker ?? '');
  const [quantity, setQuantity] = useState('');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  useEffect(() => {
    if (selectedTicker) {
      setTicker(selectedTicker);
    }
  }, [selectedTicker]);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleTrade = async (side: 'buy' | 'sell') => {
    const cleanTicker = ticker.trim().toUpperCase();
    const qty = parseFloat(quantity);

    if (!cleanTicker) {
      showToast('Enter a ticker symbol', 'error');
      return;
    }
    if (!qty || qty <= 0) {
      showToast('Enter a valid quantity', 'error');
      return;
    }

    setLoading(true);
    try {
      await executeTrade(cleanTicker, side, qty);
      const currentPrice = prices[cleanTicker]?.price;
      const priceStr = currentPrice ? ` @ ${formatCurrency(currentPrice)}` : '';
      const actionStr = side === 'buy' ? 'Bought' : 'Sold';
      showToast(
        `${actionStr} ${qty} ${cleanTicker}${priceStr}`,
        'success'
      );
      setQuantity('');
      onTradeComplete?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Trade failed';
      // Extract readable message
      const match = msg.match(/:\s*(.+)$/);
      showToast(match ? match[1].substring(0, 80) : msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const currentPrice = ticker ? prices[ticker.trim().toUpperCase()]?.price : undefined;

  return (
    <div
      className="flex flex-col gap-2 px-3 py-2 border-t"
      style={{ backgroundColor: '#161b22', borderColor: '#30363d' }}
    >
      {/* Toast notification */}
      {toast && (
        <div
          className="px-3 py-2 rounded text-xs font-mono transition-all"
          style={{
            backgroundColor: toast.type === 'success' ? '#26a64120' : '#f8514920',
            border: `1px solid ${toast.type === 'success' ? '#26a641' : '#f85149'}`,
            color: toast.type === 'success' ? '#26a641' : '#f85149',
          }}
        >
          {toast.message}
        </div>
      )}

      <div className="flex items-center gap-2">
        {/* Ticker input */}
        <div className="flex flex-col gap-0.5">
          <label className="text-xs" style={{ color: '#8b949e' }}>Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL"
            maxLength={10}
            className="w-24 px-2 py-1.5 text-sm font-mono rounded outline-none"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              color: '#ecad0a',
            }}
          />
        </div>

        {/* Quantity input */}
        <div className="flex flex-col gap-0.5">
          <label className="text-xs" style={{ color: '#8b949e' }}>Quantity</label>
          <input
            type="number"
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            placeholder="0"
            min="0.01"
            step="0.01"
            className="w-24 px-2 py-1.5 text-sm font-mono rounded outline-none"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              color: '#e6edf3',
            }}
          />
        </div>

        {/* Current price display */}
        {currentPrice !== undefined && (
          <div className="flex flex-col gap-0.5">
            <label className="text-xs" style={{ color: '#8b949e' }}>Market Price</label>
            <div
              className="px-2 py-1.5 text-sm font-mono rounded"
              style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#8b949e' }}
            >
              {formatCurrency(currentPrice)}
            </div>
          </div>
        )}

        {/* Cost estimate */}
        {currentPrice !== undefined && quantity && parseFloat(quantity) > 0 && (
          <div className="flex flex-col gap-0.5">
            <label className="text-xs" style={{ color: '#8b949e' }}>Est. Total</label>
            <div
              className="px-2 py-1.5 text-sm font-mono rounded"
              style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', color: '#209dd7' }}
            >
              {formatCurrency(currentPrice * parseFloat(quantity))}
            </div>
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Trade buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => handleTrade('buy')}
            disabled={loading}
            className="px-5 py-2 rounded text-sm font-bold transition-all hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: '#753991', color: '#fff' }}
          >
            {loading ? '...' : 'BUY'}
          </button>
          <button
            onClick={() => handleTrade('sell')}
            disabled={loading}
            className="px-5 py-2 rounded text-sm font-bold transition-all hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: '#f85149', color: '#fff' }}
          >
            {loading ? '...' : 'SELL'}
          </button>
        </div>
      </div>
    </div>
  );
}
