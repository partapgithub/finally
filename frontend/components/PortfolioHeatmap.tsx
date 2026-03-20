'use client';

import { Position } from '@/lib/api';
import { formatCurrency, formatPercent } from '@/lib/api';

interface PortfolioHeatmapProps {
  positions: Position[];
  onSelectTicker?: (ticker: string) => void;
}

function getPnlColor(pnlPercent: number): string {
  const clampedPct = Math.max(-10, Math.min(10, pnlPercent));
  const t = (clampedPct + 10) / 20; // 0 to 1, 0.5 is neutral

  if (t < 0.5) {
    // Red zone: deep red to neutral gray
    const ratio = t / 0.5;
    const r = Math.round(248 - (248 - 58) * ratio);
    const g = Math.round(81 - (81 - 50) * ratio);
    const b = Math.round(73 - (73 - 50) * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // Green zone: neutral gray to deep green
    const ratio = (t - 0.5) / 0.5;
    const r = Math.round(58 + (38 - 58) * ratio);
    const g = Math.round(50 + (166 - 50) * ratio);
    const b = Math.round(50 + (65 - 50) * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  }
}

export default function PortfolioHeatmap({ positions, onSelectTicker }: PortfolioHeatmapProps) {
  if (positions.length === 0) {
    return (
      <div
        className="h-full flex items-center justify-center rounded"
        style={{ backgroundColor: '#1a1a2e' }}
      >
        <div className="text-center">
          <div className="text-2xl mb-2" style={{ color: '#30363d' }}>▦</div>
          <div className="text-sm" style={{ color: '#6e7681' }}>No positions yet</div>
          <div className="text-xs mt-1" style={{ color: '#6e7681' }}>Buy stocks to see your portfolio heatmap</div>
        </div>
      </div>
    );
  }

  const totalValue = positions.reduce(
    (sum, p) => sum + p.quantity * p.current_price,
    0
  ) || 1;

  // Sort by position value descending
  const sorted = [...positions].sort(
    (a, b) => b.quantity * b.current_price - a.quantity * a.current_price
  );

  return (
    <div className="h-full p-1 flex flex-wrap gap-1 overflow-hidden">
      {sorted.map(position => {
        const posValue = position.quantity * position.current_price;
        const weight = posValue / totalValue;
        const pct = Math.max(weight * 100, 8); // minimum 8% for visibility
        const bgColor = getPnlColor(position.pnl_percent);

        return (
          <div
            key={position.ticker}
            className="flex flex-col items-center justify-center rounded cursor-pointer transition-all hover:brightness-110 hover:scale-[1.02] overflow-hidden"
            style={{
              backgroundColor: bgColor,
              width: `calc(${pct}% - 4px)`,
              minWidth: '60px',
              flexGrow: weight > 0.15 ? 1 : 0,
            }}
            onClick={() => onSelectTicker?.(position.ticker)}
            title={`${position.ticker}: ${formatCurrency(posValue)} (${formatPercent(position.pnl_percent)})`}
          >
            <div className="text-xs font-bold text-white/90 leading-tight">
              {position.ticker}
            </div>
            <div
              className="text-xs font-mono"
              style={{ color: position.pnl_percent >= 0 ? '#90ef90' : '#ffaaaa' }}
            >
              {formatPercent(position.pnl_percent)}
            </div>
            <div className="text-xs text-white/70 font-mono">
              {formatCurrency(posValue)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
