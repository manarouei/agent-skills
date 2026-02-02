import json
from typing import Dict, Any
import aio_pika
from config import settings
from services.workflow_message_handler import WorkflowMessageHandler

class WorkflowMessageConsumer:
    """Consumes workflow messages from RabbitMQ"""
    
    def __init__(self, message_handler: WorkflowMessageHandler):
        self.message_handler = message_handler
        self.workflow_queue_name = "workflow_updates"
        self.websocket_queue_name = None  # Will be auto-generated
        
    async def start(self):
        """Start consuming messages"""
        connection = await aio_pika.connect_robust(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT, 
            login=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASSWORD
        )
        
        # Creating channel
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        # Declaring workflow updates queue
        workflow_queue = await channel.declare_queue(
            self.workflow_queue_name,
            durable=True
        )
        
        # Start consuming workflow updates
        await workflow_queue.consume(self._process_workflow_message)
        
        # Set up WebSocket coordination
        await self._setup_websocket_coordination(channel)
        
        return connection
    
    async def _setup_websocket_coordination(self, channel):
        """Set up WebSocket coordination queue and consumer"""
        # Get the fanout exchange for WebSocket messages
        websocket_exchange = await channel.declare_exchange(
            "websocket_messages",
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )
        
        # Create an exclusive queue for this worker
        websocket_queue = await channel.declare_queue(
            exclusive=True  # Auto-delete when worker disconnects
        )
        
        # Bind to the fanout exchange
        await websocket_queue.bind(websocket_exchange)
        
        # Start consuming coordination messages
        await websocket_queue.consume(self._process_websocket_coordination_message)
        
        self.websocket_queue_name = websocket_queue.name
    
    async def _process_workflow_message(self, message: aio_pika.IncomingMessage):
        """Process a message from the workflow updates queue"""
        async with message.process():
            try:
                body = message.body.decode()
                data = json.loads(body)
                
                # Process the message via the handler
                await self.message_handler.handle_message(data)
                
            except Exception as e:
                print(f"Error processing workflow message: {str(e)}")
                import traceback
                traceback.print_exc()
    
    async def _process_websocket_coordination_message(self, message: aio_pika.IncomingMessage):
        """Process WebSocket coordination messages between workers"""
        async with message.process():
            try:
                message_body = message.body.decode()
                data = json.loads(message_body)
                await self.message_handler.handle_websocket_coordination_message(data)
            except Exception as e:
                print(f"Error processing WebSocket coordination message: {str(e)}")