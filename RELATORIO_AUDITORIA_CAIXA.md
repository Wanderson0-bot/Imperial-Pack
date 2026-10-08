# Auditoria do módulo Caixa — Imperial Pack System

**Data:** 07/10/2026  
**Escopo:** auditoria exclusiva, somente leitura, do banco, backend, frontend, integrações, permissões, auditoria e testes relacionados ao Caixa.  
**Restrições observadas:** nenhum código, banco, migration ou arquitetura foi alterado. A consulta ao PostgreSQL foi limitada a metadados do schema, revisão Alembic e grants de permissões; nenhum registro de negócio foi consultado ou modificado.

## Parecer executivo

O sistema já possui um **ledger financeiro operacional**: `cash_movements`, APIs para listar e registrar entradas/saídas, cálculo do resumo financeiro, geração de movimentos quando contas a pagar/receber são liquidadas e movimentos inversos para reembolsos.

Esse ledger **não é um módulo de caixa/PDV com ciclo de caixa**. Não há estrutura ou interface dedicada para abertura, fechamento, conferência de saldo físico, sangria, suprimento ou ajuste formal. Também não existe página ou service frontend de Caixa.

As integrações descritas no contexto estão presentes no código. A compra/pedido cria título financeiro automaticamente; o movimento de caixa surge quando o título passa para pago/recebido. Portanto, a cadeia é **automática na geração do movimento a partir da liquidação**, mas a liquidação é disparada pela mudança de status, não pela simples criação da compra ou do pedido. O contexto informado pelo usuário relata validação E2E recente dessas integrações; essa execução não foi repetida nesta auditoria.

## Matriz solicitada

