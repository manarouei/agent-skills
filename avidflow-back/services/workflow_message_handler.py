import asyncio
import json
from typing import Dict, Any
import aio_pika
from fastapi import WebSocket
from config import settings

class WorkflowMessageHandler:
    """Handles messages from RabbitMQ and forwards them to appropriate WebSocket connections"""
    
    def __init__(self):
        self.local_websocket_connections = {}  # Only local connections for this worker
        self.execution_complete_events = {}  # Local completion events
        self.connection = None
        self.channel = None
        self.websocket_exchange = None

        # token -> {"event": asyncio.Event, "data": Dict[str, Any] | None, "connection_key": str}
        self.test_webhook_waiters: dict[str, dict] = {}
    
    async def initialize_rabbitmq(self):
        """Initialize RabbitMQ connection for WebSocket coordination"""
        self.connection = await aio_pika.connect_robust(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            login=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASSWORD
        )
        
        self.channel = await self.connection.channel()
        
        # Create a fanout exchange for WebSocket messages
        self.websocket_exchange = await self.channel.declare_exchange(
            "websocket_messages",
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )
    
    async def register_execution(self, workflow_id: str, execution_id: str, websocket: WebSocket) -> None:
        """Register a new execution websocket locally and notify other workers"""
        connection_key = f"{workflow_id}:{execution_id}"
        
        # Store locally
        self.local_websocket_connections[connection_key] = websocket
        self.execution_complete_events[connection_key] = asyncio.Event()
        
        # Notify other workers about this registration via RabbitMQ
        if self.websocket_exchange:
            registration_message = {
                "type": "websocket_registered",
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "worker_id": id(self)  # Use object id as worker identifier
            }
            
            await self.websocket_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(registration_message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
                ),
                routing_key=""
            )
    
    async def handle_message(self, message: Dict[str, Any]) -> None:
        """Process messages from RabbitMQ and send to appropriate websocket"""
        event = message.get("event")
        workflow_id = message.get("workflow_id")
        execution_id = message.get("execution_id")
        
        if not workflow_id or not execution_id:
            return
        
        connection_key = f"{workflow_id}:{execution_id}"
        
        # Check if we have this WebSocket connection locally
        websocket = self.local_websocket_connections.get(connection_key)
        
        if websocket:
            try:
                # Send message to the local WebSocket
                await websocket.send_json({
                    "type": "workflow_update",
                    "data": message
                })
                
                # If this is a completion or error event, signal completion and close
                if event in ["workflow_completed", "workflow_error", "node_error"]:
                    if connection_key in self.execution_complete_events:
                        self.execution_complete_events[connection_key].set()
                    
                    await asyncio.sleep(0.5)
                    await websocket.close()
                    
                    # Clean up locally
                    self._cleanup_connection(connection_key)
                    
            except Exception:
                # Connection might be already closed
                self._cleanup_connection(connection_key)
        else:
            # Forward to other workers via RabbitMQ fanout exchange
            if self.websocket_exchange:
                await self.websocket_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps({
                            "type": "workflow_message_forward",
                            "message": message
                        }).encode(),
                        delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
                    ),
                    routing_key=""
                )
    
    async def register_test_webhook_waiter(self, connection_key: str, token: str) -> None:
        """Register a waiter for a test webhook payload identified by token."""
        self.test_webhook_waiters[token] = {
            "event": asyncio.Event(),
            "data": None,
            "connection_key": connection_key,
        }

    async def wait_for_test_webhook(self, token: str, timeout: float = 120.0) -> dict | None:
        """Wait for test webhook payload or timeout."""
        waiter = self.test_webhook_waiters.get(token)
        if not waiter:
            return None
        try:
            await asyncio.wait_for(waiter["event"].wait(), timeout=timeout)
            return waiter["data"]
        except asyncio.TimeoutError:
            return None
        finally:
            # cleanup regardless of outcome
            self.test_webhook_waiters.pop(token, None)

    async def receive_test_webhook_payload(self, token: str, payload: dict) -> None:
        """Receive payload locally or forward to any worker that registered the token."""
        waiter = self.test_webhook_waiters.get(token)
        if waiter:
            waiter["data"] = payload
            waiter["event"].set()
            return
        # Forward to all workers; the correct worker will deliver to its local waiter
        if self.websocket_exchange:
            await self.websocket_exchange.publish(
                aio_pika.Message(
                    body=json.dumps({
                        "type": "webhook_test_payload",
                        "token": token,
                        "payload": payload
                    }).encode(),
                    delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
                ),
                routing_key=""
            )

    async def handle_websocket_coordination_message(self, data: Dict[str, Any]) -> None:
        """Handle coordination messages between workers"""
        message_type = data.get("type")
        
        if message_type == "workflow_message_forward":
            # This is a forwarded workflow message, try to handle it locally
            workflow_message = data.get("message")
            if workflow_message:
                await self._handle_forwarded_message(workflow_message)
            return

        # Deliver webhook test payload to local waiter if present
        if message_type == "webhook_test_payload":
            token = data.get("token")
            payload = data.get("payload")
            if not token:
                return
            waiter = self.test_webhook_waiters.get(token)
            if waiter:
                waiter["data"] = payload
                waiter["event"].set()
            return
    
    async def _handle_forwarded_message(self, message: Dict[str, Any]) -> None:
        """Handle a message forwarded from another worker"""
        event = message.get("event")
        workflow_id = message.get("workflow_id")
        execution_id = message.get("execution_id")
        
        if not workflow_id or not execution_id:
            return
        
        connection_key = f"{workflow_id}:{execution_id}"
        websocket = self.local_websocket_connections.get(connection_key)
        
        if websocket:
            try:
                await websocket.send_json({
                    "type": "workflow_update",
                    "data": message
                })
                
                if event in ["workflow_completed", "workflow_error"]:
                    if connection_key in self.execution_complete_events:
                        self.execution_complete_events[connection_key].set()
                    
                    await asyncio.sleep(0.5)
                    await websocket.close()
                    self._cleanup_connection(connection_key)
                    
            except Exception:
                self._cleanup_connection(connection_key)
    
    def _cleanup_connection(self, connection_key: str) -> None:
        """Clean up local connection references"""
        if connection_key in self.local_websocket_connections:
            del self.local_websocket_connections[connection_key]
        if connection_key in self.execution_complete_events:
            del self.execution_complete_events[connection_key]
    
    async def close(self):
        """Close RabbitMQ connections"""
        if self.connection:
            await self.connection.close()