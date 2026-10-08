from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import user_permission_keys
from app.customers.router import customer_history_summary, customer_replenishment_estimate
from app.database.models import (
    AccountPayable,
    AccountReceivable,
    Customer,
    InventoryBalance,
    Order,
    OrderItem,
    Partner,
    PartnerAlert,
    PartnerOpportunity,
    Product,
    Supplier,
    User,
)
from app.partners.router import partner_history_summary, partner_replenishment_estimate
from app.orders.states import REALIZED_ORDER_STATUSES

ALERT_WINDOW_DAYS = 7
REPLENISHMENT_EARLY_WINDOW_DAYS = 3
OPPORTUNITY_COMPARISON_DAYS = 30
ALL_SCOPES = {'inventory', 'finance', 'customers', 'partners'}
ENTITY_SCOPE = {
    'inventory_product': 'inventory',
    'payable': 'finance',
    'receivable': 'finance',
    'customer': 'customers',
    'partner': 'partners',
}


def accessible_scopes(db: Session, user: User) -> set[str]:
    if user.is_general_admin:
        return ALL_SCOPES.copy()
    permissions = set(user_permission_keys(db, user))
    return {
        scope for scope, permission in (
            ('inventory', 'inventory:read'),
            ('finance', 'finance:read'),
            ('customers', 'customers:read'),
            ('partners', 'partners:read'),
        ) if permission in permissions
    }


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _alert(alert_type: str, entity_type: str, entity_id: str, label: str, title: str, description: str, reason: str, priority: str, *, partner_id: str | None = None, product_id: str | None = None) -> dict:
    key = f'{alert_type}:{entity_type}:{entity_id}:{product_id or ""}'
    return {
        'alert_type': alert_type,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'entity_label': label,
        'title': title,
        'description': description,
        'reason': reason,
        'priority': priority,
        'partner_id': partner_id,
        'product_id': product_id,
        'dedupe_key': key,
    }


def _opportunity(opportunity_type: str, entity_type: str, entity_id: str, label: str, title: str, description: str, action: str, evidence: dict, *, partner_id: str | None = None, customer_id: str | None = None, product_id: str | None = None) -> dict:
    key = f'{opportunity_type}:{entity_type}:{entity_id}:{product_id or ""}'
    return {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'entity_label': label,
        'title': title,
        'description': description,
        'action': action,
        'evidence': evidence,
        'partner_id': partner_id,
        'customer_id': customer_id,
        'product_id': product_id,
        'dedupe_key': key,
    }