| Área | Existe | Funciona | Evidência | Falta |
|---|---|---|---|---|
| Banco | Sim | Sim, schema presente no PostgreSQL consultado | Existem `financial_categories`, `accounts_payable`, `accounts_receivable`, `cash_movements` e `audit_logs`; inspeção de colunas, PKs, FKs, índices e checks. Alembic atual: `0007_single_company_indexes`. | Não falta uma tabela básica de movimentações. Falta estrutura de sessão/turno de caixa, abertura e fechamento. |
| Backend | Sim | Sim para ledger, liquidações, reembolsos e resumo, com testes correspondentes | Router `/finance`, schema `CashMovement*`, persistência SQLAlchemy e testes em `test_finance.py`. | Serviço separado, endpoints e regras próprias de ciclo de caixa não existem. |
| Frontend | Não há Caixa dedicado | Não há interface do Caixa | `/src` não contém página/service/rota do Caixa. A navegação não oferece Caixa; o resumo de compra é apenas uma calculadora da compra. | Página, listagem, filtros e formulários específicos do Caixa, condicionados às permissões que vierem a ser definidas. |
| Abertura | Não | Não | Não há tabela, model, schema, endpoint ou ação de abertura encontrados. | Sessão de caixa e valor inicial, se fizerem parte do escopo funcional. |
| Fechamento | Não | Não | Não há tabela, endpoint, conferência nem fechamento de sessão encontrados. | Fechamento, saldo esperado/contado e divergência, se exigidos. |
| Entrada | Sim | Sim, como movimento genérico ou liquidação de recebível | `ENTRY` é aceito em `POST /finance/movements`; recebimento de conta gera `RECEIVABLE_SETTLEMENT`. | Identificação/fluxo específico de entrada de caixa, caso seja necessário além do ledger. |
| Saída | Sim | Sim, como movimento genérico ou liquidação de conta a pagar | `EXIT` é aceito em `POST /finance/movements`; pagamento de conta gera `PAYABLE_SETTLEMENT`. | Identificação/fluxo específico de saída de caixa, caso seja necessário além do ledger. |
| Sangria | Parcial | Não como operação tipada | Pode ser representada manualmente como movimento `EXIT`; não há tipo ou regra de sangria. | Ação/formulário e distinção auditável como sangria, se requerida. |
| Suprimento | Parcial | Não como operação tipada | Pode ser representado manualmente como movimento `ENTRY`; não há tipo ou regra de suprimento. | Ação/formulário e distinção auditável como suprimento, se requerida. |
| Estorno | Parcial | Sim para liquidações de pagar/receber; não para movimento manual arbitrário | Reembolso de conta gera movimento oposto e é idempotente; status fica `CANCELLED` e `refunded_at` é preenchido. | Não há cancelamento/estorno formal de um movimento manual genérico. |
| Ajuste | Não como operação própria | Parcial apenas via movimento genérico | Não há endpoint/tipo `ADJUSTMENT`; o payload aceita somente `ENTRY` ou `EXIT`. | Processo de ajuste identificado e sua regra de saldo/auditoria, se necessário. |
| Compras → Caixa | Sim | Sim, híbrido e em duas etapas | Compra atualiza estoque e cria conta a pagar `PENDING`; ao pagar, cria `EXIT` vinculado à conta. Teste verifica a conta gerada; liquidação/estorno está coberta separadamente. | Não falta a integração básica. A compra ainda não cria saída de caixa no momento do registro — coerente com título pendente. |
| Pedidos → Caixa | Sim | Sim, híbrido e em duas etapas | Pedido confirmado movimenta estoque e cria conta a receber `PENDING`; ao receber, cria `ENTRY` vinculada à conta. Teste verifica título; liquidação/estorno está coberta separadamente. | Não falta a integração básica. O pedido não cria entrada de caixa antes do recebimento. |
| Contas a pagar → Caixa | Sim | Sim | Transição para `PAID` cria saída; reembolso cria entrada inversa. `settlement_key` evita duplicar movimentos de liquidação/reembolso. | Não falta o caminho operacional básico. |
| Contas a receber → Caixa | Sim | Sim | Transição para `RECEIVED` cria entrada; reembolso cria saída inversa. `settlement_key` evita duplicações. | Não falta o caminho operacional básico. |
| Permissões | Sim | Parcial na gestão; autorização backend integrada | Existem `finance:read` e `finance:write`, verificados via `RolePermission` nos endpoints financeiros. Os dois registros existem no catálogo do banco consultado. | Não há granularidade por operação nem tela frontend para configurar permissões de papéis. A API permite criar papel com permissões, mas não foi encontrada API para editar permissões de papel existente. |
| Auditoria | Sim | Sim para operações de escrita implementadas | `audit_logs` recebe eventos de criação de movimento, liquidação, criação/alteração/reembolso de contas e criação de categoria. | Leituras não são auditadas; operações de abertura/fechamento/sangria/suprimento/ajuste não existem para auditar. |
| Testes | Sim | Parcial em relação a um módulo de Caixa completo | Testes cobrem criação de títulos, resumo, liquidação idempotente, reembolso e cancelamento de pedido após reembolso; há teste PostgreSQL para unicidade de `settlement_key`. | Sem testes de UI/fluxo frontend, sessão de caixa, abertura/fechamento, conferência, sangria, suprimento ou ajuste. |

## 1. Banco de dados

### Estruturas confirmadas

A inspeção do banco PostgreSQL configurado encontrou as tabelas financeiras abaixo. A consulta do catálogo confirmou a revisão Alembic `0007_single_company_indexes`.

