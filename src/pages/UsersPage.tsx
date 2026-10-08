import { FormEvent, useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { authService } from '../services/authService';
import type { InternalUser } from '../types/auth';

type Role = { id: string; name: string };
export function UsersPage() {
  const [users, setUsers] = useState<InternalUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [removingId, setRemovingId] = useState('');
  const [form, setForm] = useState({ name: '', email: '', password: '', role_id: '' });
  const current = authService.getCurrentUser();
  const canManage = Boolean(current?.isGeneralAdmin || current?.permissions.includes('manage_users'));
  const canRemoveUsers = Boolean(current?.isGeneralAdmin);
  const refresh = async () => {
    try {
      const [nextUsers, nextRoles] = await Promise.all([authService.getUsers(), authService.getRoles()]);
      setUsers(nextUsers); setRoles(nextRoles);
      if (!form.role_id && nextRoles[0]) setForm((value) => ({ ...value, role_id: nextRoles[0].id }));
    } catch (error) { setFeedback(error instanceof Error ? error.message : 'Falha ao carregar usuários.'); }
  };
  useEffect(() => { void refresh(); }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canManage) { setFeedback('Você não tem permissão para criar usuários.'); return; }
    try {
      await authService.createUser(form);
      setFeedback('Usuário criado. A senha inicial deve ser entregue com segurança.');
      setForm({ name: '', email: '', password: '', role_id: roles[0]?.id ?? '' });
      setShowForm(false);
      await refresh();
    } catch (error) { setFeedback(error instanceof Error ? error.message : 'Falha ao criar usuário.'); }
  };
  const toggleStatus = async (user: InternalUser) => {
    try { await authService.updateUserStatus(user.id, user.status !== 'active'); await refresh(); }
    catch (error) { setFeedback(error instanceof Error ? error.message : 'Falha ao atualizar usuário.'); }
  };
  const removeUser = async (user: InternalUser) => {
    if (!window.confirm(`Remover permanentemente ${user.name} (${user.email})?\n\nO acesso e a conta serão apagados. Os registros históricos serão preservados, mas referências a este usuário poderão ser desvinculadas.`)) return;
    setRemovingId(user.id);
    setFeedback('');
    try {
      await authService.deleteUser(user.id);
      setUsers((currentUsers) => currentUsers.filter((currentUser) => currentUser.id !== user.id));
      setFeedback(`Usuário ${user.name} removido.`);
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Falha ao remover usuário.');
    } finally {
      setRemovingId('');
    }
  };
  return <><Header title="Usuários e permissões" breadcrumb="Administração / Usuários" /><div className="page-shell">
    <PageHeader title="Usuários e permissões" description="Controle o acesso interno por função e permissões." actions={<button className="btn btn--primary" type="button" onClick={() => setShowForm(true)} disabled={!canManage}>Criar usuário</button>} />
    {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
    <section className="panel"><div className="table-scroll"><table className="table"><thead><tr><th>Usuário</th><th>Função</th><th>Status</th><th>Ação</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><strong>{user.name}</strong><small>{user.email}</small></td><td>{user.isGeneralAdmin ? 'Administrador geral' : user.role}</td><td>{user.status === 'active' ? 'Ativo' : 'Inativo'}</td><td><div className="table-actions">{!user.isGeneralAdmin ? <button className="btn btn--secondary" type="button" onClick={() => void toggleStatus(user)}>{user.status === 'active' ? 'Desativar' : 'Ativar'}</button> : null}{canRemoveUsers && user.id !== current?.id ? <button className="btn btn--secondary table-action-danger" type="button" disabled={removingId === user.id} onClick={() => void removeUser(user)}>{removingId === user.id ? 'Removendo…' : 'Remover'}</button> : null}{user.isGeneralAdmin && user.id === current?.id ? 'Sua conta' : null}</div></td></tr>)}</tbody></table></div>{!users.length ? <p className="table-state">Nenhum usuário retornado pela API.</p> : null}</section>
    {showForm ? <div className="admin-modal-backdrop"><form className="admin-modal" onSubmit={(event) => void submit(event)}><div className="admin-modal__header"><div><span className="eyebrow">ADMINISTRAÇÃO</span><h2>Criar usuário interno</h2></div><button type="button" onClick={() => setShowForm(false)} aria-label="Fechar">×</button></div>
      <label>Nome<input required minLength={2} value={form.name} onChange={(event) => setForm((value) => ({ ...value, name: event.target.value }))} /></label>
      <label>E-mail<input required type="email" value={form.email} onChange={(event) => setForm((value) => ({ ...value, email: event.target.value }))} /></label>
      <label>Senha inicial (mínimo 12 caracteres)<input required type="password" minLength={12} value={form.password} onChange={(event) => setForm((value) => ({ ...value, password: event.target.value }))} /></label>
      <label>Função autorizada<select required value={form.role_id} onChange={(event) => setForm((value) => ({ ...value, role_id: event.target.value }))}>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
      {!roles.length ? <p className="admin-modal__hint">Crie uma função com permissões antes de autorizar usuários.</p> : null}
      <p className="admin-modal__hint">A conta será criada pela API e a senha será armazenada com hash Argon2. Não envie a senha por um canal desprotegido.</p>
      <div className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setShowForm(false)}>Cancelar</button><button type="submit" className="btn btn--primary" disabled={!roles.length}>Criar usuário</button></div>
    </form></div> : null}
  </div></>;
}