def _history_signals(db: Session, customer: Customer, entity_type: str, partner_id: str | None, now: datetime) -> tuple[list[dict], list[dict], bool]:
    alerts: list[dict] = []
    opportunities: list[dict] = []
    summary = customer_history_summary(db, customer.id)
    if summary['status'] == 'insufficient_data':
        return alerts, opportunities, False

    history = partner_history_summary(db, partner_id) if partner_id else summary
    estimate = partner_replenishment_estimate(db, partner_id) if partner_id else customer_replenishment_estimate(db, customer.id)
    if estimate['status'] == 'ready':
        last_purchase = _utc(history['last_purchase'])
        interval = float(history['frequency']['average_days'])
        days_since = (now.date() - last_purchase.date()).days
        expected_days = round(interval)
        days_until = expected_days - days_since
        if days_until <= REPLENISHMENT_EARLY_WINDOW_DAYS:
            is_overdue = days_until < 0
            label = customer.name
            overdue_ratio = days_since / interval if interval > 0 else 0
            priority = 'high' if is_overdue and overdue_ratio >= 1.5 else 'medium'
            alert_type = f'{entity_type}_purchase_overdue' if is_overdue else f'{entity_type}_replenishment_window'
            title = 'Compra fora da frequência habitual' if is_overdue else 'Janela habitual de compra próxima'
            reason = f'Última compra em {last_purchase.date().isoformat()}; intervalo médio observado de {expected_days} dias.'
            description = f'{label} está há {days_since} dias sem comprar; o intervalo histórico médio é de {expected_days} dias.'
            alerts.append(_alert(alert_type, entity_type, customer.id if entity_type == 'customer' else partner_id or customer.id, label, title, description, reason, priority, partner_id=partner_id))
            opportunities.append(_opportunity(
                f'{entity_type}_replenishment', entity_type, customer.id if entity_type == 'customer' else partner_id or customer.id,
                label, 'Verificar reposição com o cliente', description,
                'Consultar o cliente sobre a necessidade de reposição; nenhuma compra será criada automaticamente.',
                {'orders': history['orders'], 'last_purchase': last_purchase.isoformat(), 'average_interval_days': expected_days, 'days_since_last_purchase': days_since},
                partner_id=partner_id, customer_id=customer.id,
            ))

        product_estimates = estimate.get('product_estimates', {})
        for product_id, product_estimate in product_estimates.items():
            product_last = _utc(product_estimate['last_purchase'])
            product_interval = round(float(product_estimate['average_interval_days']))
            product_days_since = (now.date() - product_last.date()).days
            product_days_until = product_interval - product_days_since
            if product_days_until > REPLENISHMENT_EARLY_WINDOW_DAYS:
                continue
            product = db.get(Product, product_id)
            product_name = product.name if product else product_estimate.get('product_name', 'Produto')
            overdue = product_days_until < 0
            description = f'{product_name}: última compra há {product_days_since} dias; intervalo médio observado de {product_interval} dias.'
            alerts.append(_alert(
                f'{entity_type}_product_replenishment', entity_type,
                customer.id if entity_type == 'customer' else partner_id or customer.id,
                customer.name, 'Produto recorrente próximo da reposição', description,
                f'Quantidade média registrada por compra: {product_estimate["average_quantity_per_purchase"]}; intervalo médio observado: {product_interval} dias.',
                'high' if overdue and product_days_since >= product_interval * 1.5 else 'medium',
                partner_id=partner_id, product_id=product_id,
            ))
            opportunities.append(_opportunity(
                f'{entity_type}_product_replenishment', entity_type,
                customer.id if entity_type == 'customer' else partner_id or customer.id,
                customer.name, f'Avaliar reposição de {product_name}', description,
                'Validar com o cliente se o produto continua necessário e avaliar a disponibilidade em estoque.',
                {'product_id': product_id, 'last_purchase': product_last.isoformat(), 'average_interval_days': product_interval, 'average_quantity_per_purchase': str(product_estimate['average_quantity_per_purchase'])},
                partner_id=partner_id, customer_id=customer.id, product_id=product_id,
            ))

    orders = list(db.scalars(select(Order).where(Order.customer_id == customer.id, Order.status.in_(REALIZED_ORDER_STATUSES)).order_by(Order.ordered_at.asc())))
    intervals = [(current.ordered_at.date() - previous.ordered_at.date()).days for previous, current in zip(orders, orders[1:])]
    if len(intervals) >= 3:
        previous_average = mean(intervals[:-1])
        latest_interval = intervals[-1]
        entity_id = customer.id if entity_type == 'customer' else partner_id or customer.id
        evidence = {'previous_average_interval_days': round(previous_average, 2), 'latest_interval_days': latest_interval, 'orders_compared': len(intervals) + 1}
        if previous_average > 0 and latest_interval >= previous_average * 1.5:
            priority = 'high' if latest_interval >= previous_average * 2 else 'medium'
            description = f'O intervalo mais recente foi de {latest_interval} dias, contra média anterior de {previous_average:.1f} dias.'
            alerts.append(_alert(f'{entity_type}_frequency_drop', entity_type, entity_id, customer.name, 'Queda na frequência de compra', description, 'Comparação do último intervalo com a média dos intervalos anteriores; diferença de pelo menos 50%.', priority, partner_id=partner_id))
            opportunities.append(_opportunity(f'{entity_type}_frequency_drop', entity_type, entity_id, customer.name, 'Investigar queda na frequência', description, 'Revisar o relacionamento e confirmar se houve mudança na necessidade do cliente.', evidence, partner_id=partner_id, customer_id=customer.id))
        elif previous_average > 0 and latest_interval <= previous_average * 0.5:
            description = f'O intervalo mais recente foi de {latest_interval} dias, contra média anterior de {previous_average:.1f} dias.'
            opportunities.append(_opportunity(f'{entity_type}_frequency_increase', entity_type, entity_id, customer.name, 'Frequência de compra aumentou', description, 'Verificar se a mudança altera o planejamento de atendimento ou abastecimento.', evidence, partner_id=partner_id, customer_id=customer.id))

    if entity_type == 'partner' and partner_id:
        purchase_quantities: dict[str, dict[str, Decimal]] = {}
        product_rows = db.execute(
            select(OrderItem, Order.ordered_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.customer_id == customer.id, Order.status.in_(REALIZED_ORDER_STATUSES))
        ).all()
        for item, _ in product_rows:
            quantities = purchase_quantities.setdefault(item.product_id, {})
            quantities[item.order_id] = quantities.get(item.order_id, Decimal('0')) + item.quantity

        order_position = {order.id: index for index, order in enumerate(orders)}
        for product_id, quantities in purchase_quantities.items():
            product_purchases = sorted(quantities.items(), key=lambda entry: order_position[entry[0]])
            if len(product_purchases) < 3:
                continue
            previous_average_quantity = mean(quantity for _, quantity in product_purchases[:-1])
            latest_quantity = product_purchases[-1][1]
            if previous_average_quantity <= 0:
                continue
            if latest_quantity >= previous_average_quantity * Decimal('1.5'):
                change_direction = 'aumentou'
                significant_change = True
                high_priority = latest_quantity >= previous_average_quantity * 2
            elif latest_quantity <= previous_average_quantity * Decimal('0.5'):
                change_direction = 'diminuiu'
                significant_change = True
                high_priority = latest_quantity <= previous_average_quantity * Decimal('0.5')
            else:
                continue
            product = db.get(Product, product_id)
            product_name = product.name if product else 'Produto'
            description = f'A quantidade mais recente de {product_name} {change_direction} para {latest_quantity}; a média das compras anteriores foi {previous_average_quantity}.'
            evidence = {
                'product_id': product_id,
                'previous_average_quantity': str(previous_average_quantity),
                'latest_quantity': str(latest_quantity),
                'previous_purchases': len(product_purchases) - 1,
            }
            alerts.append(_alert(
                'partner_purchase_pattern_change', 'partner', partner_id, customer.name,
                'Alteração no padrão de compra do parceiro', description,
                'Comparação da última quantidade por produto com a média das compras anteriores; variação de pelo menos 50%.',
                'high' if high_priority else 'medium', partner_id=partner_id, product_id=product_id,
            ))
            opportunities.append(_opportunity(
                'partner_purchase_pattern_change', 'partner', partner_id, customer.name,
                f'Revisar mudança de quantidade: {product_name}', description,
                'Confirmar se a mudança de quantidade representa uma necessidade recorrente ou pontual antes de ajustar o atendimento.',
                evidence, partner_id=partner_id, customer_id=customer.id, product_id=product_id,
            ))
    return alerts, opportunities, True