| Tabela | Colunas | PK / FKs | Índices e constraints relevantes |
|---|---|---|---|
| `financial_categories` | `id`, `name`, `kind`, `is_active`, `created_by`, `created_at`, `updated_at` | PK `id`; `created_by` → `users.id` (`SET NULL`) | Sem índice ou unique próprio; sem check. |
| `accounts_payable` | `id`, `supplier_id`, `description`, `category_id`, `amount`, `due_at`, `paid_at`, `refunded_at`, `status`, `payment_method`, `reference_id`, `notes`, `created_by`, `created_at`, `updated_at` | PK `id`; fornecedor → `suppliers.id` (`RESTRICT`); categoria → `financial_categories.id` (`SET NULL`); criador → `users.id` (`SET NULL`) | Índice de `supplier_id`; índice unique parcial em `reference_id` não nulo; check `amount >= 0`. |
| `accounts_receivable` | `id`, `customer_id`, `description`, `category_id`, `amount`, `due_at`, `received_at`, `refunded_at`, `status`, `payment_method`, `reference_id`, `notes`, `created_by`, `created_at`, `updated_at` | PK `id`; cliente → `customers.id` (`RESTRICT`); categoria → `financial_categories.id` (`SET NULL`); criador → `users.id` (`SET NULL`) | Índice de `customer_id`; índice unique parcial em `reference_id` não nulo; check `amount >= 0`. |
| `cash_movements` | `id`, `movement_type`, `amount`, `category_id`, `origin`, `reference_id`, `notes`, `occurred_at`, `created_by`, `payable_id`, `receivable_id`, `settlement_key`, `created_at`, `updated_at` | PK `id`; categoria → `financial_categories.id` (`SET NULL`); criador → `users.id` (`SET NULL`); pagar → `accounts_payable.id` (`SET NULL`); receber → `accounts_receivable.id` (`SET NULL`) | Índice unique em `settlement_key`; check `amount >= 0`. |
| `audit_logs` | `id`, `actor_id`, `action`, `entity_type`, `entity_id`, `details`, `occurred_at` | PK `id`; ator → `users.id` (`SET NULL`) | Índice de `actor_id`. |

`role_permissions` tem PK composta (`role_id`, `permission_id`) e FKs para `roles.id` e `permissions.id`, com `CASCADE`.

### Relacionamentos e lacunas do schema

- O vínculo de uma movimentação com título a pagar/receber é feito por FKs `payable_id` e `receivable_id`.
- O vínculo com compra/pedido é **indireto**: `accounts_payable.reference_id` guarda o identificador da compra e `accounts_receivable.reference_id` guarda o identificador do pedido. Esses `reference_id` são strings, não FKs para `purchases`/`orders`. `cash_movements` não tem `purchase_id` nem `order_id`.
- Há coluna `payment_method` em contas a pagar e receber, mas não tabela de meios de pagamento nem FK/enum. `cash_movements` não tem coluna de meio de pagamento. Os títulos criados automaticamente por compra/pedido não informam método de pagamento.
- No ORM, os vínculos estão descritos por colunas/FKs; não foram encontradas propriedades `relationship()` para essas entidades.
- Não foi encontrada estrutura de sessão/turno/caixa registradora, abertura, fechamento ou caixa físico. A busca no catálogo por tabelas com nomes de caixa/turno/registradora encontrou somente `cash_movements`.
- Na tabela de movimentos, não há check constraint de domínio para `movement_type`; a validação `ENTRY`/`EXIT` ocorre na aplicação. Não há índice próprio de `occurred_at`, `reference_id`, `payable_id` ou `receivable_id` no schema consultado.

## 2. Backend e regras encontradas

O backend concentra a implementação financeira em `backend/app/finance/router.py`; não foi encontrado service de Caixa separado. O router registrado sob o prefixo da API `/finance` oferece:

- Categorias: `GET/POST /categories`.
- Contas a pagar: `GET/POST /payables`, `PATCH /payables/{id}` e `POST /payables/{id}/refund`.
- Contas a receber: `GET/POST /receivables`, `PATCH /receivables/{id}` e `POST /receivables/{id}/refund`.
- Movimentos: `GET/POST /movements`.
- Resumo financeiro: `GET /summary`, com filtros opcionais `start` e `end`.

O movimento manual recebe `movement_type`, `amount`, `origin`, categoria opcional, `reference_id`, observação e data. A aplicação aceita apenas `ENTRY` e `EXIT`; quantidade não negativa também é validada no banco. Sangria, suprimento e ajuste não têm tipos ou regras próprios.

`cash_flow_summary` soma movimentos `ENTRY` menos `EXIT`, filtrando esses movimentos pelo intervalo recebido. Também retorna totais pendentes de pagar e receber. Os valores pendentes não recebem filtro de data; o campo `cash_balance` é a diferença dos movimentos dentro do período, sem saldo inicial/carry-forward ou reconciliação com dinheiro contado.

