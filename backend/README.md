# Imperial Pack FastAPI backend

The repository root remains the Vite frontend. This backend uses FastAPI, SQLAlchemy 2 and PostgreSQL through the standard `DATABASE_URL` setting. It is an internal single-company application for Imperial Pack: there are no organizations, memberships, tenant IDs, or organization-based RLS policies. `customers.establishment` remains the customer's business name, not a tenant boundary. The backend does not substitute SQLite or an in-memory database when configuration is absent: database-backed endpoints return 503 until configured.

## Local setup

1. Create a PostgreSQL database and copy `.env.example` to `backend/.env`.
2. Set a cryptographically random `SECRET_KEY` and the database credentials.
3. Install `python -m pip install -r requirements.txt`.
4. Inspect the current database revision with `alembic -c alembic.ini current` and the available revisions with `alembic -c alembic.ini history`. After a logical backup and schema review, apply the reviewed single-company revision with `alembic -c alembic.ini upgrade 0007_single_company_indexes`. This revision path creates the missing finance tables and their integrity controls; it does not add organizations or RLS.
5. To create the first administrator through the login screen, set `INITIAL_ADMIN_EMAIL` to the one authorized address before starting the API. Registration is available only while the users table is empty and only for that address. Alternatively, bootstrap two administrators with `python -m app.auth.bootstrap admin1@example.com admin2@example.com`; passwords are prompted and hashed. Choose one bootstrap path.
6. Start with `uvicorn app.main:app --reload` from this directory.

Google OAuth is enabled only when client ID, secret, redirect URI, and the explicit authorized-email allowlist are configured. OAuth never creates an account automatically.

For the deployed Vercel frontend (`https://imperial-pack.vercel.app`) and Render API, CORS allows that exact origin plus the origins listed in `FRONTEND_ORIGINS`. For other HTTPS frontend and API deployments, set `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true`; keep `FRONTEND_ORIGINS` limited to exact trusted frontend origins. Same-site/local development can use `COOKIE_SAMESITE=lax` and `COOKIE_SECURE=false`. `/health` reports `database_connected` after executing `SELECT 1`. Alembic requires `DATABASE_URL` and does not fall back to localhost.

Production settings require a `SECRET_KEY` of at least 32 UTF-8 bytes and secure cookies. The API is not production-ready until deployment secrets, PostgreSQL, HTTPS, backup policy, and the authorized email allowlist are configured and reviewed.

## PostgreSQL integrity tests

The default backend suite uses isolated SQLite databases for fast regression checks. PostgreSQL locking and concurrent idempotency checks are in `tests/test_postgres_integrity.py`; run them with `TEST_POSTGRES_URL` pointing to a dedicated disposable test database:

```powershell
$env:TEST_POSTGRES_URL = "postgresql+psycopg://..."
python -m pytest -q tests/test_postgres_integrity.py
```

The test fixture creates and drops a uniquely named `ip_integrity_*` schema and requires permission to create/drop schemas. Point `TEST_POSTGRES_URL` only at a dedicated disposable PostgreSQL test database; never use the production database. Without this variable, PostgreSQL integration cases are skipped and SQLite results do not certify PostgreSQL concurrency.

## Operational alerts and opportunities

`GET /api/alerts` and `GET /api/opportunities` refresh persistent records from inventory balances, pending financial titles, non-cancelled customer orders, and active partner history. Source visibility follows the existing `inventory:read`, `finance:read`, `customers:read`, and `partners:read` permissions. Status changes require a matching write permission or the dedicated `alerts:manage` / `opportunities:manage` permission and are audited.

Rules use recorded facts only. Zero stock is high priority; positive stock below the configured minimum is medium. Financial titles overdue by calendar date are high priority; titles due within seven days are medium. Customer and partner replenishment windows use their observed mean purchase intervals and open three days before the expected date. A frequency change requires at least four orders and a latest interval at least 50% shorter or longer than the preceding intervals' mean. A partner product-quantity pattern change requires at least three recorded purchases and a latest quantity at least 50% above or below the previous purchases' mean. Product demand opportunities compare quantities in the last 30 days with the prior 30 days and require an increase. Replenishment is omitted when customer history is `insufficient_data`.

Priority is categorical and rule-based: overdue purchase patterns become high only at 1.5 times the observed interval; frequency drops become high at twice the prior interval mean; partner quantity changes become high when the latest quantity is at least twice or at most half of its previous mean. Event keys are unique per rule and entity. Repeated reads update an active record instead of inserting duplicates; a cleared event is closed and can be reopened if it recurs.

## Revisões de produção

O processo da API não executa Alembic ao iniciar. Antes de publicar alterações de schema, use o Shell do serviço Render apontado para o mesmo `DATABASE_URL` da API. Faça primeiro um backup/snapshot no Neon e confira a revisão real:

