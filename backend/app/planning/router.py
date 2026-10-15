from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import AccountPayable, AccountReceivable, Customer, InventoryBalance, Order, Planning, PlanningEntityLink, PlanningGoal, PlanningOpportunityDismissal, PlanningTask, Product, Purchase, Supplier, User
from app.database.session import get_db
from app.planning.schemas import GoalCreate, GoalUpdate, PlanCreate, PlanUpdate, TaskInput, TaskUpdate

router = APIRouter(prefix='/planning', tags=['planning'])
ACCESS = 'planning:manage'
CATEGORIES = ('commercial', 'customers', 'suppliers', 'purchases', 'inventory', 'finance', 'operational', 'strategic', 'other')
STATUSES = ('draft', 'not_started', 'in_progress', 'on_hold', 'completed', 'cancelled')
PRIORITIES = ('low', 'medium', 'high', 'urgent')
ENTITY_FIELDS: dict[str, tuple[str, Any, str]] = {
    'customer': ('customer_id', Customer, 'name'), 'supplier': ('supplier_id', Supplier, 'name'),
    'product': ('product_id', Product, 'name'), 'purchase': ('purchase_id', Purchase, None),
    'order': ('order_id', Order, None), 'payable': ('payable_id', AccountPayable, 'description'),
    'receivable': ('receivable_id', AccountReceivable, 'description'),
}
TEMPLATES = [
    {'key': 'prospecting', 'title': 'Prospecção de novos clientes', 'description': 'Organizar etapas para prospectar e acompanhar potenciais clientes.', 'category': 'commercial', 'tasks': ['Definir perfil de cliente desejado', 'Preparar lista de contatos', 'Realizar primeiro contato', 'Registrar próximos passos']},
    {'key': 'customer_followup', 'title': 'Acompanhamento de clientes', 'description': 'Planejar um acompanhamento comercial de clientes cadastrados.', 'category': 'customers', 'tasks': ['Revisar histórico de pedidos', 'Definir pauta do contato', 'Realizar contato', 'Registrar retorno e próxima ação']},
    {'key': 'inactive_customers', 'title': 'Recuperação de clientes', 'description': 'Estruturar uma ação de recuperação. A identificação dos clientes deve ser feita pelo administrador.', 'category': 'customers', 'tasks': ['Selecionar clientes com critério definido', 'Revisar histórico e contexto', 'Preparar abordagem', 'Registrar resultado do acompanhamento']},
    {'key': 'monthly_purchases', 'title': 'Planejamento de compras mensais', 'description': 'Organizar a avaliação de compras para o período.', 'category': 'purchases', 'tasks': ['Revisar necessidades de estoque', 'Consultar fornecedores e condições', 'Comparar cotações', 'Aprovar e registrar a compra no fluxo de compras']},
    {'key': 'stock_replenishment', 'title': 'Reposição de estoque', 'description': 'Planejar a avaliação de reposição dos produtos vinculados.', 'category': 'inventory', 'tasks': ['Conferir saldo e estoque mínimo', 'Validar necessidade de reposição', 'Consultar fornecedor', 'Registrar compra aprovada no fluxo próprio']},
    {'key': 'supplier_negotiation', 'title': 'Negociação com fornecedores', 'description': 'Organizar os pontos e próximos passos de uma negociação.', 'category': 'suppliers', 'tasks': ['Revisar condições atuais', 'Preparar condições desejadas', 'Realizar negociação', 'Registrar condições acordadas']},
    {'key': 'product_launch', 'title': 'Lançamento de novos produtos', 'description': 'Coordenar atividades internas de um lançamento.', 'category': 'strategic', 'tasks': ['Definir público e posicionamento', 'Confirmar cadastro e preço', 'Preparar materiais comerciais', 'Revisar disponibilidade e início das vendas']},
    {'key': 'monthly_commercial', 'title': 'Planejamento comercial mensal', 'description': 'Definir atividades comerciais do mês e acompanhar suas etapas.', 'category': 'commercial', 'tasks': ['Revisar resultados registrados', 'Definir objetivos do período', 'Organizar ações por responsável', 'Revisar andamento no fim do período']},
    {'key': 'expense_reduction', 'title': 'Redução de despesas', 'description': 'Estruturar uma revisão baseada em registros financeiros existentes.', 'category': 'finance', 'tasks': ['Revisar despesas registradas', 'Identificar itens para análise', 'Avaliar alternativas', 'Registrar decisões e responsáveis']},
    {'key': 'weekly_company', 'title': 'Planejamento semanal da empresa', 'description': 'Organizar prioridades e prazos da semana.', 'category': 'operational', 'tasks': ['Revisar tarefas e prazos abertos', 'Definir prioridades da semana', 'Acompanhar ações prioritárias', 'Fechar pendências e registrar próximos passos']},
]


