import { FormEvent, useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { authService } from '../services/authService';
import type { InternalUser } from '../types/auth';

const permissionGroups = [
  { title: 'Administração', items: [['users:read', 'Visualizar usuários'], ['users:create', 'Criar contas'], ['users:manage', 'Gerenciar contas'], ['users:manage_roles', 'Gerenciar funções']] },
  { title: 'Clientes e fornecedores', items: [['customers:read', 'Visualizar clientes'], ['customers:create', 'Criar clientes'], ['customers:update', 'Editar clientes'], ['suppliers:read', 'Visualizar fornecedores'], ['suppliers:manage', 'Gerenciar fornecedores']] },
  { title: 'Produtos e compras', items: [['products:read', 'Visualizar produtos'], ['products:create', 'Criar produtos'], ['products:update', 'Editar produtos'], ['purchases:read', 'Visualizar compras'], ['purchases:create', 'Registrar compras'], ['purchases:cancel', 'Cancelar compras']] },
  { title: 'Vendas e estoque', items: [['orders:read', 'Visualizar pedidos'], ['orders:create', 'Criar pedidos'], ['orders:update_status', 'Finalizar e cancelar pedidos'], ['inventory:read', 'Visualizar estoque'], ['inventory:adjust', 'Ajustar estoque']] },
  { title: 'Precificação e financeiro', items: [['pricing:read', 'Visualizar precificação'], ['pricing:approve', 'Aprovar preços'], ['finance:read', 'Visualizar financeiro'], ['finance:write', 'Gerenciar financeiro']] },
  { title: 'Inteligência e relatórios', items: [['intelligence:read', 'Visualizar inteligência'], ['intelligence:train', 'Treinar modelo de inteligência'], ['reports:read', 'Visualizar relatórios'], ['opportunities:manage', 'Gerenciar oportunidades'], ['partners:read', 'Visualizar parceiros'], ['partners:activate', 'Ativar parceiros'], ['partners:deactivate', 'Desativar parceiros'], ['partners:conditions', 'Gerenciar condições de parceiros'], ['partners:evaluate_predictions', 'Avaliar previsões']] },
] as const;
export function UsersPage() {
  const [users, setUsers] = useState<InternalUser[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [removingId, setRemovingId] = useState('');
  const [form, setForm] = useState({ name: '', email: '', password: '', permissions: [] as string[] });
  const current = authService.getCurrentUser();
  const canManage = Boolean(current?.isGeneralAdmin || current?.permissions.includes('manage_users'));
  const canRemoveUsers = Boolean(current?.isGeneralAdmin);
  const refresh = async () => {
    try {
      setUsers(await authService.getUsers());
    } catch (error) { setFeedback(error instanceof Error ? error.message : 'Falha ao carregar usuários.'); }
  };
  useEffect(() => { void refresh(); }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canManage) { setFeedback('Você não tem permissão para criar usuários.'); return; }
    try {
      await authService.createUser(form);
      setFeedback('Usuário criado. A senha inicial deve ser entregue com segurança.');
      setForm({ name: '', email: '', password: '', permissions: [] });
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
  const togglePermission = (permission: string) => setForm((value) => ({ ...value, permissions: value.permissions.includes(permission) ? value.permissions.filter((item) => item !== permission) : [...value.permissions, permission] }));
  return <><Header title="Usuários e permissões" breadcrumb="Administração / Usuários" /><div className="page-shell">
    <PageHeader title="Usuários e permissões" description="Controle o acesso interno por função e permissões." actions={<button className="btn btn--primary" type="button" onClick={() => setShowForm(true)} disabled={!canManage}>Criar usuário</button>} />
    {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
    <section className="panel"><div className="table-scroll"><table className="table"><thead><tr><th>Usuário</th><th>Função</th><th>Status</th><th>Ação</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><strong>{user.name}</strong><small>{user.email}</small></td><td>{user.isGeneralAdmin ? 'Administrador geral' : user.role}</td><td>{user.status === 'active' ? 'Ativo' : 'Inativo'}</td><td><div className="table-actions">{!user.isGeneralAdmin ? <button className="btn btn--secondary" type="button" onClick={() => void toggleStatus(user)}>{user.status === 'active' ? 'Desativar' : 'Ativar'}</button> : null}{canRemoveUsers && user.id !== current?.id ? <button className="btn btn--secondary table-action-danger" type="button" disabled={removingId === user.id} onClick={() => void removeUser(user)}>{removingId === user.id ? 'Removendo…' : 'Remover'}</button> : null}{user.isGeneralAdmin && user.id === current?.id ? 'Sua conta' : null}</div></td></tr>)}</tbody></table></div>{!users.length ? <p className="table-state">Nenhum usuário retornado pela API.</p> : null}</section>
    {showForm ? <div className="admin-modal-backdrop"><form className="admin-modal users-create-modal" onSubmit={(event) => void submit(event)}><div className="admin-modal__header"><div><span className="eyebrow">ADMINISTRAÇÃO</span><h2>Criar usuário interno</h2></div><button type="button" onClick={() => setShowForm(false)} aria-label="Fechar">×</button></div>
      <label>Nome<input required minLength={2} value={form.name} onChange={(event) => setForm((value) => ({ ...value, name: event.target.value }))} /></label>
      <label>E-mail<input required type="email" value={form.email} onChange={(event) => setForm((value) => ({ ...value, email: event.target.value }))} /></label>
      <label>Senha inicial (mínimo 12 caracteres)<input required type="password" minLength={12} value={form.password} onChange={(event) => setForm((value) => ({ ...value, password: event.target.value }))} /></label>
      <fieldset className="user-permission-picker"><legend>Permissões desta conta</legend><p className="admin-modal__hint">Selecione os acessos que o usuário terá no sistema.</p>{permissionGroups.map((group) => <div className="user-permission-picker__group" key={group.title}><strong>{group.title}</strong><div>{group.items.map(([key, label]) => <label key={key}><input type="checkbox" checked={form.permissions.includes(key)} onChange={() => togglePermission(key)} /><span>{label}</span></label>)}</div></div>)}</fieldset>
      <p className="admin-modal__hint">A conta será criada pela API e a senha será armazenada com hash Argon2. Não envie a senha por um canal desprotegido.</p>
      <div className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setShowForm(false)}>Cancelar</button><button type="submit" className="btn btn--primary">Criar usuário</button></div>
    </form></div> : null}
  </div></>;
}
