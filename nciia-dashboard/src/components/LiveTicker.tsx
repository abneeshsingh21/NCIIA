
import { useState, useEffect } from 'react';
import { Radio } from 'lucide-react';
import { CyberNewsItem, fetchCyberNews } from '../lib/api';

export default function LiveTicker() {
  const [news, setNews] = useState<CyberNewsItem[]>([]);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        setNews(await fetchCyberNews());
      } catch (e) {
        console.error("Failed to fetch news ticker", e);
      }
    };

    void fetchNews();
    
    const interval = setInterval(fetchNews, 300000);
    return () => clearInterval(interval);
  }, []);

  if (news.length === 0) return null;

  return (
    <div style={{ 
      background: '#0d1117', 
      borderBottom: '1px solid #30363d', 
      height: '30px', 
      display: 'flex', 
      alignItems: 'center',
      overflow: 'hidden',
      position: 'relative',
      zIndex: 100
    }}>
      <div style={{ 
        background: '#ef4444', 
        height: '100%', 
        padding: '0 10px', 
        display: 'flex', 
        alignItems: 'center', 
        fontSize: '11px', 
        fontWeight: 'bold',
        color: 'white',
        zIndex: 2
      }}>
        <Radio size={12} style={{ marginRight: '5px' }} />
        LIVE INTEL
      </div>
      
      <div className="ticker-wrap" style={{ flex: 1, overflow: 'hidden' }}>
        <div className="ticker-move" style={{ 
          display: 'inline-block', 
          whiteSpace: 'nowrap',
          paddingLeft: '100%',
          animation: 'ticker 60s linear infinite'
        }}>
          {news.map((item, i) => (
            <span key={i} style={{ display: 'inline-block', marginRight: '50px', fontSize: '12px', color: '#c9d1d9' }}>
              <span style={{ color: '#58a6ff', fontWeight: 'bold' }}>[{item.source}]</span> {item.title}
            </span>
          ))}
        </div>
      </div>
      
      <style>{`
        @keyframes ticker {
          0% { transform: translate3d(0, 0, 0); }
          100% { transform: translate3d(-100%, 0, 0); }
        }
      `}</style>
    </div>
  );
}
