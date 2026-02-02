import json
import pika
from typing import Dict, Any, Callable
import aio_pika
from config import settings


class QueueService:
    """Service for RabbitMQ messaging"""
    
    def __init__(self):
        self.connection_params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=pika.PlainCredentials(
                username=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASSWORD
            )
        )
        
    def publish_sync(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish message to queue (synchronous version)"""
        try:
            connection = pika.BlockingConnection(self.connection_params)
            channel = connection.channel()
            
            # Declare queue (creates if doesn't exist)
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Publish message
            channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                )
            )
            
            connection.close()
            return True
        except Exception as e:
            print(f"Error publishing to queue: {str(e)}")
            return False
    
    async def publish(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Publish message to queue (async version)"""
        try:
            # Create connection
            connection = await aio_pika.connect_robust(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                login=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASSWORD,
                virtualhost=settings.RABBITMQ_VHOST
            )
            
            # Create channel
            channel = await connection.channel()
            
            # Declare queue
            queue = await channel.declare_queue(queue_name, durable=True)
            
            # Convert message to JSON and publish
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=queue_name
            )
            
            # Close connection
            await connection.close()
            return True
        except Exception as e:
            print(f"Error publishing to queue: {str(e)}")
            return False
    
    async def consume(self, queue_name: str, callback: Callable) -> None:
        """Consume messages from queue"""
        # Create connection
        connection = await aio_pika.connect_robust(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            login=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASSWORD,
            virtualhost=settings.RABBITMQ_VHOST
        )
        
        # Create channel
        channel = await connection.channel()
        
        # Declare queue
        queue = await channel.declare_queue(queue_name, durable=True)
        
        # Set up consumer
        async def internal_callback(message: aio_pika.IncomingMessage) -> None:
            async with message.process():
                body = message.body.decode()
                data = json.loads(body)
                await callback(data)
        
        # Start consuming
        await queue.consume(internal_callback)