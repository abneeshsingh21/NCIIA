import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, Terminal, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class GlobalErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('CRITICAL SYSTEM FAILURE:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: '100vh',
          width: '100vw',
          background: '#050510',
          color: '#ef4444',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: '"JetBrains Mono", monospace'
        }}>
          <div style={{
            border: '1px solid #ef4444',
            padding: '40px',
            borderRadius: '12px',
            background: 'rgba(239, 68, 68, 0.05)',
            maxWidth: '600px',
            width: '90%',
            textAlign: 'center',
            boxShadow: '0 0 40px rgba(239, 68, 68, 0.2)'
          }}>
            <AlertTriangle size={64} style={{ marginBottom: '24px' }} />
            <h1 style={{ fontSize: '24px', marginBottom: '16px', letterSpacing: '2px' }}>SYSTEM MALFUNCTION</h1>
            
            <div style={{ 
              background: '#000', 
              padding: '20px', 
              borderRadius: '8px', 
              marginBottom: '24px', 
              textAlign: 'left',
              overflow: 'auto',
              maxHeight: '200px',
              border: '1px solid #333'
            }}>
              <p style={{ margin: 0, color: '#f87171', fontSize: '14px' }}>
                <Terminal size={14} style={{ display: 'inline', marginRight: '8px' }} />
                Error: {this.state.error?.message || 'Unknown Critical Error'}
              </p>
            </div>

            <button 
              onClick={() => window.location.reload()}
              style={{
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                padding: '12px 24px',
                borderRadius: '6px',
                fontSize: '16px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                fontWeight: 600
              }}
            >
              <RefreshCw size={18} />
              REBOOT SYSTEM
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default GlobalErrorBoundary;
