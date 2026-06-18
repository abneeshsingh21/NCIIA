import { useState } from 'react';
import { Shield, Lock, FileText, AlertTriangle, CheckCircle, Smartphone } from 'lucide-react';

interface FraudAction {
  id: string;
  name: string;
  description: string;
  icon: any;
  dangerLevel: 'low' | 'medium' | 'high';
}

const FRAUD_ACTIONS: FraudAction[] = [
  {
    id: 'takedown_request',
    name: 'Issue DMCA Takedown',
    description: 'Auto-generate and send legal takedown notice to registrar.',
    icon: FileText,
    dangerLevel: 'medium'
  },
  {
    id: 'asset_freeze',
    name: 'Freeze Assets / Wallet',
    description: 'Submit formal request to major exchanges/banks to freeze funds.',
    icon: Lock,
    dangerLevel: 'high'
  },
  {
    id: 'identity_flag',
    name: 'Flag Identity',
    description: 'Mark persona as confirmed fraudulent across shared intel databases.',
    icon: AlertTriangle,
    dangerLevel: 'medium'
  },
  {
    id: 'device_lock',
    name: 'Device Lock Command',
    description: 'Send remote lock signal to compromised corporate devices.',
    icon: Smartphone,
    dangerLevel: 'high'
  }
];

export default function FraudControlCenter({ caseId }: { caseId: string }) {
  const [executing, setExecuting] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  const handleExecute = async (action: FraudAction) => {
    if (!confirm(`Are you sure you want to execute: ${action.name}?`)) return;
    
    setExecuting(action.id);
    
    try {
      // Simulate API call to backend ResponseEngine
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const response = await fetch(`http://${window.location.hostname}:8000/api/response/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          action_type: action.id === 'device_lock' ? 'fraud_report' : action.id, // Mapping for demo
          target: "Target-X",
          details: { reason: "User Manual Override" }
        })
      });
      
      if (response.ok) {
        setHistory(prev => [{
            id: Date.now(),
            action: action.name,
            timestamp: new Date().toLocaleTimeString(),
            status: 'SUCCESS'
        }, ...prev]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setExecuting(null);
    }
  };

  return (
    <div className="card" style={{ border: '1px solid var(--accent-danger)', background: 'rgba(220, 38, 38, 0.05)' }}>
      <div style={{ padding: '20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--accent-danger)' }}>
          <Shield size={24} />
          Active Response & Fraud Control
        </h2>
        <div className="badge" style={{ background: 'var(--accent-danger)', color: '#fff' }}>
          AUTHORIZED PERSONNEL ONLY
        </div>
      </div>
      
      <div style={{ padding: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '15px', marginBottom: '30px' }}>
          {FRAUD_ACTIONS.map(action => (
            <button
              key={action.id}
              onClick={() => handleExecute(action)}
              disabled={!!executing}
              className={`btn ${executing === action.id ? 'btn-outline' : 'btn-danger-outline'}`}
              style={{ 
                textAlign: 'left', 
                padding: '15px',
                display: 'flex',
                alignItems: 'center',
                gap: '15px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                opacity: executing && executing !== action.id ? 0.5 : 1
              }}
            >
              <div style={{ 
                padding: '10px', 
                background: 'rgba(255,255,255,0.05)', 
                borderRadius: '8px',
                color: action.dangerLevel === 'high' ? 'var(--accent-danger)' : 'var(--text-primary)'
              }}>
                <action.icon size={20} />
              </div>
              <div>
                <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{action.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{action.description}</div>
              </div>
              {executing === action.id && <div className="spinner" style={{ marginLeft: 'auto' }} />}
            </button>
          ))}
        </div>
        
        {history.length > 0 && (
          <div style={{ background: 'var(--bg-primary)', padding: '15px', borderRadius: '8px' }}>
            <h4 style={{ marginTop: 0, marginBottom: '10px', fontSize: '14px', color: 'var(--text-secondary)' }}>ACTION LOG</h4>
            {history.map(item => (
              <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', padding: '8px 0', borderBottom: '1px solid var(--border-color)' }}>
                <span>{item.timestamp}</span>
                <span style={{ fontWeight: 'bold' }}>{item.action}</span>
                <span style={{ color: 'var(--accent-success)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <CheckCircle size={12} /> {item.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
