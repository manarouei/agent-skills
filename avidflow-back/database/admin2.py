import bcrypt
from sqlalchemy import select
from database.config import get_async_engine, get_async_session
# from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from fastapi import Request, Response
from fastapi.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from .models import (
    AdminUser,
    User,
    PhoneCode,
    WhiteListPhones,
    Workflow,
    Credential,
    CredentialType,
    DynamicNode,
    Plan,
    Order,
    Transaction,
    Subscription,
    Option
)
from config import settings

from starlette_admin.auth import AuthProvider
from starlette_admin.exceptions import LoginFailed
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette_admin.fields import FileField, TextAreaField, JSONField



class CustomAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        query = select(AdminUser).where(AdminUser.username==username, AdminUser.is_superuser==True)
        async for db in get_async_session():
            user = await db.execute(query)
            user = user.scalar_one_or_none()
            if not user or not bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
                raise LoginFailed("Invalid username or password")

        request.session.update({"username": username})

        return response
    
    async def is_authenticated(self, request) -> bool:
        query = select(AdminUser).where(AdminUser.username==request.session.get('username'), AdminUser.is_superuser==True)
        async for db in get_async_session():
            user = await db.execute(query)
            user = user.scalar_one_or_none()
            if user:
                """
                Save current `user` object in the request state. Can be used later
                to restrict access to connected user.
                """
                request.session['username'] = user.username
                return True

        return False
    
    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response
    

class UserView(ModelView):
    fields = ['id', 'email', 'username', 'first_name', 'last_name', 'hashed_password', 'is_active', 'is_staff', 'is_superuser', 'last_login', 'created_at', 'updated_at', 'workflows', 'credentials', 'orders', 'subscriptions']
    exclude_fields_from_list = ['workflows', 'credentials', 'hashed_password', 'orders', 'subscriptions', 'created_at', 'updated_at']
    exclude_fields_from_detail = ['hashed_password', 'workflows', 'subscriptions', 'orders', 'credentials']
    exclude_fields_from_create = ['id', 'created_at', 'updated_at', 'hashed_password', 'workflows', 'subscriptions', 'orders', 'credentials']
    exclude_fields_from_edit = ['id', 'created_at', 'updated_at', 'hashed_password', 'workflows', 'subscriptions', 'orders', 'credentials']


class DynamicNodeView(ModelView):
    fields = ['id', 'type', 'version', 'name', 'description', 'properties', 'is_active', 'category', FileField('icon', 'icon'), 'is_start', 'is_end', 'is_webhook', 'is_schedule']
    exclude_fields_from_list = ['properties', 'icon', 'description']


class WorkflowView(ModelView):
    fields = ['id', 'name', 'description', 'nodes', 'connections', 'settings', 'pin_data', 'trigger_count', 'active', 'created_at', 'updated_at', 'user']
    exclude_fields_from_list = ['nodes', 'connections', 'settings', 'pin_data', 'user']


class OptionView(ModelView):
    fields = ['id', 'name', 'value']


class PlanView(ModelView):
    """General subscription plans"""
    fields = ['id', 'title', 'description', 'nodes_limit', 'price', 'duration_days', 'is_active', 'created_at', 'updated_at']
    exclude_fields_from_list = ['description', 'updated_at']
    exclude_fields_from_create = ['id', 'created_at', 'updated_at']
    exclude_fields_from_edit = ['id', 'created_at', 'updated_at']


class OrderView(ModelView):
    """User's actual subscriptions"""
    fields = ['id', 'user_id', 'plan_snapshot', 'amount', 'status', 'created_at', 'updated_at', 'user', 'transaction', 'tax']
    exclude_fields_from_list = ['plan_snapshot', 'created_at', 'updated_at']
    exclude_fields_from_create = ['id', 'created_at', 'updated_at']
    exclude_fields_from_edit = ['id', 'created_at', 'updated_at']


class TransactionView(ModelView):
    fields = ['id', 'order_id', 'authority', 'ref_id', 'status', 'gateway', 'created_at', 'updated_at', 'order']
    exclude_fields_from_list = ['updated_at']
    exclude_fields_from_create = ['id', 'created_at', 'updated_at']
    exclude_fields_from_edit = ['id', 'created_at', 'updated_at']


class SubscriptionView(ModelView):
    """
    Subscription management with per-user node access.
    
    plan_type options:
    - "free": Basic access with free tier nodes
    - "custom": Custom node access defined in node_overrides
    
    node_overrides JSON format:
    {
        "nodes": ["ai_agent", "deepseek", "openai", "telegram"],
        "features": {"max_executions": 1000}  // optional
    }
    """
    fields = [
        'id', 'user_id', 'plan_type',
        JSONField('node_overrides', label='Node Overrides (JSON)'),
        'nodes_used', 'nodes_limit', 'start_date', 'end_date', 
        'is_active', 'created_at', 'updated_at', 'user'
    ]
    exclude_fields_from_list = ['updated_at', 'node_overrides']
    exclude_fields_from_create = ['id', 'updated_at', 'created_at']
    exclude_fields_from_edit = ['id', 'updated_at', 'created_at']
    searchable_fields = ['user_id', 'plan_type']
    sortable_fields = ['id', 'user_id', 'plan_type', 'is_active', 'start_date', 'end_date']
    
    label = "Subscriptions"
    name = "subscription"
    icon = "fa fa-credit-card"


admin = Admin(get_async_engine(), 
              title="hello admin",
              auth_provider=CustomAuthProvider(),
              middlewares=[Middleware(SessionMiddleware, secret_key=settings.ADMIN_SECRET_KEY)],)

admin.add_view(UserView(User))
admin.add_view(ModelView(PhoneCode))
admin.add_view(ModelView(WhiteListPhones))
admin.add_view(WorkflowView(Workflow))
admin.add_view(ModelView(Credential))
admin.add_view(ModelView(CredentialType))
admin.add_view(DynamicNodeView(DynamicNode))
admin.add_view(OptionView(Option))
admin.add_view(PlanView(Plan))
admin.add_view(OrderView(Order))
admin.add_view(TransactionView(Transaction))
admin.add_view(SubscriptionView(Subscription))
