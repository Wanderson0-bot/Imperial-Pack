from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class Role(Base, Timestamped):
    __tablename__ = 'roles'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Permission(Base):
    __tablename__ = 'permissions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class RolePermission(Base):
    __tablename__ = 'role_permissions'
    role_id: Mapped[str] = mapped_column(ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)


class User(Base, Timestamped):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role_id: Mapped[str] = mapped_column(ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_general_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    __tablename__ = 'user_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class Customer(Base, Timestamped):
    __tablename__ = 'customers'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    establishment: Mapped[str | None] = mapped_column(String(180))
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True)
    city: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(30), default='INTERNAL', nullable=False)
    status: Mapped[str] = mapped_column(String(30), default='ACTIVE', nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    external_id: Mapped[str | None] = mapped_column(String(120))


class CustomerAddress(Base, Timestamped):
    __tablename__ = 'customer_addresses'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id', ondelete='CASCADE'), index=True)
    label: Mapped[str] = mapped_column(String(80), default='Principal')
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    number: Mapped[str | None] = mapped_column(String(30))
    complement: Mapped[str | None] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2))
    postal_code: Mapped[str | None] = mapped_column(String(20))


class ProductCategory(Base, Timestamped):
    __tablename__ = 'product_categories'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    image_url: Mapped[str | None] = mapped_column(Text)


class Product(Base, Timestamped):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category_id: Mapped[str | None] = mapped_column(ForeignKey('product_categories.id', ondelete='SET NULL'))
    image_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    current_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    markup_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=0, nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (CheckConstraint('current_cost >= 0', name='cost_nonnegative'), CheckConstraint('current_price >= 0', name='price_nonnegative'))


class Supplier(Base, Timestamped):
    __tablename__ = 'suppliers'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(String(240))
    minimum_order: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    delivery_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SupplierProduct(Base):
    __tablename__ = 'supplier_products'
    supplier_id: Mapped[str] = mapped_column(ForeignKey('suppliers.id', ondelete='CASCADE'), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)


class Purchase(Base, Timestamped):
    __tablename__ = 'purchases'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    supplier_id: Mapped[str] = mapped_column(ForeignKey('suppliers.id', ondelete='RESTRICT'), nullable=False, index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(100))
    observations: Mapped[str | None] = mapped_column(Text)
    products_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal('0'), server_default='0', nullable=False)
    freight: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    other_costs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default='APPROVED', nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    idempotency_key: Mapped[str | None] = mapped_column(String(120))


class PurchaseItem(Base):
    __tablename__ = 'purchase_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    purchase_id: Mapped[str] = mapped_column(ForeignKey('purchases.id', ondelete='CASCADE'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal('0'), server_default='0', nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    freight_share: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    other_cost_share: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    real_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)


class Order(Base, Timestamped):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id', ondelete='RESTRICT'), nullable=False, index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default='NEW', nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    responsible_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    source: Mapped[str] = mapped_column(String(30), default='INTERNAL', nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(120))
    stock_committed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OrderItem(Base):
    __tablename__ = 'order_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class InventoryBalance(Base, Timestamped):
    __tablename__ = 'inventory_balances'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), nullable=False, unique=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)