def validate_dates(start_date: date | None, due_date: date | None, entity: str):
    if start_date and due_date and due_date < start_date:
        raise HTTPException(status_code=422, detail=f'{entity} due date cannot be earlier than its start date.')


def reference_name(db: Session, entity_type: str, entity_id: str) -> str:
    field, model, label_field = ENTITY_FIELDS[entity_type]
    record = db.get(model, entity_id)
    if not record:
        raise HTTPException(status_code=422, detail=f'The selected {entity_type} does not exist.')
    if label_field:
        return str(getattr(record, label_field))
    return f'{entity_type.title()} · {entity_id[:8]}'


def add_links(db: Session, planning: Planning, links):
    seen: set[tuple[str, str]] = set()
    for link in links:
        key = (link.entity_type, link.entity_id)
        if key in seen:
            continue
        seen.add(key)
        field, _, _ = ENTITY_FIELDS[link.entity_type]
        reference_name(db, link.entity_type, link.entity_id)
        db.add(PlanningEntityLink(planning_id=planning.id, **{field: link.entity_id}))


def link_record(db: Session, link: PlanningEntityLink) -> dict:
    for entity_type, (field, _, _) in ENTITY_FIELDS.items():
        entity_id = getattr(link, field)
        if entity_id:
            return {'id': link.id, 'entity_type': entity_type, 'entity_id': entity_id, 'label': reference_name(db, entity_type, entity_id)}
    return {'id': link.id, 'entity_type': 'unknown', 'entity_id': '', 'label': 'Referência indisponível'}


def task_record(db: Session, task: PlanningTask) -> dict:
    assignee = db.get(User, task.assignee_id) if task.assignee_id else None
    return {'id': task.id, 'planning_id': task.planning_id, 'title': task.title, 'description': task.description, 'stage': task.stage, 'status': task.status, 'priority': task.priority, 'due_date': task.due_date, 'assignee_id': task.assignee_id, 'assignee_name': assignee.name if assignee else None, 'sort_order': task.sort_order, 'observations': task.observations, 'completed_at': task.completed_at, 'created_at': task.created_at, 'updated_at': task.updated_at}


def goal_record(goal: PlanningGoal) -> dict:
    target = float(goal.target_value)
    current = float(goal.current_value)
    return {'id': goal.id, 'planning_id': goal.planning_id, 'name': goal.name, 'description': goal.description, 'category': goal.category, 'initial_value': float(goal.initial_value) if goal.initial_value is not None else None, 'target_value': target, 'current_value': current, 'unit': goal.unit, 'start_date': goal.start_date, 'due_date': goal.due_date, 'status': goal.status, 'progress_percent': min(100, max(0, current / target * 100)) if target > 0 else 0, 'created_at': goal.created_at, 'updated_at': goal.updated_at}


def plan_record(db: Session, plan: Planning) -> dict:
    tasks = list(db.scalars(select(PlanningTask).where(PlanningTask.planning_id == plan.id).order_by(PlanningTask.sort_order, PlanningTask.created_at)))
    goals = list(db.scalars(select(PlanningGoal).where(PlanningGoal.planning_id == plan.id).order_by(PlanningGoal.due_date, PlanningGoal.name)))
    links = list(db.scalars(select(PlanningEntityLink).where(PlanningEntityLink.planning_id == plan.id).order_by(PlanningEntityLink.id)))
    completed = sum(task.status == 'completed' for task in tasks)
    progress = round(completed / len(tasks) * 100, 1) if tasks else 0
    return {'id': plan.id, 'title': plan.title, 'description': plan.description, 'category': plan.category, 'expected_outcome': plan.expected_outcome, 'start_date': plan.start_date, 'due_date': plan.due_date, 'status': plan.status, 'priority': plan.priority, 'observations': plan.observations, 'archived': plan.archived_at is not None, 'archived_at': plan.archived_at, 'progress_percent': progress, 'task_count': len(tasks), 'completed_task_count': completed, 'tasks': [task_record(db, task) for task in tasks], 'goals': [goal_record(goal) for goal in goals], 'links': [link_record(db, link) for link in links], 'created_at': plan.created_at, 'updated_at': plan.updated_at}


def get_plan(db: Session, plan_id: str) -> Planning:
    plan = db.get(Planning, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail='Planning not found.')
    return plan


