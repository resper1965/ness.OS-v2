import React, { useState, useEffect } from 'react';
import { Server, HardDrive, RefreshCw, AlertTriangle } from 'lucide-react';

export default function CloudManagement() {
  const [instances, setInstances] = useState<any[]>([]);
  const [storage, setStorage] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'compute' | 'storage'>('compute');
  
  // Restart Modal state
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [restartingInstance, setRestartingInstance] = useState<any>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchCompute = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/contabo/compute');
      if (res.ok) {
        const data = await res.json();
        setInstances(data);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const fetchStorage = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/contabo/storage');
      if (res.ok) {
        const data = await res.json();
        setStorage(data);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (activeTab === 'compute') fetchCompute();
    if (activeTab === 'storage') fetchStorage();
  }, [activeTab]);

  const handleRestart = async () => {
    if (!restartingInstance) return;
    setActionLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/api/contabo/compute/${restartingInstance.instanceId}/restart`, {
        method: 'POST'
      });
      if (res.ok) {
        alert(`Instance ${restartingInstance.displayName} is restarting...`);
        setShowRestartConfirm(false);
      }
    } catch (e) {
      console.error(e);
    }
    setActionLoading(false);
    setRestartingInstance(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Cloud Management (Contabo)</h2>
          <p className="text-[var(--color-brand-muted)]">Manage your infrastructure resources seamlessly.</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-white/5 space-x-4">
        <button 
          onClick={() => setActiveTab('compute')}
          className={`pb-3 font-medium flex items-center gap-2 ${activeTab === 'compute' ? 'border-b-2 border-[var(--color-brand-primary)] text-white' : 'text-[var(--color-brand-muted)] hover:text-white'}`}
        >
          <Server size={18}/> Compute (VPS)
        </button>
        <button 
          onClick={() => setActiveTab('storage')}
          className={`pb-3 font-medium flex items-center gap-2 ${activeTab === 'storage' ? 'border-b-2 border-[var(--color-brand-primary)] text-white' : 'text-[var(--color-brand-muted)] hover:text-white'}`}
        >
          <HardDrive size={18}/> Object Storage
        </button>
      </div>

      {/* Content */}
      <div className="bg-[var(--color-brand-surface)] border border-white/5 rounded-xl overflow-hidden">
        
        {loading ? (
          <div className="p-8 text-center text-[var(--color-brand-muted)] flex flex-col items-center gap-2">
            <RefreshCw className="animate-spin" size={24} />
            Loading {activeTab}...
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 text-[var(--color-brand-muted)] bg-black/20">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Region</th>
                <th className="p-4 font-medium">Status</th>
                <th className="p-4 font-medium">Specs / IPs</th>
                <th className="p-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {activeTab === 'compute' && instances.map(instance => (
                <tr key={instance.instanceId} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                  <td className="p-4 font-medium">{instance.displayName}</td>
                  <td className="p-4 text-[var(--color-brand-muted)]">{instance.region}</td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${instance.status === 'running' ? 'bg-[var(--color-brand-success)]/10 text-[var(--color-brand-success)]' : 'bg-[var(--color-brand-danger)]/10 text-[var(--color-brand-danger)]'}`}>
                      {instance.status}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-[var(--color-brand-muted)]">
                    {instance.vCpu} vCPU, {instance.ramMb / 1024} GB RAM<br/>
                    IP: {instance.ipConfig?.v4?.ip}
                  </td>
                  <td className="p-4 text-right">
                    <button 
                      onClick={() => { setRestartingInstance(instance); setShowRestartConfirm(true); }}
                      className="text-sm bg-[var(--color-brand-primary)]/10 text-[var(--color-brand-primary)] hover:bg-[var(--color-brand-primary)] hover:text-white px-3 py-1.5 rounded transition-colors"
                    >
                      Restart
                    </button>
                  </td>
                </tr>
              ))}

              {activeTab === 'storage' && storage.map(store => (
                <tr key={store.tenantId} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                  <td className="p-4 font-medium">{store.tenantId}</td>
                  <td className="p-4 text-[var(--color-brand-muted)]">{store.region}</td>
                  <td className="p-4">
                    <span className="px-2 py-1 rounded text-xs font-medium bg-[var(--color-brand-success)]/10 text-[var(--color-brand-success)]">
                      {store.status}
                    </span>
                  </td>
                  <td className="p-4 text-sm text-[var(--color-brand-muted)]">
                    Total: {store.totalSpaceTb} TB
                  </td>
                  <td className="p-4 text-right">
                    <span className="text-sm text-[var(--color-brand-muted)]">No actions</span>
                  </td>
                </tr>
              ))}

              {instances.length === 0 && storage.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-[var(--color-brand-muted)]">
                    No resources found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Restart Confirm Modal (Glassmorphism Overlay) */}
      {showRestartConfirm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-[var(--color-brand-surface)] border border-white/10 rounded-xl max-w-md w-full p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-[var(--color-brand-danger)] mb-4">
              <AlertTriangle size={24} />
              <h3 className="text-xl font-bold">Restart Instance</h3>
            </div>
            
            <p className="text-[var(--color-brand-muted)] mb-6">
              Are you sure you want to restart <strong>{restartingInstance?.displayName}</strong>? 
              This action will forcibly reboot the server and interrupt ongoing services.
            </p>

            <div className="flex items-center justify-end gap-3">
              <button 
                disabled={actionLoading}
                onClick={() => { setShowRestartConfirm(false); setRestartingInstance(null); }}
                className="px-4 py-2 rounded-md font-medium text-[var(--color-brand-muted)] hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button 
                disabled={actionLoading}
                onClick={handleRestart}
                className="px-4 py-2 rounded-md font-medium bg-[var(--color-brand-danger)] text-white hover:opacity-90 transition-opacity flex items-center gap-2"
              >
                {actionLoading && <RefreshCw size={14} className="animate-spin" />}
                Force Restart
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
