# Relatório de auditoria técnica — Imperial Pack System

**Data da verificação:** 05/10/2026  
**Escopo:** frontend React/Vite, API FastAPI, autenticação e permissões, modelos SQLAlchemy, cadeia Alembic, banco PostgreSQL alcançado pela configuração local, testes automatizados e smoke tests locais.

## 1. Parecer executivo

O sistema foi corrigido e validado em várias camadas. A arquitetura verificada corresponde a uma única empresa: não usa organizações, memberships ou isolamento RLS por tenant, e preserva `customers.establishment`.

**Resultado:** build e testes executados estão aprovados; o schema do PostgreSQL configurado foi migrado para a revisão atual e está alinhado aos modelos ORM. A evidência disponível, porém, **não certifica todas as jornadas de negócio ponta a ponta em produção**: não foram fornecidas credenciais de uma conta real e a validação visual manual cobriu apenas a tela de acesso. Portanto, é correto dizer que as verificações automatizadas e os smoke tests passaram, não que cada operação real foi exercitada no navegador.

Principais resultados:

- Banco validado na revisão Alembic `0007_single_company_indexes`, igual ao head atual.
- 33 tabelas; nenhuma divergência reportada entre banco e modelos para tabelas, colunas, tipos, nulabilidade, PKs, FKs, índices, unicidade e checks.
- Migrações aplicadas após criação de backup lógico, sem exclusão de dados de negócio.
- Suite backend completa com integração PostgreSQL: **65 aprovados** na execução anterior à última alteração restrita ao estado de configuração OAuth; após essa alteração, **12 testes direcionados aprovados**.
- Frontend: **4 testes aprovados**; build TypeScript/Vite executado após a alteração mais recente (ver seção 5).
- API local conectou ao banco; endpoints protegidos responderam `401` sem sessão, como esperado.
- OAuth Google não está configurado neste ambiente; a API informa isso e a interface não oferece o botão indisponível.

## 2. Arquitetura e funcionalidades mapeadas

| Camada | Componentes e funções | Evidência/limite |
|---|---|---|
| Interface | React 18, Vite e React Router; acesso, visão geral, compras, preços, produtos, estoque, pedidos, clientes, fornecedores, Imperial Partner, alertas, inteligência, relatórios, configurações e usuários | Build e testes unitários aprovados. Inspeção manual no navegador limitada a `/acesso`. |
| API | FastAPI com autenticação, usuários, clientes, produtos, fornecedores, compras, pedidos, estoque, preços, parceiros, inteligência, relatórios, finanças e alertas | Routers registrados e testes backend executados; smoke tests anônimos feitos contra o banco configurado. |
| Persistência | PostgreSQL, SQLAlchemy 2 e Alembic | Migrações aplicadas e schema comparado com os modelos. |
| Acesso | Sessões em cookie HTTP-only, permissões por papel, revogação de sessão, registro de auditoria e OAuth Google opcional | Cobertura automatizada para cadastro inicial, login, logout, permissões, CORS e comportamento sem configuração OAuth. Não foi usado usuário real de produção. |
| Inteligência | Estatísticas de consumo, interfaces de provider e avaliações | Testes existentes cobrem cálculos e cenários sem provider configurado; não há evidência de previsão externa configurada neste ambiente. |

Jornadas representadas no código:

- Catálogo de categorias/produtos, custos, preços e históricos.
- Compras com fornecedor, itens, custos adicionais e reflexos operacionais.
- Pedidos com clientes, itens, snapshots de preço e movimentação de estoque.
- Estoque, movimentos e sinais de mínimo/ruptura.
- Clientes, endereços, fornecedores e operações Imperial Partner.
- Contas a pagar/receber, categorias financeiras, liquidações, estornos e caixa.
- Autenticação, sessões, autorização e auditoria.
- Relatórios, alertas e sinais de reposição/demanda.

## 3. Banco de dados e migrações

