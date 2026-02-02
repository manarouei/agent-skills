import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from contextlib import asynccontextmanager
from typing import Dict, Any

# Database imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Service imports
from services.workflow_message_handler import WorkflowMessageHandler
from services.workflow_message_consumer import WorkflowMessageConsumer
from services.redis_manager import RedisManager
from database.admin2 import admin
from config import settings

# Router imports
from routers import (
    auth,
    user,
    workflow,
    executions,
    node_types,
    websocket,
    credentials,
    dashboard,
    oauth2,
    webhook,
    payments,
    form_submission,
    chat,
    tools,
    admin_node_access,
)

load_dotenv()


# Error handling
class ErrorHandler:
    async def log_error(self, error: Exception, context: Dict[str, Any] = None):
        # Log error to your preferred logging system
        error_msg = f"Error: {str(error)}"
        if context:
            error_msg += f", Context: {context}"
        print(error_msg)  # Replace with proper logging


# Application lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    app.state.error_handler = ErrorHandler()

    # Initialize database
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    app.state.session_factory = AsyncSessionLocal

    # Initialize message handler
    message_handler = WorkflowMessageHandler()
    await message_handler.initialize_rabbitmq()
    app.state.message_handler = message_handler

    # Start RabbitMQ consumer
    consumer = WorkflowMessageConsumer(message_handler)
    app.state.message_consumer_connection = await consumer.start()

    redis_manager = RedisManager()
    await redis_manager.connect()
    app.state.redis = redis_manager

    # Yield control to FastAPI
    yield

    # Shutdown: Cleanup resources
    await engine.dispose()
    await message_handler.close()

    if hasattr(app.state, "message_consumer_connection"):
        await app.state.message_consumer_connection.close()

    if hasattr(app.state, "redis"):
        await app.state.redis.disconnect()


app = FastAPI(
    title="workflow API",
    description="API for workflow automation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    await app.state.error_handler.log_error(exc, {"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# Add routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(user.router, prefix="/api/users", tags=["Users"])
app.include_router(workflow.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(executions.router, prefix="/api/executions", tags=["Executions"])
app.include_router(node_types.router, prefix="/api/node-types", tags=["Node Types"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(executions.router, prefix="/api/executions", tags=["Executions"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["Credentials"])
app.include_router(oauth2.router, prefix="/api/oauth2", tags=["OAuth2"])
app.include_router(websocket.router, tags=["WebSockets"])
app.include_router(webhook.router, tags=["Webhooks"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(form_submission.router, prefix="/api/form", tags=["form_submission"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin_node_access.router, prefix="/api", tags=["Admin - Node Access"])
admin.mount_to(app)

# Static files (only in debug mode)
if settings.DEBUG and os.path.exists("media"):
    app.mount("/media", StaticFiles(directory="media"), name="media")


# Add pagination to the app
add_pagination(app)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to the Workflow Automation API",
        "documentation": "/docs",
    }


# Health check endpoint
@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": app.version}


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, workers=4)
