import { useState, useCallback } from 'react';
import { Bitcoin, Search, AlertTriangle, Loader, ExternalLink, ArrowRight, TrendingUp } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface Transaction { hash: string; from: string; to: string; value_usd: number; value_crypto: string; timestamp: string; chain: string; label: string; }
interface WalletResult {
  address: string; chain: string; balance_usd: number; balance_crypto: string;
  total_received: number; total_sent: number; tx_count: number;
  first_seen: string; last_seen: string; label: string;
  is_exchange: boolean; mixer_detected: boolean; risk_score: number;
  risk_flags: string[]; transactions: Transaction[]; connected_wallets: string[]; errors: string[];
}

const RISK_COLOR = (s: number) => s >= 75 ? '#ef4444' : s >= 50 ? '#f97316' : s >= 25 ? '#eab308' : '#22c55e';
const CHAIN_EXPLORER: Record<string, string> = {
  Bitcoin: 'https://www.blockchain.com/explorer/addresses/btc/',
  Ethereum: 'https://etherscan.io/address/',
  'BNB Chain': 'https://bscscan.com/address/',
  TRON: 'https://tronscan.org/#/address/',
};

export default function CryptoTracer() {
  const [address, setAddress] = useState('');
  const [result, setResult] = useState<WalletResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trace = useCallback(async () => {
    if (!address.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await fetch(`${API_BASE}/api/osint/crypto`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: address.trim() }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) { setError(e instanceof Error ? e.message : 'Trace failed'); }
    finally { setLoading(false); }
  }, [address]);

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Bitcoin size={22} className="icon--warning" /> Crypto Wallet Tracer</h2>
          <p className="page-header__sub">Trace BTC · ETH · BNB · TRON wallets · Detect exchanges (KYC-able) · Mixer detection</p>
        </div>
      </header>

      <div className="card">
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="filter-bar__search" style={{ flex: 1 }}>
            <Bitcoin size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Paste wallet address (BTC, ETH, TRON, BNB auto-detected)…"
              value={address} onChange={e => setAddress(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && trace()} />
          </div>
          <button className="btn btn--primary" onClick={trace} disabled={loading || !address.trim()}>
            {loading ? <><Loader size={14} className="spin" /> Tracing…</> : <><Search size={14} /> Trace Wallet</>}
          </button>
        </div>
      </div>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} /> {error}</div>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Wallet overview */}
          <div className="card" style={{ borderColor: RISK_COLOR(result.risk_score), borderWidth: 2 }}>
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 4 }}>{result.chain} Wallet</div>
                <code style={{ fontSize: 12, wordBreak: 'break-all', color: 'var(--accent-primary)' }}>{result.address}</code>
                {result.label && <div className="tag" style={{ marginTop: 8, color: '#22c55e' }}>🏦 {result.label}</div>}
              </div>
              <div style={{ display: 'flex', gap: 24, marginLeft: 'auto' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#22c55e' }}>${result.balance_usd.toLocaleString()}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Current Balance</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{result.balance_crypto}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#ef4444' }}>${result.total_received.toLocaleString()}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Total Received</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: RISK_COLOR(result.risk_score) }}>{result.risk_score}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Risk Score</div>
                </div>
              </div>
              {CHAIN_EXPLORER[result.chain] && (
                <a href={`${CHAIN_EXPLORER[result.chain]}${result.address}`} target="_blank" rel="noopener noreferrer" className="btn btn--ghost btn--sm">
                  <ExternalLink size={12} /> Block Explorer
                </a>
              )}
            </div>

            {/* Badges */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
              <span className="badge badge--neutral">{result.tx_count} transactions</span>
              {result.is_exchange && <span className="badge badge--success">🏦 Exchange wallet — KYC traceable via police</span>}
              {result.mixer_detected && <span className="badge badge--critical">⚠ Mixer/Tumbler detected — money laundering</span>}
              {result.connected_wallets.length > 0 && <span className="badge badge--neutral">{result.connected_wallets.length} connected wallets</span>}
            </div>

            {/* Risk flags */}
            {result.risk_flags.length > 0 && (
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {result.risk_flags.map((flag, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                    <AlertTriangle size={13} style={{ color: RISK_COLOR(result.risk_score), flexShrink: 0 }} />
                    {flag}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Transaction history */}
          {result.transactions.length > 0 && (
            <div className="card">
              <div className="card__header"><h3 className="card__title"><TrendingUp size={14} className="icon--primary" /> Transaction History ({result.transactions.length})</h3></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                {result.transactions.map((tx, i) => (
                  <div key={i} style={{ padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{tx.hash}…</code>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, color: '#22c55e' }}>${tx.value_usd.toLocaleString()}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{tx.value_crypto}</span>
                        {tx.label && <span className="tag" style={{ color: '#22c55e', fontSize: 11 }}>🏦 {tx.label}</span>}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                      <code style={{ fontSize: 10 }}>{tx.from.slice(0, 12)}…</code>
                      <ArrowRight size={11} />
                      <code style={{ fontSize: 10 }}>{tx.to.slice(0, 12)}…</code>
                      <span style={{ marginLeft: 'auto' }}>{tx.chain}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
