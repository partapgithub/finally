'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { sendChatMessage, fetchChatHistory, TradeAction, WatchlistChange, formatCurrency } from '@/lib/api';

interface LocalMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  trades?: TradeAction[];
  watchlistChanges?: WatchlistChange[];
  timestamp: string;
}

interface ChatPanelProps {
  onTradeExecuted?: () => void;
  onWatchlistChanged?: () => void;
}

export default function ChatPanel({ onTradeExecuted, onWatchlistChanged }: ChatPanelProps) {
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }, 50);
  }, []);

  // Load chat history on mount
  useEffect(() => {
    fetchChatHistory()
      .then(history => {
        const mapped: LocalMessage[] = history.map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          trades: m.actions?.trades,
          watchlistChanges: m.actions?.watchlist_changes,
          timestamp: m.created_at,
        }));
        setMessages(mapped);
        setHistoryLoaded(true);
        scrollToBottom();
      })
      .catch(() => {
        setHistoryLoaded(true);
      });
  }, [scrollToBottom]);

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;

    const userMessage: LocalMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(msg);

      const assistantMessage: LocalMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        trades: response.trades,
        watchlistChanges: response.watchlist_changes,
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Notify parent if trades were executed
      if (response.trades && response.trades.length > 0) {
        onTradeExecuted?.();
      }
      if (response.watchlist_changes && response.watchlist_changes.length > 0) {
        onWatchlistChanged?.();
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Failed to get response';
      setMessages(prev => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Error: ${errMsg}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  return (
    <div
      className="flex flex-col h-full border-l"
      style={{ backgroundColor: '#161b22', borderColor: '#30363d' }}
    >
      {/* Chat Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b flex-shrink-0"
        style={{ borderColor: '#30363d', backgroundColor: '#161b22' }}
      >
        <div
          className="w-6 h-6 rounded flex items-center justify-center text-sm flex-shrink-0"
          style={{ backgroundColor: '#753991' }}
        >
          ✦
        </div>
        <div>
          <div className="text-sm font-bold" style={{ color: '#e6edf3' }}>
            Fin<span style={{ color: '#ecad0a' }}>Ally</span> AI
          </div>
          <div className="text-xs" style={{ color: '#8b949e' }}>
            Your trading assistant
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-3"
      >
        {!historyLoaded ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="skeleton h-12 rounded" />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 py-8">
            <div className="text-3xl" style={{ color: '#30363d' }}>✦</div>
            <div className="text-sm" style={{ color: '#8b949e' }}>
              Ask me about your portfolio, request analysis, or place trades.
            </div>
            <div className="space-y-1.5 text-xs" style={{ color: '#6e7681' }}>
              <div className="px-3 py-1.5 rounded" style={{ backgroundColor: '#21262d' }}>
                &quot;How is my portfolio performing?&quot;
              </div>
              <div className="px-3 py-1.5 rounded" style={{ backgroundColor: '#21262d' }}>
                &quot;Buy 5 shares of AAPL&quot;
              </div>
              <div className="px-3 py-1.5 rounded" style={{ backgroundColor: '#21262d' }}>
                &quot;What stocks should I watch?&quot;
              </div>
            </div>
          </div>
        ) : (
          messages.map(msg => (
            <div
              key={msg.id}
              className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className="max-w-full px-3 py-2 rounded-lg text-xs leading-relaxed break-words"
                style={{
                  backgroundColor: msg.role === 'user' ? '#753991' : '#1a1a2e',
                  color: '#e6edf3',
                  border: msg.role === 'assistant' ? '1px solid #30363d' : 'none',
                  maxWidth: '90%',
                }}
              >
                {msg.content}
              </div>

              {/* Trade confirmations */}
              {msg.trades && msg.trades.length > 0 && (
                <div className="space-y-1 w-full">
                  {msg.trades.map((trade, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 px-2 py-1 rounded text-xs font-mono"
                      style={{
                        backgroundColor: '#26a64115',
                        border: '1px solid #26a641',
                        color: '#26a641',
                      }}
                    >
                      <span>✓</span>
                      <span>
                        {trade.side === 'buy' ? 'Bought' : 'Sold'} {trade.quantity} {trade.ticker}
                        {trade.price ? ` @ ${formatCurrency(trade.price)}` : ''}
                      </span>
                      {trade.error && (
                        <span style={{ color: '#f85149' }}>— {trade.error}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Watchlist changes */}
              {msg.watchlistChanges && msg.watchlistChanges.length > 0 && (
                <div className="space-y-1 w-full">
                  {msg.watchlistChanges.map((change, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 px-2 py-1 rounded text-xs font-mono"
                      style={{
                        backgroundColor: '#209dd715',
                        border: '1px solid #209dd7',
                        color: '#209dd7',
                      }}
                    >
                      <span>{change.action === 'add' ? '+' : '−'}</span>
                      <span>
                        {change.action === 'add' ? 'Added' : 'Removed'} {change.ticker} from watchlist
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="text-xs" style={{ color: '#6e7681' }}>
                {formatTime(msg.timestamp)}
              </div>
            </div>
          ))
        )}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-start gap-2">
            <div
              className="w-6 h-6 rounded flex items-center justify-center text-sm flex-shrink-0"
              style={{ backgroundColor: '#753991' }}
            >
              ✦
            </div>
            <div
              className="px-3 py-2 rounded-lg"
              style={{ backgroundColor: '#1a1a2e', border: '1px solid #30363d' }}
            >
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full dot-1" style={{ backgroundColor: '#8b949e' }} />
                <div className="w-1.5 h-1.5 rounded-full dot-2" style={{ backgroundColor: '#8b949e' }} />
                <div className="w-1.5 h-1.5 rounded-full dot-3" style={{ backgroundColor: '#8b949e' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div
        className="p-3 border-t flex-shrink-0"
        style={{ borderColor: '#30363d' }}
      >
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask FinAlly AI..."
            disabled={loading}
            className="flex-1 px-3 py-2 text-xs rounded outline-none disabled:opacity-50"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              color: '#e6edf3',
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-3 py-2 rounded text-xs font-bold transition-all hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ backgroundColor: '#753991', color: '#fff' }}
          >
            {loading ? '...' : '→'}
          </button>
        </div>
        <div className="text-xs mt-1" style={{ color: '#6e7681' }}>
          Press Enter to send
        </div>
      </div>
    </div>
  );
}
