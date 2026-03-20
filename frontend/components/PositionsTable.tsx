'use client';

import { Portfolio, formatCurrency, formatPercent } from '@/lib/api';
import { PriceData } from '@/hooks/useMarketData';

interface PositionsTableProps {
  portfolio: Portfolio | null;
  prices: Record<string, PriceData>;
  onSelectTicker?: (ticker: string) => void;
}

export default function PositionsTable({ portfolio, prices, onSelectTicker }: PositionsTableProps) {
  const positions = portfolio?.positions ?? [];

  // Merge live prices with position data
  const enrichedPositions = positions.map(pos => {
    const livePrice = prices[pos.ticker]?.price ?? pos.current_price;
    const unrealizedPnl = (livePrice - pos.avg_cost) * pos.quantity;
    const pnlPercent = pos.avg_cost > 0 ? ((livePrice - pos.avg_cost) / pos.avg_cost) * 100 : 0;
    return {
      ...pos,
      current_price: livePrice,
      unrealized_pnl: unrealizedPnl,
      pnl_percent: pnlPercent,
    };
  });

  if (enrichedPositions.length === 0) {
    return (
      <div
        className="h-full flex items-center justify-center"
        style={{ backgroundColor: '#161b22' }}
      >
        <div className="text-sm" style={{ color: '#6e7681' }}>
          No open positions
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto" style={{ backgroundColor: '#161b22' }}>
      <table className="w-full text-xs">
        <thead className="sticky top-0 z-10" style={{ backgroundColor: '#161b22' }}>
          <tr style={{ borderBottom: '1px solid #30363d' }}>
            {['Ticker', 'Qty', 'Avg Cost', 'Current', 'P&L', '% Chg'].map(col => (
              <th
                key={col}
                className="px-3 py-2 text-left font-bold uppercase tracking-wider"
                style={{ color: '#8b949e' }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {enrichedPositions.map((pos, i) => {
            const isPnlPositive = pos.unrealized_pnl >= 0;
            const pnlColor = isPnlPositive ? '#26a641' : '#f85149';

            return (
              <tr
                key={pos.ticker}
                className="cursor-pointer transition-colors hover:brightness-110"
                style={{
                  backgroundColor: i % 2 === 0 ? '#161b22' : '#1a1a2e',
                  borderBottom: '1px solid #30363d',
                }}
                onClick={() => onSelectTicker?.(pos.ticker)}
              >
                <td className="px-3 py-2">
                  <span className="font-bold" style={{ color: '#ecad0a' }}>
                    {pos.ticker}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono" style={{ color: '#e6edf3' }}>
                  {pos.quantity % 1 === 0
                    ? pos.quantity.toFixed(0)
                    : pos.quantity.toFixed(4)}
                </td>
                <td className="px-3 py-2 font-mono" style={{ color: '#8b949e' }}>
                  {formatCurrency(pos.avg_cost)}
                </td>
                <td className="px-3 py-2 font-mono" style={{ color: '#e6edf3' }}>
                  {formatCurrency(pos.current_price)}
                </td>
                <td className="px-3 py-2 font-mono font-bold" style={{ color: pnlColor }}>
                  {isPnlPositive ? '+' : ''}{formatCurrency(pos.unrealized_pnl)}
                </td>
                <td className="px-3 py-2 font-mono font-bold" style={{ color: pnlColor }}>
                  {formatPercent(pos.pnl_percent)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
