import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';

export function SettingsPage() {
  return (
    <>
      <Header title="Configurações" breadcrumb="Configurações / Sistema" />
      <div className="page-shell">
        <PageHeader
          title="Configurações"
          description="Parâmetros internos da operação, precificação e gestão de usuários."
          actions={<span className="page-header__meta">Parâmetros somente leitura</span>}
        />

        <section className="settings-grid">
          <div className="panel">
            <div className="panel__header"><h3>Precificação</h3></div>
            <div className="field"><label>Margem mínima</label><input value="20%" readOnly /></div>
            <div className="field"><label>Margem padrão</label><input value="30%" readOnly /></div>
            <div className="field"><label>Markup máximo</label><input value="100%" readOnly /></div>
            <div className="field"><label>Arredondamento</label><input value="R$ 0,50" readOnly /></div>
          </div>

          <div className="panel">
            <div className="panel__header"><h3>Estoque</h3></div>
            <div className="field"><label>Estoque mínimo</label><input value="15" readOnly /></div>
            <div className="field"><label>Alertas</label><input value="Ativados" readOnly /></div>
          </div>

          <div className="panel">
            <div className="panel__header"><h3>Usuários</h3></div>
            <div className="field"><label>Nome</label><input value="Nicolas Imperial" readOnly /></div>
            <div className="field"><label>Cargo</label><input value="Sócio Operacional" readOnly /></div>
            <div className="field"><label>Permissões</label><input value="Compras, Precificação, Relatórios" readOnly /></div>
          </div>
        </section>
      </div>
    </>
  );
}