## 3. Integrações operacionais

### Compra → estoque → contas a pagar → caixa

1. `create_purchase` registra a compra e seus itens, atualiza saldo de estoque/custo e cria uma `AccountPayable` pendente com `reference_id` igual ao ID da compra.
2. Isso não cria movimento de caixa na criação da compra.
3. Quando a conta muda para `PAID`, o backend cria movimento `EXIT`, origem `PAYABLE_SETTLEMENT`, com `payable_id` e uma chave de liquidação idempotente.
4. Ao cancelar compra, o sistema reverte estoque/custo e cancela o título não pago. Se já pago, exige o reembolso antes do cancelamento; o reembolso gera a entrada inversa.

### Pedido → estoque → contas a receber → caixa

1. `create_order` cria pedido e itens; em status operacional confirmado, atualiza estoque; cria uma `AccountReceivable` pendente com `reference_id` igual ao ID do pedido.
2. Isso não cria movimento de caixa na criação do pedido.
3. Quando a conta muda para `RECEIVED`, o backend cria movimento `ENTRY`, origem `RECEIVABLE_SETTLEMENT`, com `receivable_id` e chave idempotente.
4. Reembolso gera `EXIT`. O cancelamento de pedido recebido exige reembolso anterior; após isso o título é cancelado e estoque revertido.

**Classificação:** híbrida na jornada de ponta a ponta: criação de título/estoque e criação do movimento correspondente são automáticas no backend, mas o caixa somente muda na ação de liquidação (mudança do status da conta). Não é entrada/saída automática no momento de salvar compra/pedido nem uma integração manual duplicada de movimento quando a conta é liquidada.

## 4. Frontend

- `src/App.tsx` não declara rota de Caixa nem importa página de Caixa.
- `src/components/Sidebar.tsx` não lista Caixa.
- Não foram encontrados `cashService`, hook, formulário, tabela, botão ou componente próprio de Caixa no frontend.
- `src/pages/ReportsPage.tsx` mostra vendas, estoque, margem, produtos e clientes; não consulta o endpoint `/finance/summary`.
- O “Resumo financeiro” em `PurchasePage.tsx` é um cálculo de itens/frete para a compra, não o saldo nem o extrato do Caixa.
- Não existe tratamento visual de permissões para ações de Caixa porque essa interface não existe.

## 5. Permissões e audit logs

As permissões existentes relacionadas ao financeiro são `finance:read` e `finance:write`. As rotas de leitura exigem a primeira; criação/alteração/liquidação/reembolso exigem a segunda. `require_permission` consulta `Permission` + `RolePermission` para o papel do usuário; `is_general_admin` passa pela autorização geral. Não se deve inferir a permissão de qualquer funcionário a partir do cargo nominal.

O catálogo do banco consultado continha essas duas permissões. A consulta somente leitura dos vínculos `RolePermission` não retornou grants `finance:*` associados a papéis naquele banco. Isso é um dado do estado consultado, não uma inferência sobre uma pessoa ou funcionário específico.

O backend permite **criar** papel com lista de permissões (`POST /users/roles`, protegido por `users:manage_roles`), e valida se as chaves informadas existem. Não foi encontrada rota para editar as permissões de um papel existente. A interface de usuários lista papéis e os seleciona ao criar usuário, mas não disponibiliza editor de papéis/permissões.

Eventos de escrita financeira registrados:

- `finance.cash_movement.create`: criação manual de movimento.
- `finance.settlement.cash_movement`: criação de movimento na liquidação.
- `finance.payable.create`, `finance.payable.update`, `finance.payable.refund`.
- `finance.receivable.create`, `finance.receivable.update`, `finance.receivable.refund`.
- `finance.category.create`.
- Cancelamentos de compra/pedido também auditam alteração/cancelamento do título e a operação comercial correspondente.

Listagens e consultas de resumo não geram eventos de auditoria. O log guarda ator, ação, entidade, ID, detalhes e instante.