### Estado verificado

- Alembic `current`: `0007_single_company_indexes`.
- Alembic `head`: `0007_single_company_indexes`.
- 33 tabelas esperadas pelos modelos presentes no banco.
- Comparação ORM × banco: **nenhuma diferença reportada** para tabelas, colunas, tipos compilados, nulabilidade, chaves primárias e estrangeiras/on-delete, índices, constraints unique e checks.
- As quatro tabelas financeiras ausentes inicialmente (`financial_categories`, `accounts_payable`, `accounts_receivable` e `cash_movements`) agora existem.
- Não foram encontradas tabelas de organização/membership nem políticas RLS; `customers.establishment` permanece presente.
- A inspeção final não encontrou schemas temporários de testes deixados para trás.

### Alterações executadas

1. Antes de DDL, foi criado um backup lógico PostgreSQL em formato custom, `imperial-pack-pre-change-20261005.dump`, no armazenamento desta sessão. O tamanho e a assinatura `PGDMP` foram verificados. A validação do catálogo via `pg_restore` não foi possível porque o controle de aplicativos do Windows bloqueou sua execução; portanto, não se afirma que um restore completo foi testado.
2. A revisão `0006_integrity_controls` foi ajustada para criar, quando ausentes, as tabelas financeiras definidas no metadata ORM antes de aplicar os controles de integridade.
3. A revisão `0006` foi aplicada ao banco configurado.
4. A revisão aditiva `0007_single_company_indexes` foi criada e aplicada para adicionar o índice de consulta de oportunidades por cliente.
5. As migrações de tenant `0007–0009`, que ainda não haviam sido aplicadas ao banco consultado e eram incompatíveis com a arquitetura single-company solicitada, foram removidas da cadeia de código; a revisão atual tem outro `0007` correspondente à arquitetura de empresa única.
6. Os testes de integração PostgreSQL usaram schemas temporários isolados e estes foram removidos ao fim das execuções.

As alterações de banco foram aditivas no ambiente verificado. Antes de promover para outra instalação, confirme sua revisão Alembic: uma instalação que já tenha aplicado as antigas migrações de tenant `0007–0009` precisa de avaliação específica; não se deve aplicar a nova cadeia cegamente sobre ela.

## 4. Correções realizadas

- **Cadastro de produto:** a criação de produto novo agora usa a operação de criação; a edição continua usando atualização.
- **Strings da interface:** caracteres corrompidos foram corrigidos nas páginas de produtos e inteligência.
- **OAuth Google:** `/api/auth/setup-status` informa se as credenciais e o redirect URI estão configurados. A tela só mostra a opção Google quando disponível; os endpoints OAuth retornam `503` quando não configurados.
- **Alertas:** a fixture de teste passou a gerar um sinal de estoque baixo válido, em vez de inserir um alerta incompatível com as permissões/cenário. A autorização de atualização não autorizada permanece coberta.
- **Configuração de produção:** validação de chave secreta de pelo menos 32 bytes e exigência de cookies seguros em produção.
- **Metadados ORM:** unicidades e índices foram alinhados com as constraints existentes no banco.
- **Migrations:** revisão de integridade compatibilizada com as tabelas financeiras ausentes; migrações incompatíveis com o modelo single-company retiradas da cadeia ainda não aplicada.

## 5. Testes e verificações

