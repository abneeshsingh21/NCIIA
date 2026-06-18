import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import { WebSocketProvider } from './context/WebSocketContext';
import GlobalErrorBoundary from './components/GlobalErrorBoundary';
import CyberBackground from './components/CyberBackground';
import Sidebar from './components/Sidebar';
import LiveTicker from './components/LiveTicker';

// Lazy-load all pages to reduce initial bundle size
const Dashboard          = lazy(() => import('./pages/Dashboard'));
const Personas           = lazy(() => import('./pages/Personas'));
const Signals            = lazy(() => import('./pages/Signals'));
const Cases              = lazy(() => import('./pages/Cases'));
const OsintSearch        = lazy(() => import('./pages/OsintSearch'));
const Alerts             = lazy(() => import('./pages/Alerts'));
const ThreatIntelligence = lazy(() => import('./pages/ThreatIntelligence'));
const AiAnalyst          = lazy(() => import('./pages/AiAnalyst'));
const AttackMap          = lazy(() => import('./pages/AttackMap'));
const EnrichmentExplorer = lazy(() => import('./pages/EnrichmentExplorer'));
const HunterAgents       = lazy(() => import('./pages/HunterAgents'));
const ScamInvestigator   = lazy(() => import('./pages/ScamInvestigator'));

function PageLoader() {
  return (
    <div className="page-loader">
      <div className="page-loader__spinner" />
    </div>
  );
}

export default function App() {
  return (
    <GlobalErrorBoundary>
      <WebSocketProvider>
        <Router>
          <div className="app-root">
            <CyberBackground />
            <div className="app-shell">
              <LiveTicker />
              <div className="app-body">
                <Sidebar />
                <main className="main-content">
                  <Suspense fallback={<PageLoader />}>
                    <Routes>
                      <Route path="/"           element={<Dashboard />} />
                      <Route path="/osint"      element={<OsintSearch />} />
                      <Route path="/personas"   element={<Personas />} />
                      <Route path="/signals"    element={<Signals />} />
                      <Route path="/cases"      element={<Cases />} />
                      <Route path="/alerts"     element={<Alerts />} />
                      <Route path="/threats"    element={<ThreatIntelligence />} />
                      <Route path="/ai"         element={<AiAnalyst />} />
                      <Route path="/attack"     element={<AttackMap />} />
                      <Route path="/enrichment" element={<EnrichmentExplorer />} />
                      <Route path="/hunters"    element={<HunterAgents />} />
                      <Route path="/investigate" element={<ScamInvestigator />} />
                    </Routes>
                  </Suspense>
                </main>
              </div>
            </div>
          </div>
        </Router>
      </WebSocketProvider>
    </GlobalErrorBoundary>
  );
}
