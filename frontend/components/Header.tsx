'use client';

import { formatCurrency } from '@/lib/api';

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  connectionStatus: 'connected' | 'reconnecting' | 'disconnected';
}

export default function Header({ totalValue, cashBalance, connectionStatus }: HeaderProps) {
  const statusColor = {
    connected: '#26a641',
    reconnecting: '#ecad0a',
    disconnected: '#f85149',
  }[connectionStatus];

  const statusLabel = {
    connected: 'Live',
    reconnecting: 'Reconnecting',
    disconnected: 'Disconnected',
  }[connectionStatus];

  return (
    <header
      className="flex items-center justify-between px-4 py-2 border-b"
      style={{
        backgroundColor: '#161b22',
        borderColor: '#30363d',
        minHeight: '48px',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <div className="text-xl font-bold tracking-tight">
          <span style={{ color: '#e6edf3' }}>Fin</span>
          <span style={{ color: '#ecad0a' }}>Ally</span>
        </div>
        <div
          className="text-xs px-2 py-0.5 rounded"
          style={{ backgroundColor: '#21262d', color: '#8b949e' }}
        >
          AI Trading Workstation
        </div>
      </div>

      {/* Center: Portfolio Value */}
      <div className="flex items-center gap-6">
        <div className="text-center">
          <div className="text-xs" style={{ color: '#8b949e' }}>PORTFOLIO</div>
          <div className="font-mono font-bold text-base" style={{ color: '#e6edf3' }}>
            {formatCurrency(totalValue)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs" style={{ color: '#8b949e' }}>CASH</div>
          <div className="font-mono font-bold text-base" style={{ color: '#ecad0a' }}>
            {formatCurrency(cashBalance)}
          </div>
        </div>
      </div>

      {/* Right: Connection status */}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${connectionStatus === 'reconnecting' ? 'pulse-yellow' : ''}`}
          style={{ backgroundColor: statusColor }}
        />
        <span className="text-xs" style={{ color: '#8b949e' }}>
          {statusLabel}
        </span>
      </div>
    </header>
  );
}
