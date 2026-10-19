import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';

type TutorialStep = { title: string; route: string; description: string; actions: string };

const steps: TutorialStep[] = [
  { title: 'Visão geral', route: '/', description: 'Seu resumo do negócio. Aqui você acompanha pedidos em andamento, alertas de estoque, compras pendentes e atividade recente.', actions: 'Use os links de cada alerta para abrir diretamente a tela e resolver a pendência.' },
  { title: 'Pedidos', route: '/pedidos', description: 'Acompanhe os pedidos dos clientes. Cada pedido avança por Novo, Confirmado, Em separação, Pronto e Entregue.', actions: 'Use a próxima ação indicada na linha. Aceitar reserva o estoque; finalizar marca o pedido como entregue. Cancelar devolve o estoque reservado.' },
  { title: 'Clientes', route: '/clientes', description: 'Cadastre e pesquise clientes. A lista também mostra o histórico de pedidos e compras.', actions: 'Use Novo pedido para escolher produtos e quantidades. O pedido aparece na tela Pedidos para ser aceito.' },
  { title: 'Produtos', route: '/produtos', description: 'Consulte e cadastre os produtos vendidos, com preço, custo, categoria e estoque mínimo.', actions: 'Abra um produto para ver seus detalhes. Mantenha custo, preço e estoque mínimo atualizados.' },
  { title: 'Detalhe do produto', route: '/produtos', description: 'A página de cada produto reúne informações completas, histórico e dados usados nas decisões de estoque e preço.', actions: 'Abra um item na lista de Produtos para acessar seus detalhes.' },
  { title: 'Estoque', route: '/estoque', description: 'Veja as quantidades disponíveis, identifique itens baixos e consulte movimentações.', actions: 'Registre entradas, saídas ou ajustes com o motivo correspondente. Compras recebidas também atualizam o estoque.' },
  { title: 'Compras', route: '/compras/nova', description: 'Registre uma compra de fornecedor em etapas: escolha o fornecedor, inclua produtos e confira os valores.', actions: 'Informe quantidades e custos; adicione frete e outros custos quando houver. Revise o total antes de salvar.' },
  { title: 'Fornecedores', route: '/fornecedores', description: 'Mantenha contatos e informações dos fornecedores que abastecem seus produtos.', actions: 'Cadastre ou edite os dados para facilitar o preenchimento de novas compras.' },
  { title: 'Precificação', route: '/precificacao', description: 'Revise os preços de venda e as margens calculadas com base nos custos cadastrados.', actions: 'Confira as recomendações e aplique alterações apenas quando fizer sentido para o negócio.' },
  { title: 'Oportunidades', route: '/oportunidades', description: 'Veja alertas e ações sugeridas para situações que precisam de atenção operacional.', actions: 'Abra cada oportunidade para entender o motivo e seguir para a tela onde pode resolver.' },
  { title: 'Inteligência', route: '/inteligencia', description: 'Consulte análises e previsões geradas a partir dos dados disponíveis no sistema.', actions: 'Use os resultados como apoio para planejar compras e acompanhar tendências.' },
  { title: 'Relatórios', route: '/relatorios', description: 'Consulte resultados consolidados do período, como vendas, pedidos e operação.', actions: 'Escolha os filtros disponíveis para ajustar o período e analisar os dados.' },
  { title: 'Imperial Partner', route: '/imperial-partner', description: 'Acompanhe clientes parceiros e informações sobre seus ciclos de compra.', actions: 'Consulte os dados do parceiro para planejar o relacionamento e a reposição.' },
  { title: 'Planejar', route: '/planejar', description: 'Organize objetivos e tarefas relacionadas à operação.', actions: 'Crie um plano, adicione tarefas e atualize o andamento conforme o trabalho avança.' },
  { title: 'Usuários', route: '/usuarios', description: 'Gerencie quem pode acessar o sistema e quais permissões cada pessoa possui.', actions: 'Cadastre usuários e revise suas permissões com cuidado.' },
  { title: 'Configurações', route: '/configuracoes', description: 'Ajuste parâmetros gerais que influenciam o funcionamento do sistema.', actions: 'Revise as opções antes de salvar, pois elas podem afetar preços e alertas.' },
];

export function SystemTutorial() {
  const user = authService.getCurrentUser();
  const navigate = useNavigate();
  const location = useLocation();
  const storageKey = user ? `imperial-tutorial-seen:${user.id}` : '';
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!storageKey) return;
    try {
      if (!window.localStorage.getItem(storageKey)) setOpen(true);
    } catch {
      // Keep the tutorial usable when browser storage is unavailable.
    }
  }, [storageKey]);

  const markSeen = () => {
    if (!storageKey) return;
    try { window.localStorage.setItem(storageKey, 'true'); } catch { /* Storage may be disabled. */ }
  };

  const close = () => { markSeen(); setOpen(false); setStarted(false); };
  const start = () => { markSeen(); setStarted(true); setStepIndex(0); navigate(steps[0].route); };
  const currentStep = steps[stepIndex];
  const goToStep = (index: number) => {
    setStepIndex(index);
    navigate(steps[index].route);
  };

  return <>
    <button className="system-tutorial-trigger" type="button" onClick={() => { setOpen(true); setStarted(false); }}>Seguir tutorial</button>
    {open ? <div className="system-tutorial-backdrop" role="presentation">
      <section className="system-tutorial" role="dialog" aria-modal="true" aria-labelledby="system-tutorial-title" aria-describedby="system-tutorial-description">
        <div className="system-tutorial__topline"><span>GUIA DO SISTEMA</span><button type="button" className="system-tutorial__close" aria-label="Fechar tutorial" onClick={close}>×</button></div>
        {!started ? <>
          <p className="system-tutorial__eyebrow">Boas-vindas{user?.name ? `, ${user.name}` : ''}</p>
          <h2 id="system-tutorial-title">Conheça cada área do sistema</h2>
          <p id="system-tutorial-description">Este guia apresenta as telas principais em etapas curtas e mostra para que serve cada uma. Você pode cancelar agora e abrir o tutorial depois pelo botão “Seguir tutorial”.</p>
          <div className="system-tutorial__actions"><button type="button" className="btn btn--secondary" onClick={close}>Cancelar</button><button type="button" className="btn btn--primary" onClick={start}>Seguir tutorial</button></div>
        </> : <>
          <div className="system-tutorial__progress"><span>Etapa {stepIndex + 1} de {steps.length}</span><div><i style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }} /></div></div>
          <p className="system-tutorial__eyebrow">{currentStep.title}</p>
          <h2 id="system-tutorial-title">{currentStep.title}</h2>
          <div id="system-tutorial-description" aria-live="polite"><p>{currentStep.description}</p><p>{currentStep.actions}</p></div>
          {location.pathname !== currentStep.route ? <button type="button" className="system-tutorial__visit" onClick={() => navigate(currentStep.route)}>Abrir tela: {currentStep.title}</button> : null}
          <div className="system-tutorial__actions"><button type="button" className="btn btn--secondary" onClick={close}>Cancelar</button><div>{stepIndex > 0 ? <button type="button" className="btn btn--secondary" onClick={() => goToStep(stepIndex - 1)}>Voltar</button> : null}<button type="button" className="btn btn--primary" onClick={() => stepIndex === steps.length - 1 ? close() : goToStep(stepIndex + 1)}>{stepIndex === steps.length - 1 ? 'Concluir' : 'Próxima etapa'}</button></div></div>
        </>}
      </section>
    </div> : null}
  </>;
}
