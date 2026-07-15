import React, { useState, useEffect } from 'react';
import { Bell, BellOff, BellRing, Loader2 } from 'lucide-react';

interface PushNotificationToggleProps {
  token: string;
}

const API_BASE = import.meta.env.VITE_API_URL ?? '';

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export default function PushNotificationToggle({ token }: PushNotificationToggleProps) {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [support, setSupport] = useState(true);

  // Verifica o status da inscrição ao montar o componente
  useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setSupport(false);
      setLoading(false);
      return;
    }

    navigator.serviceWorker.ready.then((registration) => {
      registration.pushManager.getSubscription().then((subscription) => {
        setIsSubscribed(!!subscription);
        setLoading(false);
      });
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  const handleTogglePush = async () => {
    if (loading) return;
    setLoading(true);

    try {
      if (isSubscribed) {
        // Cancelar inscrição
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await fetch(`${API_BASE}/api/v1/push/unsubscribe`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({ endpoint: subscription.endpoint })
          });
          await subscription.unsubscribe();
        }
        setIsSubscribed(false);
      } else {
        // Ativar inscrição
        const registration = await navigator.serviceWorker.ready;
        
        // Buscar chave VAPID pública do backend
        const configRes = await fetch(`${API_BASE}/api/v1/push/config`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!configRes.ok) throw new Error();
        const { public_key } = await configRes.json();

        // Solicitar permissão de notificações
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          alert('Permissão de notificação negada. Ative as notificações nas configurações do navegador.');
          setLoading(false);
          return;
        }

        // Inscrever no PushManager
        const subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(public_key)
        });

        // Registrar no backend
        const subRes = await fetch(`${API_BASE}/api/v1/push/subscribe`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(subscription)
        });

        if (!subRes.ok) throw new Error();
        setIsSubscribed(true);
      }
    } catch (err) {
      console.error('Erro ao gerenciar notificações push:', err);
      alert('Falha ao configurar notificações. Verifique a conexão.');
    } finally {
      setLoading(false);
    }
  };

  if (!support) return null;

  return (
    <button
      onClick={handleTogglePush}
      disabled={loading}
      className={`
        w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left text-xs font-medium
        transition-all duration-200 select-none border border-white/[0.04]
        ${isSubscribed 
          ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/15 hover:text-emerald-300' 
          : 'bg-white/[0.03] text-white/50 hover:bg-white/[0.06] hover:text-white/80'}
      `}
    >
      {loading ? (
        <Loader2 size={13} className="animate-spin text-[#00ADE8] shrink-0" />
      ) : isSubscribed ? (
        <BellRing size={13} className="shrink-0 text-emerald-400 animate-pulse" />
      ) : (
        <Bell size={13} className="shrink-0" />
      )}
      <span className="flex-1">
        {loading 
          ? 'Processando...' 
          : isSubscribed 
            ? 'Alertas Push Ativados' 
            : 'Ativar Alertas Push'}
      </span>
    </button>
  );
}