def assign_task(db: Session, plan: Planning, task: TaskInput) -> PlanningTask:
    validate_dates(None, task.due_date, 'Task')
    if task.assignee_id and not db.get(User, task.assignee_id):
        raise HTTPException(status_code=422, detail='The selected assignee does not exist.')
    record = PlanningTask(planning_id=plan.id, **task.model_dump(), completed_at=datetime.now(timezone.utc) if task.status == 'completed' else None)
    db.add(record)
    return record


@router.get('/templates')
def get_templates(_: User = Depends(require_permission(ACCESS))):
    return TEMPLATES


@router.get('/opportunities')
def get_opportunities(_: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    rows = db.execute(select(Product, InventoryBalance).outerjoin(InventoryBalance, InventoryBalance.product_id == Product.id).where(Product.is_active.is_(True), Product.minimum_stock > 0).order_by(Product.name))
    dismissed = set(db.scalars(select(PlanningOpportunityDismissal.opportunity_key)))
    found = []
    today = date.today()
    for product, balance in rows:
        quantity = balance.quantity if balance else Decimal('0')
        if quantity < product.minimum_stock and f'low_stock:{product.id}' not in dismissed:
            found.append({'id': f'low_stock:{product.id}', 'title': f'Avaliar reposição: {product.name}', 'reason': f'O saldo registrado é {quantity} {product.unit}, abaixo do mínimo de {product.minimum_stock} {product.unit}. Confira o estoque físico antes de decidir.', 'category': 'inventory', 'identified_at': datetime.now(timezone.utc), 'entity_type': 'product', 'entity_id': product.id, 'entity_label': product.name})
    return found


@router.post('/opportunities/{product_id}/dismiss', status_code=status.HTTP_204_NO_CONTENT)
def dismiss_stock_opportunity(product_id: str, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    opportunity_key = f'low_stock:{product.id}'
    existing = db.scalar(select(PlanningOpportunityDismissal).where(PlanningOpportunityDismissal.opportunity_key == opportunity_key))
    if not existing:
        db.add(PlanningOpportunityDismissal(opportunity_key=opportunity_key, product_id=product.id, dismissed_by=actor.id))
        audit(db, actor.id, 'planning.opportunity.dismiss', 'product', product.id)
        db.commit()


@router.get('/goals')
def list_goals(planning_id: str | None = None, _: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    statement = select(PlanningGoal).order_by(PlanningGoal.due_date, PlanningGoal.name)
    if planning_id:
        statement = statement.where(PlanningGoal.planning_id == planning_id)
    return [goal_record(goal) for goal in db.scalars(statement)]


@router.post('/goals', status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    validate_dates(payload.start_date, payload.due_date, 'Goal')
    if payload.planning_id:
        get_plan(db, payload.planning_id)
    if payload.status == 'completed' and payload.target_value > 0 and payload.current_value < payload.target_value:
        raise HTTPException(status_code=422, detail='A goal can only be completed after reaching its target value.')
    goal = PlanningGoal(**payload.model_dump())
    db.add(goal)
    db.flush()
    audit(db, actor.id, 'planning.goal.create', 'planning_goal', goal.id)
    db.commit()
    db.refresh(goal)
    return goal_record(goal)


@router.patch('/goals/{goal_id}')
def update_goal(goal_id: str, payload: GoalUpdate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    goal = db.get(PlanningGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail='Goal not found.')
    changes = payload.model_dump(exclude_unset=True)
    start_date = changes.get('start_date', goal.start_date)
    due_date = changes.get('due_date', goal.due_date)
    validate_dates(start_date, due_date, 'Goal')
    if changes.get('planning_id'):
        get_plan(db, changes['planning_id'])
    target = changes.get('target_value', goal.target_value)
    current = changes.get('current_value', goal.current_value)
    if changes.get('status', goal.status) == 'completed' and target > 0 and current < target:
        raise HTTPException(status_code=422, detail='A goal can only be completed after reaching its target value.')
    for key, value in changes.items():
        setattr(goal, key, value)
    audit(db, actor.id, 'planning.goal.update', 'planning_goal', goal.id)
    db.commit()
    db.refresh(goal)
    return goal_record(goal)


@router.get('')
def list_plannings(
    status_filter: str | None = Query(default=None, alias='status'),
    category: str | None = None,
    priority: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    search: str | None = Query(default=None, max_length=180),
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_permission(ACCESS)),
    db: Session = Depends(get_db),
):
    statement = select(Planning)
    if not include_archived:
        statement = statement.where(Planning.archived_at.is_(None))
    if status_filter:
        if status_filter not in STATUSES:
            raise HTTPException(status_code=422, detail='Invalid planning status.')
        statement = statement.where(Planning.status == status_filter)
    if category:
        if category not in CATEGORIES:
            raise HTTPException(status_code=422, detail='Invalid planning category.')
        statement = statement.where(Planning.category == category)
    if priority:
        if priority not in PRIORITIES:
            raise HTTPException(status_code=422, detail='Invalid planning priority.')
        statement = statement.where(Planning.priority == priority)
    if due_from:
        statement = statement.where(Planning.due_date >= due_from)
    if due_to:
        statement = statement.where(Planning.due_date <= due_to)
    if search:
        statement = statement.where(Planning.title.ilike(f'%{search.strip()}%'))
    statement = statement.order_by(Planning.due_date.is_(None), Planning.due_date, Planning.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return [plan_record(db, plan) for plan in db.scalars(statement)]


@router.post('', status_code=status.HTTP_201_CREATED)
def create_planning(payload: PlanCreate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    validate_dates(payload.start_date, payload.due_date, 'Planning')
    plan = Planning(**payload.model_dump(exclude={'tasks', 'links'}), created_by=actor.id)
    db.add(plan)
    db.flush()
    for task in payload.tasks:
        assign_task(db, plan, task)
    add_links(db, plan, payload.links)
    audit(db, actor.id, 'planning.create', 'planning', plan.id)
    db.commit()
    db.refresh(plan)
    return plan_record(db, plan)


@router.get('/{plan_id}')
def read_planning(plan_id: str, _: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    return plan_record(db, get_plan(db, plan_id))


@router.patch('/{plan_id}')
def update_planning(plan_id: str, payload: PlanUpdate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    plan = get_plan(db, plan_id)
    changes = payload.model_dump(exclude_unset=True)
    archived = changes.pop('archived', None)
    links = changes.pop('links', None)
    validate_dates(changes.get('start_date', plan.start_date), changes.get('due_date', plan.due_date), 'Planning')
    for key, value in changes.items():
        setattr(plan, key, value)
    if archived is not None:
        plan.archived_at = datetime.now(timezone.utc) if archived else None
    if links is not None:
        db.query(PlanningEntityLink).filter(PlanningEntityLink.planning_id == plan.id).delete(synchronize_session=False)
        add_links(db, plan, links)
    audit(db, actor.id, 'planning.update', 'planning', plan.id)
    db.commit()
    db.refresh(plan)
    return plan_record(db, plan)


@router.post('/{plan_id}/tasks', status_code=status.HTTP_201_CREATED)
def create_task(plan_id: str, payload: TaskInput, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    plan = get_plan(db, plan_id)
    task = assign_task(db, plan, payload)
    db.flush()
    audit(db, actor.id, 'planning.task.create', 'planning_task', task.id)
    db.commit()
    db.refresh(task)
    return task_record(db, task)


@router.patch('/tasks/{task_id}')
def update_task(task_id: str, payload: TaskUpdate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    task = db.get(PlanningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found.')
    changes = payload.model_dump(exclude_unset=True)
    if 'due_date' in changes:
        validate_dates(None, changes['due_date'], 'Task')
    if 'assignee_id' in changes and changes['assignee_id'] and not db.get(User, changes['assignee_id']):
        raise HTTPException(status_code=422, detail='The selected assignee does not exist.')
    if changes.get('status') == 'completed' and task.status != 'completed':
        task.completed_at = datetime.now(timezone.utc)
    elif changes.get('status') and changes['status'] != 'completed':
        task.completed_at = None
    for key, value in changes.items():
        setattr(task, key, value)
    audit(db, actor.id, 'planning.task.update', 'planning_task', task.id)
    db.commit()
    db.refresh(task)
    return task_record(db, task)


@router.delete('/tasks/{task_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    task = db.get(PlanningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found.')
    audit(db, actor.id, 'planning.task.delete', 'planning_task', task.id)
    db.delete(task)
    db.commit()


@router.post('/{plan_id}/goals', status_code=status.HTTP_201_CREATED)
def create_planning_goal(plan_id: str, payload: GoalCreate, actor: User = Depends(require_permission(ACCESS)), db: Session = Depends(get_db)):
    get_plan(db, plan_id)
    if payload.planning_id and payload.planning_id != plan_id:
        raise HTTPException(status_code=422, detail='Goal planning ID does not match the URL.')
    return create_goal(payload.model_copy(update={'planning_id': plan_id}), actor, db)