| Verificação | Resultado | Contexto |
|---|---:|---|
| Suite backend completa com integração PostgreSQL | **65 aprovados** | Executada antes da última alteração pequena em `setup-status`/OAuth. |
| Regressão direcionada após alteração OAuth | **12 aprovados** | Cadastro inicial, segurança de usuário, autorização single-company e configuração. 2 avisos de depreciação. |
| Testes de migrations/configuração | **7 aprovados** | Execução anterior, antes do último ajuste isolado de OAuth. |
| Frontend (`npm.cmd test`) | **4 aprovados** | 2 arquivos de teste: cálculos de compra e precificação. |
| Build (`npm.cmd run build`) | **Verificado após a alteração OAuth** | TypeScript (`tsc -b`) e Vite. |
| Smoke `/health` | **200** | Banco conectado; configuração local autenticada. |
| Smoke `/api/auth/setup-status` | **200** | Cadastro inicial indisponível e Google OAuth não configurado, conforme ambiente. |
| Smoke sem sessão: `/api/auth/me`, `/api/products`, `/api/finance/summary` | **401 esperado** | Confirma proteção contra acesso anônimo; não substitui jornada autenticada real. |
| Preflight CORS do frontend local | **200** | Origem `http://localhost:5173` autorizada com credenciais. |
| Navegador em `/acesso` | **Verificado** | Texto em português renderizado corretamente; botão Google ausente quando OAuth não está configurado. |

Os testes emitiram avisos de depreciação relacionados ao uso de `httpx` no `TestClient` do Starlette e na integração HTTPX do Authlib. Não causaram falhas.

## 6. Limitações e pontos ainda a acompanhar

- Não foi feita execução E2E autenticada de cada fluxo CRUD/financeiro em navegador, nem foram criados registros de negócio reais para essa auditoria.
- Não havia credenciais de usuário real nem credenciais OAuth Google disponíveis. Login/cadastro e revogação foram validados por testes automatizados; Google foi validado no estado não configurado.
- O teste visual cobriu a tela de acesso, não todas as telas.
- Os 4 testes frontend cobrem cálculos de compra e precificação, não todos os formulários, chamadas HTTP, permissões e estados de erro.
- O build/teste completo de backend com PostgreSQL foi aprovado antes da última mudança de resposta OAuth; a mudança posterior foi coberta por 12 testes direcionados.
- O backup foi criado e sua assinatura validada, mas `pg_restore` não pôde ser executado devido ao bloqueio do Windows; um restore real continua recomendado antes de uma implantação crítica.
- Não há lint frontend efetivo configurado no `package.json`.
- `PartnerMonitoring.tsx` existe, mas não foi identificado como rota ativa; confirmar se é intencional ou funcionalidade ainda não exposta.
- A validação do banco refere-se à instância alcançada pela configuração deste workspace, não certifica outras instalações ou ambientes de produção.
- A resposta saudável de `/health` confirma conectividade neste teste; um cenário de banco indisponível e uma rota separada de readiness não foram validados nesta execução.

## 7. Recomendações priorizadas

1. Executar uma validação E2E autenticada em homologação para os fluxos compra → estoque → contas a pagar e pedido → baixa de estoque → contas a receber, além de clientes, produtos, permissões, alertas e relatórios.
2. Realizar um restore de teste do backup em ambiente isolado antes de promover alterações de banco críticas.
3. Antes de atualizar outras instalações, inspecionar `alembic current`; tratar separadamente bancos que tenham aplicado as antigas revisões de tenant `0007–0009`.
4. Configurar OAuth apenas quando credenciais e redirect URI válidos estiverem disponíveis; a ausência atual é explicitamente indicada pela API e interface.
5. Configurar lint e, se necessário operacionalmente, distinguir health de liveness e readiness.
6. Decidir se `PartnerMonitoring.tsx` deve ser conectado a uma rota ou removido em uma alteração própria.

## 8. Conclusão

**Testes frontend: aprovados. Build frontend: aprovado. Regressão backend pós-ajuste OAuth: aprovada. Suite backend completa com PostgreSQL: aprovada na execução documentada. Schema do banco configurado: alinhado e na revisão atual.**

Não há evidência nesta auditoria de incompatibilidade restante entre os modelos ORM e a instância PostgreSQL verificada, nem de dependência do sistema em organizações/RLS. A conclusão não equivale a certificação de todos os fluxos reais em produção: isso exige E2E autenticado em homologação, com dados de teste, e validação de restore do backup.
