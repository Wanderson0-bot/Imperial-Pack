import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import { apiConfiguration } from '../config/api';
import { apiRequest } from '../services/apiClient';

export function AccessPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [registrationAvailable, setRegistrationAvailable] = useState(false);
  const [googleOAuthConfigured, setGoogleOAuthConfigured] = useState(false);
  useEffect(() => {
    if (!apiConfiguration.isConfigured) return;
    let active = true;
    void apiRequest<{ initial_registration_available: boolean; google_oauth_configured: boolean }>('/auth/setup-status')
      .then((status) => {
        if (!active) return;
        setRegistrationAvailable(status.initial_registration_available);
        setGoogleOAuthConfigured(status.google_oauth_configured);
      })
      .catch(() => {
        if (!active) return;
        setRegistrationAvailable(false);
        setGoogleOAuthConfigured(false);
      });
    return () => { active = false; };
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      if (registrationAvailable) {
        await authService.registerInitialAdmin(name, email, password);
        await authService.signIn(email, password);
      } else {
        await authService.signIn(email, password);
      }
      navigate('/', { replace: true });
    }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Não foi possível entrar.'); }
  };
  const googleLogin = () => {
    if (!apiConfiguration.isConfigured) { setError('API de autenticação não configurada. Google OAuth indisponível.'); return; }
    window.location.assign(`${apiConfiguration.baseUrl}/auth/google`);
  };
  return <main className="access-page"><section className="access-panel"><span className="eyebrow">OPERAÇÃO IMPERIAL PACK</span><h1>{registrationAvailable ? 'Criar administrador inicial' : 'Entrar no sistema'}</h1><p className="access-subtitle">Acesso exclusivo para sócios e usuários autorizados.</p><form onSubmit={(event) => void submit(event)}>{registrationAvailable ? <label>Nome<input type="text" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} maxLength={180} /></label> : null}<label>E-mail<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="seu@imperialpack.com.br" /></label><label>Senha<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={registrationAvailable ? 12 : undefined} /></label>{error ? <p className="access-error" role="alert">{error}</p> : null}<button className="btn btn--primary" type="submit">{registrationAvailable ? 'Criar administrador' : 'Entrar'}</button></form>{googleOAuthConfigured ? <button className="google-placeholder" type="button" onClick={googleLogin}>Continuar com Google</button> : null}{!apiConfiguration.isConfigured ? <small>API de autenticação não configurada.</small> : registrationAvailable ? <small>O cadastro inicial fica restrito ao e-mail autorizado pelo administrador do sistema.</small> : <small>Use uma conta criada por um administrador.</small>}</section></main>;
}