## 6. Testes existentes e limites

Em `backend/tests/test_finance.py`:

- `test_financial_records_are_created_for_purchase_and_order`: compra cria conta a pagar pendente pelo total e pedido cria conta a receber pendente pelo preço.
- `test_cash_flow_summary_counts_real_entries_and_exits`: verifica entradas, saídas e saldo calculado.
- `test_title_settlement_and_refund_create_idempotent_cash_movements`: verifica liquidação única, reembolso, vínculos às contas e saldo final.
- `test_received_order_requires_refund_before_cancellation`: verifica bloqueio de cancelamento sem reembolso e reversão de estoque depois do reembolso.

Em `backend/tests/test_integrity_migration.py`, a migration é exercitada contra SQLite e o teste verifica tabelas financeiras, chave de liquidação, colunas de reembolso e unicidade de referência dos títulos. Em `backend/tests/test_postgres_integrity.py`, há teste de unicidade PostgreSQL para `settlement_key`.

Não foram encontrados testes frontend para Caixa. Os testes de finanças citados não exercitam login/autorização em chamadas HTTP do Caixa, UI, abertura/fechamento, contagem física, sangria, suprimento ou ajuste formal. A validação E2E mais recente mencionada no contexto foi considerada como informação fornecida pelo usuário, mas não foi reexecutada nesta auditoria.

## Conclusões solicitadas

1. **O que o Caixa já possui:** ledger `cash_movements`, categorias, endpoints de movimento e resumo, vinculação a contas a pagar/receber, `ENTRY`/`EXIT`, trilha de auditoria, liquidação e reembolso idempotentes.
2. **O que já está funcionando:** integração por títulos liquidados; pagamentos criam saídas e recebimentos criam entradas. O resumo calcula entradas menos saídas. Os testes cobrem criação dos títulos, resumo, liquidação, reembolso e cancelamento condicionado a reembolso.
3. **O que está incompleto:** não existe Caixa como tela/módulo operacional; faltam ciclo de abertura/fechamento e reconciliação, operações tipadas de sangria/suprimento/ajuste e estorno de movimento manual genérico. A configuração de papéis/permissões não tem editor frontend nem API de atualização de papel existente.
4. **O que precisa ser implementado:** depende do escopo aprovado para o módulo. Para um Caixa com sessão/turno, implementar abertura/fechamento e UI/regras de operação, além de decidir se sangria, suprimento, ajuste e estorno manual são requisitos. Completar configuração de papéis/permissões se a configuração pelo admin precisar ser feita pela interface. Não é necessário reimplementar o ledger ou a integração de liquidações.
5. **O que NÃO deve ser recriado:** `cash_movements`, categorias, contas a pagar/receber, cálculo de resumo, FKs dos movimentos aos títulos, geração de saída/entrada nas liquidações nem a integração compra/pedido já existente.
6. **Será necessária alteração de banco?** Para manter as funcionalidades financeiras existentes ou expor o ledger numa tela simples, a auditoria não identificou necessidade de recriar ou substituir tabelas. Para abertura/fechamento e reconciliação persistentes, provavelmente será necessário ampliar o schema; somente o requisito detalhado pode determinar se isso requer tabela nova ou extensão das estruturas existentes. Esta auditoria não propõe nem aplica migration.

## Evidências principais no código

- Schema e router financeiro: `backend/app/finance/schemas.py`, `backend/app/finance/router.py`.
- Modelos: `backend/app/database/models.py`.
- Integração de compras e pedidos: `backend/app/purchases/router.py`, `backend/app/orders/router.py`.
- Autorização e papéis: `backend/app/auth/dependencies.py`, `backend/app/users/router.py`, `backend/app/users/schemas.py`.
- Testes: `backend/tests/test_finance.py`, `backend/tests/test_integrity_migration.py`, `backend/tests/test_postgres_integrity.py`.
- Navegação e rotas frontend: `src/App.tsx`, `src/components/Sidebar.tsx`; resumo de relatórios em `src/pages/ReportsPage.tsx`.