def build_operational_signals(db: Session, scopes: set[str], now: datetime | None = None) -> tuple[list[dict], list[dict], bool]:
    current = _utc(now or datetime.now(timezone.utc))
    alerts: list[dict] = []
    opportunities: list[dict] = []
    history_available = False

    if 'inventory' in scopes:
        rows = db.execute(select(Product, InventoryBalance).outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id).where(Product.is_active.is_(True)).order_by(Product.name)).all()
        for product, balance in rows:
            quantity = balance.quantity if balance else 0
            if quantity <= 0:
                alert_type, title, priority = 'stock_zero', 'Produto sem estoque', 'high'
            elif product.minimum_stock > 0 and quantity < product.minimum_stock:
                alert_type, title, priority = 'stock_below_minimum', 'Estoque abaixo do mínimo', 'medium'
            else:
                continue
            reason = f'Estoque atual: {quantity}; estoque mínimo cadastrado: {product.minimum_stock}.'
            description = f'{product.name} está com {quantity} {product.unit}; a reposição precisa ser avaliada.'
            alerts.append(_alert(alert_type, 'inventory_product', product.id, product.name, title, description, reason, priority, product_id=product.id))
            opportunities.append(_opportunity('stock_replenishment', 'inventory_product', product.id, product.name, f'Avaliar reposição de {product.name}', description, 'Conferir saldo físico e necessidade de compra antes de registrar reposição.', {'quantity': str(quantity), 'minimum_stock': str(product.minimum_stock), 'unit': product.unit}, product_id=product.id))

    if 'finance' in scopes:
        finance_rows = (
            (AccountPayable, Supplier, 'payable', 'Conta a pagar', 'supplier_id'),
            (AccountReceivable, Customer, 'receivable', 'Conta a receber', 'customer_id'),
        )
        for model, related_model, entity_type, label, relation_key in finance_rows:
            for account in db.scalars(select(model).where(model.status.in_(['PENDING', 'OVERDUE'])).order_by(model.due_at)):
                due_at = _utc(account.due_at)
                days_until = (due_at.date() - current.date()).days
                if days_until < 0:
                    due_state, priority = 'overdue', 'high'
                    title = f'{label} vencida'
                    due_text = f'venceu em {due_at.date().isoformat()}'
                elif days_until <= ALERT_WINDOW_DAYS:
                    due_state, priority = 'due_soon', 'medium'
                    title = f'{label} próxima do vencimento'
                    due_text = f'vence em {due_at.date().isoformat()}'
                else:
                    continue
                related = db.get(related_model, getattr(account, relation_key))
                related_label = related.name if related else account.description
                description = f'{account.description} ({related_label}), no valor de R$ {account.amount}, {due_text}.'
                alerts.append(_alert(f'{entity_type}_{due_state}', entity_type, account.id, related_label, title, description, f'Vencimento registrado: {due_at.isoformat()}; status atual: {account.status}.', priority))

    if 'customers' in scopes or 'partners' in scopes:
        active_partners = list(db.scalars(select(Partner).where(Partner.status == 'ACTIVE').order_by(Partner.id))) if 'partners' in scopes else []
        partner_by_customer = {partner.customer_id: partner for partner in active_partners}
        partner_customers = set(partner_by_customer)
        if 'customers' in scopes:
            for customer in db.scalars(select(Customer).where(Customer.status == 'ACTIVE').order_by(Customer.id)):
                if customer.id in partner_customers:
                    continue
                found_alerts, found_opportunities, has_history = _history_signals(db, customer, 'customer', None, current)
                alerts.extend(found_alerts)
                opportunities.extend(found_opportunities)
                history_available = history_available or has_history
        for partner in active_partners:
            customer = db.get(Customer, partner.customer_id)
            if customer is None:
                continue
            found_alerts, found_opportunities, has_history = _history_signals(db, customer, 'partner', partner.id, current)
            alerts.extend(found_alerts)
            opportunities.extend(found_opportunities)
            history_available = history_available or has_history

    if 'inventory' in scopes:
        recent_start = current - timedelta(days=OPPORTUNITY_COMPARISON_DAYS)
        previous_start = current - timedelta(days=2 * OPPORTUNITY_COMPARISON_DAYS)
        rows = db.execute(
            select(OrderItem.product_id, OrderItem.quantity, Order.ordered_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status.in_(REALIZED_ORDER_STATUSES), Order.ordered_at >= previous_start, Order.ordered_at <= current)
        ).all()
        quantities: dict[str, list] = {}
        for product_id, quantity, ordered_at in rows:
            periods = quantities.setdefault(product_id, [0, 0])
            if _utc(ordered_at) >= recent_start:
                periods[1] += quantity
            else:
                periods[0] += quantity
        for product_id, (previous_quantity, recent_quantity) in quantities.items():
            if previous_quantity <= 0 or recent_quantity <= previous_quantity:
                continue
            product = db.get(Product, product_id)
            if product is None:
                continue
            description = f'{product.name}: {recent_quantity} unidades nos últimos {OPPORTUNITY_COMPARISON_DAYS} dias; {previous_quantity} no período anterior equivalente.'
            opportunities.append(_opportunity('product_demand_increase', 'inventory_product', product.id, product.name, f'Aumento de demanda: {product.name}', description, 'Verificar o ritmo de saída e revisar o planejamento de reposição.', {'recent_period_days': OPPORTUNITY_COMPARISON_DAYS, 'recent_quantity': str(recent_quantity), 'previous_quantity': str(previous_quantity)}, product_id=product.id))

    return alerts, opportunities, history_available


