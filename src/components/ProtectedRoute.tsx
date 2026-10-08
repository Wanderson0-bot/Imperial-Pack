import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { authService } from '../services/authService';

export function ProtectedRoute() {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  useEffect(() => {
    let active = true;
    void authService.getCurrentUserAsync().then((user) => { if (active) { setAuthenticated(Boolean(user)); setReady(true); } });
    return () => { active = false; };
  }, []);
  if (!ready) return <main className="access-page"><p>Verificando sessão...</p></main>;
  return authenticated ? <Outlet /> : <Navigate to="/acesso" replace />;
}
