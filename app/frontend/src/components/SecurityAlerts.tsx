import { useEffect, useState } from 'react';
import { request } from '../http';
import { Alert } from './ui/kit';

interface AuditItem { check: string; status: 'secure' | 'warning' | 'danger' | 'unknown'; message: string }

/** Riscos da auditoria do ambiente: só aparece quando há aviso ou perigo. */
export default function SecurityAlerts() {
  const [issues, setIssues] = useState<AuditItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    request<AuditItem[]>('/api/tenants/security-audit')
      .then(a => setIssues(a.filter(i => i.status === 'warning' || i.status === 'danger')), () => setFailed(true));
  }, []);
  if (failed) return <Alert tone="info">Auditoria do ambiente indisponível: sem dado.</Alert>;
  if (!issues?.length) return null;
  return (
    <Alert>
      <div className="nx-stack" style={{ gap: 4 }}>
        <strong>Riscos no ambiente ({issues.length})</strong>
        {issues.map(i => <span key={i.check}>{i.check}: <span className="nx-muted">{i.message}</span></span>)}
      </div>
    </Alert>
  );
}