class InventoryMovement(Base):
    __tablename__ = 'inventory_movements'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    reason: Mapped[str] = mapped_column(String(180), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    purchase_id: Mapped[str | None] = mapped_column(ForeignKey('purchases.id', ondelete='SET NULL'))
    order_id: Mapped[str | None] = mapped_column(ForeignKey('orders.id', ondelete='SET NULL'))
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class CostHistory(Base):
    __tablename__ = 'cost_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), index=True)
    purchase_id: Mapped[str | None] = mapped_column(ForeignKey('purchases.id', ondelete='SET NULL'))
    previous_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    new_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class PricingHistory(Base):
    __tablename__ = 'pricing_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), index=True)
    previous_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    margin_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    markup_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class Partner(Base, Timestamped):
    __tablename__ = 'partners'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id', ondelete='RESTRICT'), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE', nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class PartnerCondition(Base, Timestamped):
    __tablename__ = 'partner_conditions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), unique=True)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    payment_term_days: Mapped[int | None] = mapped_column(Integer)
    payment_method: Mapped[str | None] = mapped_column(String(80))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class PartnerProduct(Base):
    __tablename__ = 'partner_products'
    partner_id: Mapped[str] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class ConsumptionHistory(Base):
    __tablename__ = 'consumption_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id', ondelete='RESTRICT'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey('orders.id', ondelete='RESTRICT'), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    interval_since_previous_days: Mapped[int | None] = mapped_column(Integer)
    voided: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PartnerReplenishmentCycle(Base, Timestamped):
    __tablename__ = 'partner_replenishment_cycles'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), index=True)
    cycle_type: Mapped[str] = mapped_column(String(20), nullable=False)
    custom_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PartnerAlert(Base):
    __tablename__ = 'partner_alerts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey('products.id', ondelete='SET NULL'))
    entity_type: Mapped[str] = mapped_column(String(30), default='partner', nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    entity_label: Mapped[str] = mapped_column(String(180), default='', nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(180), default='', nullable=False)
    description: Mapped[str] = mapped_column(Text, default='', nullable=False)
    reason: Mapped[str] = mapped_column(Text, default='', nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default='medium', nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='OPEN', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerOpportunity(Base):
    __tablename__ = 'partner_opportunities'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey('customers.id', ondelete='CASCADE'), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), default='partner', nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    entity_label: Mapped[str] = mapped_column(String(180), default='', nullable=False)
    title: Mapped[str] = mapped_column(String(180), default='', nullable=False)
    description: Mapped[str] = mapped_column(Text, default='', nullable=False)
    action: Mapped[str] = mapped_column(Text, default='', nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='OPEN', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class Prediction(Base):
    __tablename__ = 'predictions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    partner_id: Mapped[str] = mapped_column(ForeignKey('partners.id', ondelete='CASCADE'), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='RESTRICT'))
    prediction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class PredictionEvaluation(Base):
    __tablename__ = 'prediction_evaluations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(ForeignKey('predictions.id', ondelete='CASCADE'), index=True)
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    absolute_error: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class FinancialCategory(Base, Timestamped):
    __tablename__ = 'financial_categories'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default='GENERAL', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))


class AccountPayable(Base, Timestamped):
    __tablename__ = 'accounts_payable'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    supplier_id: Mapped[str] = mapped_column(ForeignKey('suppliers.id', ondelete='RESTRICT'), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(180), nullable=False)
    category_id: Mapped[str | None] = mapped_column(ForeignKey('financial_categories.id', ondelete='SET NULL'))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='PENDING', nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    __table_args__ = (CheckConstraint('amount >= 0', name='payable_amount_nonnegative'),)


class AccountReceivable(Base, Timestamped):
    __tablename__ = 'accounts_receivable'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id', ondelete='RESTRICT'), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(180), nullable=False)
    category_id: Mapped[str | None] = mapped_column(ForeignKey('financial_categories.id', ondelete='SET NULL'))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='PENDING', nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(36))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    __table_args__ = (CheckConstraint('amount >= 0', name='receivable_amount_nonnegative'),)


class CashMovement(Base, Timestamped):
    __tablename__ = 'cash_movements'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    movement_type: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[str | None] = mapped_column(ForeignKey('financial_categories.id', ondelete='SET NULL'))
    origin: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(36))
    notes: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'))
    payable_id: Mapped[str | None] = mapped_column(ForeignKey('accounts_payable.id', ondelete='SET NULL'))
    receivable_id: Mapped[str | None] = mapped_column(ForeignKey('accounts_receivable.id', ondelete='SET NULL'))
    settlement_key: Mapped[str | None] = mapped_column(String(180))
    __table_args__ = (CheckConstraint('amount >= 0', name='cash_movement_amount_nonnegative'),)


Index('ix_orders_customer_date', Order.customer_id, Order.ordered_at)
Index('ix_partner_products_last_seen', PartnerProduct.partner_id, PartnerProduct.last_seen_at)
Index('uq_customers_origin_external_id', Customer.origin, Customer.external_id, unique=True)
Index('uq_orders_source_external_id', Order.source, Order.external_id, unique=True)
Index('uq_suppliers_normalized_name', func.lower(func.trim(Supplier.name)), unique=True)
Index('uq_partner_alerts_dedupe_key', PartnerAlert.dedupe_key, unique=True)
Index('uq_partner_opportunities_dedupe_key', PartnerOpportunity.dedupe_key, unique=True)
Index('uq_purchases_idempotency_key', Purchase.idempotency_key, unique=True)
Index('uq_cash_movements_settlement_key', CashMovement.settlement_key, unique=True)
Index(
    'uq_accounts_payable_reference_id',
    AccountPayable.reference_id,
    unique=True,
    postgresql_where=AccountPayable.reference_id.is_not(None),
    sqlite_where=AccountPayable.reference_id.is_not(None),
)
Index(
    'uq_accounts_receivable_reference_id',
    AccountReceivable.reference_id,
    unique=True,
    postgresql_where=AccountReceivable.reference_id.is_not(None),
    sqlite_where=AccountReceivable.reference_id.is_not(None),
)
