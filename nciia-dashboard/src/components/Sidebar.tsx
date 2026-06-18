import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Users, Radio, Briefcase, AlertTriangle,
  Search, Shield, Wifi, WifiOff, Loader2, Bot, Globe, Target, Crosshair, Fingerprint,
} from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  divider?: boolean;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  // Core
  { to: '/',          label: 'Dashboard',     icon: LayoutDashboard },
  { to: '/personas',  label: 'Personas',      icon: Users },
  { to: '/signals',   label: 'Signals',       icon: Radio },
  { to: '/cases',     label: 'Cases',         icon: Briefcase },
  { to: '/alerts',    label: 'Alerts',        icon: AlertTriangle },
  // Intelligence
  { to: '/threats',    label: 'Threat Intel',   icon: Shield,    divider: true },
  { to: '/osint',      label: 'OSINT Search',   icon: Search },
  { to: '/enrichment', label: 'IOC Enrichment', icon: Globe },
  // Advanced AI
  { to: '/ai',      label: 'AI Analyst',    icon: Bot,       divider: true, badge: 'AI' },
  { to: '/attack',  label: 'ATT\u0026CK Map',     icon: Target },
  { to: '/hunters',     label: 'Hunter Agents',    icon: Crosshair,    badge: 'NEW' },
  { to: '/investigate', label: 'Scam Investigator', icon: Fingerprint,  badge: 'HOT' },
];

function WsStatusBadge() {
  const { status } = useWebSocket();
  const map = {
    connected:    { label: 'Live',          Icon: Wifi,    cls: 'ws-badge ws-badge--connected' },
    connecting:   { label: 'Connecting…',   Icon: Loader2, cls: 'ws-badge ws-badge--connecting' },
    disconnected: { label: 'Disconnected',  Icon: WifiOff, cls: 'ws-badge ws-badge--disconnected' },
    error:        { label: 'Error',         Icon: WifiOff, cls: 'ws-badge ws-badge--error' },
  } as const;
  const { label, Icon, cls } = map[status];
  return (
    <div className={cls}>
      <Icon size={12} className={status === 'connecting' ? 'spin' : undefined} />
      <span>{label}</span>
    </div>
  );
}

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>N-CIIA</h1>
        <p className="sidebar-logo__sub">Cyber Intelligence Platform</p>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, label, icon: Icon, divider, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}${divider ? ' nav-item--divider' : ''}`
            }
          >
            <Icon size={16} />
            <span style={{ flex: 1 }}>{label}</span>
            {badge && (
              <span style={{
                fontSize: 9, fontWeight: 700, padding: '1px 5px',
                borderRadius: 4, background: 'rgba(0,255,136,.15)',
                color: 'var(--accent-primary)', letterSpacing: '.5px',
              }}>{badge}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <WsStatusBadge />
      </div>
    </aside>
  );
}
