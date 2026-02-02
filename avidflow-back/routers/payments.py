from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import PlanCRUD, OrderCRUD, TransactionCRUD, SubscriptionCRUD
from auth.dependencies import get_current_user
from database.models import TransactionStatusEnum, OrderStatusEnum, User
from models.payment import (
    PaymentsPlans,
    OrderCreateRequest,
    OrderResponse,
    OrderRead,
    SubscriptionDetail,
)
from fastapi_pagination import Page, Params
from config import settings
from payman import Payman
from payman.gateways.zarinpal.models import (
    VerifyRequest,
    CallbackParams,
    PaymentRequest,
)
from payman.errors import GatewayError


router = APIRouter()


# Use the same database dependency pattern as other routers
async def get_db_from_app(request: Request):
    """Get database session from app state - fixed to yield properly"""
    async with request.app.state.session_factory() as session:
        yield session



def get_gateway() -> Payman:
    """Returns a Payman instance for the ZarinPal gateway."""
    return Payman("zarinpal", merchant_id=settings.ZARINPAL_MERCHANT_ID, sandbox=False)


@router.get("/subscription", response_model=SubscriptionDetail)
async def get_user_active_subscription(
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get active subscription for user"""
    subscription = await SubscriptionCRUD.get_user_active_subscription(db=db, user_id=current_user.id)
    if not subscription:
        raise HTTPException(status_code=400, detail="طرح فعالی وجود ندارد.")
    return subscription


@router.get("/plans", response_model=List[PaymentsPlans])
async def get_subscription_plans(
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get all available subscription plans"""
    return await PlanCRUD.get_all_plans(db=db)


@router.get("/orders", response_model=Page[OrderRead])
async def list_orders(
    params: Params = Depends(),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """List user orders"""
    return await OrderCRUD.get_user_orders(db, user_id=current_user.id, params=params)


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreateRequest,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Create a new order"""
    subscription = await SubscriptionCRUD.get_user_active_subscription(
        db=db, user_id=current_user.id
    )
    if subscription:
        raise HTTPException(status_code=400, detail="اشتراک فعال دارید.")
    return await OrderCRUD.create_order(
        db=db, user_id=current_user.id, plan_id=order_data.plan_id
    )


@router.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Get order details"""
    order = await OrderCRUD.get_order(db=db, order_id=order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="جای اشتبایی آمده اید.")
    return order


@router.post("/request/{order_id}")
async def start_payment(
    order_id: int,
    pay: Payman = Depends(get_gateway),
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    """Start payment for an order"""
    order = await OrderCRUD.get_order(db=db, order_id=order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="جای اشتباهی آمده اید!")

    # Call payment service
    request = PaymentRequest(
        amount=order.amount,
        currency="IRT",
        callback_url=settings.ZARINPAL_CALLBACK_URL,
        description=f"پرداخت تعرفه آویدفلو برای کاربر {current_user.username}",
        metadata={"mobile": current_user.username},
    )
    response = await pay.payment(request)
    payment_url = pay.get_payment_redirect_url(response.authority)
    transaction = await TransactionCRUD.create_transaction(
        db, authority=response.authority, order_id=order.id
    )
    return {"gateway_address": payment_url}


@router.get("/verify")
async def handle_payment_callback(
    pay: Payman = Depends(get_gateway),
    db: AsyncSession = Depends(get_db_from_app),
    callback: CallbackParams = Depends(),
):
    """
    Handle the callback from the payment gateway and verify the transaction.
    """
    transaction = await TransactionCRUD.get_transaction_by_authority(db, callback.authority)
    if not transaction:
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")

    order = await OrderCRUD.get_order(db, order_id=transaction.order_id)
    if not order:
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")

    if not callback.is_success:
        transaction.status = TransactionStatusEnum.failed
        order.status = OrderStatusEnum.failed
        await db.commit()
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")

    try:
        verify = await pay.verify(
            VerifyRequest(authority=callback.authority, amount=order.amount)
        )

        if verify.success:
            transaction.status = TransactionStatusEnum.success
            transaction.ref_id = str(verify.ref_id)
            order.status = OrderStatusEnum.paid

            sub = await SubscriptionCRUD.create_subscription(
                db, user_id=order.user_id, order_id=order.id
            )
            db.add(sub)
            await db.commit()
            return RedirectResponse(
                url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=OK&&ref_id={verify.ref_id}"
            )
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")

    except GatewayError as e:
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")
    except Exception as e:
        return RedirectResponse(url=f"{settings.ZARINPAL_FRONTEND_URL_REDIRECT}?status=NOK")
