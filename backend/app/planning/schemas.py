from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal['commercial', 'customers', 'suppliers', 'purchases', 'inventory', 'finance', 'operational', 'strategic', 'other']
Priority = Literal['low', 'medium', 'high', 'urgent']
PlanStatus = Literal['draft', 'not_started', 'in_progress', 'on_hold', 'completed', 'cancelled']
TaskStatus = Literal['pending', 'in_progress', 'completed']
GoalStatus = Literal['in_progress', 'completed', 'cancelled']
EntityType = Literal['customer', 'supplier', 'product', 'purchase', 'order', 'payable', 'receivable']


class EntityLinkInput(BaseModel):
    entity_type: EntityType
    entity_id: str = Field(min_length=1, max_length=36)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    stage: str | None = Field(default=None, max_length=80)
    status: TaskStatus = 'pending'
    priority: Priority = 'medium'
    due_date: date | None = None
    assignee_id: str | None = None
    sort_order: int = Field(default=0, ge=0)
    observations: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    stage: str | None = Field(default=None, max_length=80)
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    assignee_id: str | None = None
    sort_order: int | None = Field(default=None, ge=0)
    observations: str | None = None


class PlanCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str | None = None
    category: Category
    expected_outcome: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: PlanStatus = 'not_started'
    priority: Priority = 'medium'
    observations: str | None = None
    tasks: list[TaskInput] = Field(default_factory=list, max_length=100)
    links: list[EntityLinkInput] = Field(default_factory=list, max_length=50)


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    category: Category | None = None
    expected_outcome: str | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: PlanStatus | None = None
    priority: Priority | None = None
    observations: str | None = None
    archived: bool | None = None
    links: list[EntityLinkInput] | None = Field(default=None, max_length=50)


class GoalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    category: Category
    initial_value: Decimal | None = Field(default=None, ge=0)
    target_value: Decimal = Field(ge=0)
    current_value: Decimal = Field(default=0, ge=0)
    unit: str = Field(min_length=1, max_length=40)
    start_date: date | None = None
    due_date: date | None = None
    status: GoalStatus = 'in_progress'
    planning_id: str | None = None


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    category: Category | None = None
    initial_value: Decimal | None = Field(default=None, ge=0)
    target_value: Decimal | None = Field(default=None, ge=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    start_date: date | None = None
    due_date: date | None = None
    status: GoalStatus | None = None
    planning_id: str | None = None
