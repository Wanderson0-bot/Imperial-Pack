from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings
from app.core.localization import translate_api_message, translate_validation_errors
from app.database.session import get_engine
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.customers.router import router as customers_router
from app.products.router import router as products_router
from app.suppliers.router import router as suppliers_router
from app.purchases.router import router as purchases_router
from app.orders.router import router as orders_router
from app.inventory.router import router as inventory_router
from app.pricing.router import router as pricing_router
from app.partners.router import router as partners_router
from app.intelligence.router import router as intelligence_router
from app.reports.router import router as reports_router
from app.finance.router import router as finance_router
from app.alerts.router import router as alerts_router

settings = get_settings()
app = FastAPI(title='Sistema Imperial Pack', version='0.1.0')
if settings.secret_key:
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site='lax', https_only=settings.environment.lower() == 'production')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])


@app.middleware('http')
async def set_content_language(request: Request, call_next):
    response = await call_next(request)
    response.headers['Content-Language'] = 'pt-BR'
    return response


@app.exception_handler(StarletteHTTPException)
async def localized_http_exception_handler(request: Request, error: StarletteHTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={'detail': translate_api_message(error.detail)},
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def localized_validation_exception_handler(request: Request, error: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={'detail': translate_validation_errors(error.errors())},
    )


for router in (auth_router, users_router, customers_router, products_router, suppliers_router, purchases_router, orders_router, inventory_router, pricing_router, partners_router, intelligence_router, finance_router, reports_router, alerts_router):
    app.include_router(router, prefix=settings.api_prefix)


@app.get('/health')
def health():
    database_connected = False
    if settings.database_url:
        try:
            with get_engine().connect() as connection:
                connection.execute(text('SELECT 1'))
            database_connected = True
        except SQLAlchemyError:
            pass
    return {'status': 'ok', 'database_configured': bool(settings.database_url), 'database_connected': database_connected, 'authentication_configured': bool(settings.secret_key), 'google_oauth_configured': bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)}