```bash
cd backend  # omita se o Root Directory do serviço Render já for backend
alembic -c alembic.ini current
alembic -c alembic.ini heads
```

O head deste checkout é `0010_planning_workspace`. As revisões `0009_product_target_margin` e `0010_planning_workspace` adicionam, respectivamente, a margem alvo dos produtos e as tabelas do Planejar. Se a revisão atual for `0008_intelligence_training_permission` ou `0009_product_target_margin`, depois de confirmar backup e destino, avance pelo caminho normal:

```bash
alembic -c alembic.ini upgrade head
```

Confirme então `alembic current` e consulte o schema no mesmo banco. A coluna `products.target_margin_percent` é `NUMERIC(8,4) NOT NULL`, com default de banco `30`, alinhado ao default de criação de produto já existente. A migration preserva linhas e não modifica preço nem custo. `planning_goals.planning_id` referencia `plannings.id` com `ON DELETE SET NULL`; as demais tabelas e vínculos são criados pela revisão `0010`.

Se `current` indicar `0010_planning_workspace` mas a coluna ou as tabelas não existirem, pare: isso indica divergência entre histórico e schema. Não use `alembic stamp`, não rebaixe a revisão e não reaplique migrations antigas. Guarde o resultado das consultas, tire novo snapshot e prepare uma nova migration somente para os objetos comprovadamente ausentes ou incompletos. Não configure migrations para executar a cada worker iniciar; use uma execução única de release/pre-deploy no Render.

## Validar a migration 0010 em PostgreSQL descartável

O teste `tests/test_planning_migration.py::test_planning_migration_grants_permission_idempotently_on_postgresql` cria um schema temporário, executa a migration duas vezes, verifica os tipos PostgreSQL e confirma que só há uma associação da permissão. Ao terminar, remove esse schema com `CASCADE`. A proteção do teste só aceita `localhost`/loopback e um nome de banco terminado em `_test`; não configure aqui a URL do Neon nem qualquer banco com dados que devam ser preservados.

Validação registrada em 2026-10-15: `python -m pytest -q tests/test_planning_migration.py` passou com **10 testes** usando um cluster PostgreSQL 18 local, isolado e descartável; o cluster foi encerrado e os arquivos temporários removidos. Isso comprova a execução da integração contra PostgreSQL 18 local, mas não contra a versão do Neon nem contra produção. A execução sem `TEST_POSTGRES_URL` continua ignorando a integração PostgreSQL.

Execute a partir da raiz do repositório. O exemplo usa Docker Desktop no PowerShell, contêiner e volume anônimo descartáveis, nome único, porta publicada somente em loopback e banco de teste. O método `trust` abaixo não usa senha e deve ficar restrito a esse contêiner local:

```powershell
$containerName = "imperial-pack-postgres-test-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$containerStarted = $false
try {
    docker run --detach --name $containerName `
      --env POSTGRES_DB=imperial_pack_test `
      --env POSTGRES_USER=imperial_pack_test `
      --env POSTGRES_HOST_AUTH_METHOD=trust `
      --publish 127.0.0.1:55432:5432 postgres:16
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the disposable PostgreSQL container.' }
    $containerStarted = $true

    $ready = $false
    for ($attempt = 0; $attempt -lt 30 -and -not $ready; $attempt++) {
        docker exec $containerName pg_isready -U imperial_pack_test -d imperial_pack_test *> $null
        $ready = $LASTEXITCODE -eq 0
        if (-not $ready) { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'Disposable PostgreSQL did not become ready.' }

    $repoRoot = Get-Location
    Set-Location backend
    $env:TEST_POSTGRES_URL = 'postgresql+psycopg://imperial_pack_test@127.0.0.1:55432/imperial_pack_test'
    $testExitCode = 1
    try {
        python -m pytest -q tests/test_planning_migration.py
        $testExitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item Env:TEST_POSTGRES_URL -ErrorAction SilentlyContinue
        Set-Location $repoRoot
    }
    if ($testExitCode -ne 0) { throw 'Migration tests failed.' }
}
finally {
    if ($containerStarted) {
        docker rm --force --volumes $containerName *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Could not remove the disposable PostgreSQL container and its volumes.' }
    }
}
```

Se for necessário autenticar o PostgreSQL local com senha, obtenha-a por prompt seguro e monte a URL no processo atual sem a imprimir, escapando usuário e senha como componentes de URL. Não passe credenciais em argumentos de linha de comando, não as inclua em arquivos versionados e não use URLs de produção. `TEST_POSTGRES_URL` deve apontar exclusivamente para um PostgreSQL local descartável com banco terminado em `_test`. O teste compila o cast para `VARCHAR(36)` e exercita a execução real no PostgreSQL; o teste SQLite, sozinho, não comprova essa compatibilidade.
