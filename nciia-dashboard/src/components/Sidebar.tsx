import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Radio,
  Briefcase,
  AlertTriangle,
  Search,
  Shield,
  Wifi,
  WifiOff,
  Loader2,
} from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
  divider?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',         label: 'Dashboard',    icon: LayoutDashboard },
  { to: '/personas', label: 'Personas',     icon: Users },
  { to: '/signals',  label: 'Signals',      icon: Radio },
  { to: '/cases',    label: 'Cases',        icon: Briefcase },
  { to: '/threats',  label: 'Threat Intel', icon: Shield, divider: true },
  { to: '/osint',    label: 'OSINT Search', icon: Search },
  { to: '/alerts',   label: 'Alerts',       icon: AlertTriangle },
];

function WsStatusBadge() {
  const { status } = useWebSocket();

  const map = {
    connected:    { label: 'Live Connected',  Icon: Wifi,    cls: 'ws-badge ws-badge--connected' },
    connecting:   { label: 'Connecting…',     Icon: Loader2, cls: 'ws-badge ws-badge--connecting' },
    disconnected: { label: 'Disconnected',    Icon: WifiOff, cls: 'ws-badge ws-badge--disconnected' },
    error:        { label: 'Connection Error',Icon: WifiOff, cls: 'ws-badge ws-badge--error' },
  } as const;

  const { label, Icon, cls } = map[status];

  return (
    <div className={cls}>
      <Icon size={12} className={status === 'connecting' ? 'spin' : undefined} />
      <span>{label}</span>
    </div>
  );
}

/** No props needed — WS status comes from context. */
export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>N-CIIA</h1>
        <p className="sidebar-logo__sub">Cyber Intelligence Assistant</p>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, label, icon: Icon, divider }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `nav-item${isActive ? ' active' : ''}${divider ? ' nav-item--divider' : ''}`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <WsStatusBadge />
      </div>
    </aside>
  );
}