def refresh_operational_signals(db: Session, scopes: set[str], now: datetime | None = None) -> tuple[bool, list[str]]:
    current = _utc(now or datetime.now(timezone.utc))
    alerts, opportunities, history_available = build_operational_signals(db, scopes, current)
    active_entities = {entity for entity, scope in ENTITY_SCOPE.items() if scope in scopes}
    alert_keys = set()
    for values in alerts:
        alert_keys.add(values['dedupe_key'])
        record = db.scalar(select(PartnerAlert).where(PartnerAlert.dedupe_key == values['dedupe_key']))
        if record is None:
            record = PartnerAlert(**values, message=values['description'], detected_at=current)
            db.add(record)
        else:
            was_inactive = not record.is_active
            for key, value in values.items():
                setattr(record, key, value)
            record.message = values['description']
            record.detected_at = current
            record.is_active = True
            if was_inactive:
                record.status = 'OPEN'
                record.resolved_at = None

    opportunity_keys = set()
    for values in opportunities:
        opportunity_keys.add(values['dedupe_key'])
        record = db.scalar(select(PartnerOpportunity).where(PartnerOpportunity.dedupe_key == values['dedupe_key']))
        if record is None:
            db.add(PartnerOpportunity(**values))
        else:
            was_inactive = not record.is_active
            for key, value in values.items():
                setattr(record, key, value)
            record.is_active = True
            if was_inactive:
                record.status = 'OPEN'

    for record in db.scalars(select(PartnerAlert).where(PartnerAlert.dedupe_key.is_not(None), PartnerAlert.entity_type.in_(active_entities))):
        if record.dedupe_key not in alert_keys and record.is_active:
            record.is_active = False
            if record.status == 'OPEN':
                record.status = 'RESOLVED'
                record.resolved_at = current
    for record in db.scalars(select(PartnerOpportunity).where(PartnerOpportunity.dedupe_key.is_not(None), PartnerOpportunity.entity_type.in_(active_entities))):
        if record.dedupe_key not in opportunity_keys and record.is_active:
            record.is_active = False
            if record.status == 'OPEN':
                record.status = 'EXPIRED'
    db.commit()
    return history_available, sorted(active_entities)