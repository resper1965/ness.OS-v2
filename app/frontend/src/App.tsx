import { Activity, ShieldAlert, Users, Server, Settings, Cloud } from 'lucide-react';
import React, { useState } from 'react';
import CloudManagement from './components/CloudManagement';

function BrandLogo() {
  return (
    <div className="flex items-center gap-1 font-logo text-2xl font-medium tracking-tight">
      ness<span style={{ color: 'var(--color-brand-primary)' }}>.</span>
    </div>
  );
}

function SidebarItem({ icon: Icon, label, active = false, onClick }: { icon: any, label: string, active?: boolean, onClick?: () => void }) {
  return (
    <div onClick={onClick} className={`flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors duration-200 ${
      active 
        ? 'bg-[var(--color-brand-primary)] text-white' 
        : 'text-[var(--color-brand-muted)] hover:bg-[var(--color-brand-surface)] hover:text-white'
    }`}>
      <Icon size={18} />
      <span className="font-medium text-sm">{label}</span>
    </div>
  );
}

function MetricCard({ title, value, status = 'neutral' }: { title: string, value: string | number, status?: 'success'|'danger'|'neutral' }) {
  const statusColor = 
    status === 'success' ? 'text-[var(--color-brand-success)]' :
    status === 'danger' ? 'text-[var(--color-brand-danger)]' : 
    'text-white';

  return (
    <div className="bg-[var(--color-brand-surface)] border border-white/5 rounded-xl p-5 flex flex-col gap-2">
      <div className="text-[var(--color-brand-muted)] text-sm font-medium">{title}</div>
      <div className={`text-3xl font-bold ${statusColor}`}>{value}</div>
    </div>
  );
}

function App() {
  const [currentView, setCurrentView] = useState<'dashboard' | 'cloud'>('dashboard');

  return (
    <div className="min-h-screen bg-[var(--color-brand-base)] text-[var(--color-brand-text)] flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 bg-[var(--color-brand-base)] flex flex-col p-4 gap-8">
        <div className="px-2">
          <BrandLogo />
        </div>
        
        <nav className="flex flex-col gap-1">
          <SidebarItem icon={Activity} label="Dashboard" active={currentView === 'dashboard'} onClick={() => setCurrentView('dashboard')} />
          <SidebarItem icon={Cloud} label="Cloud (Contabo)" active={currentView === 'cloud'} onClick={() => setCurrentView('cloud')} />
          <SidebarItem icon={Server} label="Infrastructure" />
          <SidebarItem icon={ShieldAlert} label="Incidents" />
          <SidebarItem icon={Users} label="Tenants" />
          <SidebarItem icon={Settings} label="Settings" />
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        
        {/* Subtle top glow effect for depth */}
        <div className="absolute top-0 inset-x-0 h-32 bg-[var(--color-brand-primary)] opacity-[0.03] blur-3xl pointer-events-none" />

        <header className="h-16 border-b border-white/5 flex items-center px-8 z-10">
          <h1 className="text-xl font-bold">AIOps Dashboard</h1>
        </header>

        <div className="flex-1 overflow-auto p-8 z-10">
          <div className="max-w-6xl mx-auto space-y-6">
            
            {currentView === 'dashboard' ? (
              <>
                {/* Header Section */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">System Status</h2>
                    <p className="text-[var(--color-brand-muted)]">Real-time infrastructure monitoring</p>
                  </div>
                  <button className="bg-[var(--color-brand-primary)] hover:opacity-90 transition-opacity text-white px-4 py-2 rounded-md font-medium text-sm">
                    Generate Report
                  </button>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <MetricCard title="Active Hosts" value={374} />
                  <MetricCard title="Monitored Items" value="59k" />
                  <MetricCard title="Critical Alerts" value={12} status="danger" />
                  <MetricCard title="System Health" value="98.2%" status="success" />
                </div>

                {/* Content Area */}
                <div className="bg-[var(--color-brand-surface)] border border-white/5 rounded-xl p-6 min-h-[400px]">
                  <h3 className="text-lg font-semibold mb-4">Recent Incidents</h3>
                  
                  <div className="space-y-2">
                    {/* Example Incident Row */}
                    <div className="flex items-center justify-between p-3 rounded-lg border border-white/5 hover:bg-white/[0.02] transition-colors cursor-pointer">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-[var(--color-brand-danger)]" />
                        <span className="font-medium">Zabbix DB Replication Lag High</span>
                      </div>
                      <span className="text-sm text-[var(--color-brand-muted)]">2 mins ago</span>
                    </div>
                    
                    {/* Example Incident Row */}
                    <div className="flex items-center justify-between p-3 rounded-lg border border-white/5 hover:bg-white/[0.02] transition-colors cursor-pointer">
                      <div className="flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-[var(--color-brand-danger)]" />
                        <span className="font-medium">Contabo VPS CPU &gt; 95%</span>
                      </div>
                      <span className="text-sm text-[var(--color-brand-muted)]">15 mins ago</span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <CloudManagement />
            )}

          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
