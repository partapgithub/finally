'use client';

import { useState, useEffect, useCallback } from 'react';
import { useMarketData } from '@/hooks/useMarketData';
import { fetchPortfolio, Portfolio } from '@/lib/api';
import Header from '@/components/Header';
import WatchlistPanel from '@/components/WatchlistPanel';
import MainChart from '@/components/MainChart';
import PortfolioHeatmap from '@/components/PortfolioHeatmap';
import PnLChart from '@/components/PnLChart';
import PositionsTable from '@/components/PositionsTable';
import TradeBar from '@/components/TradeBar';
import ChatPanel from '@/components/ChatPanel';

type CenterTab = 'heatmap' | 'pnl';

export default function Home() {
  const { prices, history, flashState, connectionStatus } = useMarketData();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [centerTab, setCenterTab] = useState<CenterTab>('heatmap');
  const [portfolioRefreshKey, setPortfolioRefreshKey] = useState(0);

  const loadPortfolio = useCallback(async () => {
    try {
      const data = await fetchPortfolio();
      setPortfolio(data);
    } catch {
      // Silent fail — will retry
    }
  }, []);

  // Initial load + polling every 5s
  useEffect(() => {
    loadPortfolio();
    const interval = setInterval(loadPortfolio, 5000);
    return () => clearInterval(interval);
  }, [loadPortfolio, portfolioRefreshKey]);

  const handleTradeComplete = useCallback(() => {
    setPortfolioRefreshKey(k => k + 1);
    setTimeout(loadPortfolio, 500);
  }, [loadPortfolio]);

  const handleWatchlistChange = useCallback(() => {
    // Triggers watchlist panel re-render via key could be added if needed
    // Watchlist panel manages its own state
  }, []);

  const selectedPriceData = selectedTicker ? prices[selectedTicker] : null;

  return (
    <div
      className="flex flex-col"
      style={{ height: '100vh', overflow: 'hidden', backgroundColor: '#0d1117' }}
    >
      {/* Header */}
      <Header
        totalValue={portfolio?.total_value ?? 0}
        cashBalance={portfolio?.cash_balance ?? 0}
        connectionStatus={connectionStatus}
      />

      {/* Main Grid */}
      <div
        className="flex-1 grid overflow-hidden"
        style={{
          gridTemplateColumns: '280px 1fr 340px',
          minHeight: 0,
        }}
      >
        {/* Left: Watchlist */}
        <WatchlistPanel
          prices={prices}
          history={history}
          flashState={flashState}
          selectedTicker={selectedTicker}
          onSelectTicker={setSelectedTicker}
          onWatchlistChange={handleWatchlistChange}
        />

        {/* Center: Charts, Table, Trade */}
        <div
          className="flex flex-col overflow-hidden"
          style={{ minHeight: 0 }}
        >
          {/* Main Price Chart */}
          <div style={{ height: '220px', flexShrink: 0 }}>
            <MainChart
              ticker={selectedTicker}
              history={selectedTicker ? (history[selectedTicker] ?? []) : []}
              currentPrice={selectedPriceData?.price}
              changePercent={selectedPriceData?.changePercent}
              direction={selectedPriceData?.direction}
            />
          </div>

          {/* Tab Bar: Heatmap / P&L */}
          <div
            className="flex items-center border-b border-t flex-shrink-0"
            style={{ borderColor: '#30363d', backgroundColor: '#161b22' }}
          >
            {(['heatmap', 'pnl'] as CenterTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setCenterTab(tab)}
                className="px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors"
                style={{
                  color: centerTab === tab ? '#ecad0a' : '#8b949e',
                  borderBottom: centerTab === tab ? '2px solid #ecad0a' : '2px solid transparent',
                  backgroundColor: 'transparent',
                }}
              >
                {tab === 'heatmap' ? 'Portfolio Heatmap' : 'P&L Chart'}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ height: '140px', flexShrink: 0 }}>
            {centerTab === 'heatmap' ? (
              <PortfolioHeatmap
                positions={portfolio?.positions ?? []}
                onSelectTicker={setSelectedTicker}
              />
            ) : (
              <PnLChart />
            )}
          </div>

          {/* Positions Table — fills remaining space */}
          <div className="flex-1 overflow-hidden border-t" style={{ borderColor: '#30363d', minHeight: 0 }}>
            <div
              className="px-3 py-1.5 border-b text-xs font-bold uppercase tracking-wider"
              style={{ borderColor: '#30363d', backgroundColor: '#161b22', color: '#8b949e' }}
            >
              Positions
            </div>
            <div style={{ height: 'calc(100% - 32px)', overflow: 'auto' }}>
              <PositionsTable
                portfolio={portfolio}
                prices={prices}
                onSelectTicker={setSelectedTicker}
              />
            </div>
          </div>

          {/* Trade Bar */}
          <div className="flex-shrink-0">
            <TradeBar
              selectedTicker={selectedTicker}
              prices={prices}
              onTradeComplete={handleTradeComplete}
            />
          </div>
        </div>

        {/* Right: Chat Panel */}
        <ChatPanel
          onTradeExecuted={handleTradeComplete}
          onWatchlistChanged={handleWatchlistChange}
        />
      </div>
    </div>
  );
}
