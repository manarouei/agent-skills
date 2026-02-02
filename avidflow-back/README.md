# Workflow Automation API

A powerful, extensible workflow automation platform inspired by n8n. This API allows you to create, manage, and execute workflows that connect various services and automate tasks through an intuitive node-based approach.

## Features

- **Node-Based Workflow Design**: Create workflows by connecting different types of nodes
- **REST API**: Comprehensive API for managing workflows, users, and executions
- **WebSocket Support**: Real-time workflow execution updates
- **Celery Integration**: Background task processing for reliable workflow execution
- **JWT Authentication**: Secure API access with token-based authentication
- **Extensible Node System**: Easy to add new nodes and capabilities

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Celery
- **Database**: PostgreSQL (async support)
- **Message Broker**: RabbitMQ for Celery tasks and WebSocket communication

## Built-in Node Types

- **Start**: Entry point for workflow execution
- **HTTP Request**: Make API calls to external services
- **End**: Terminal node that marks the end of a workflow
- **Merge**: Combine data from multiple branches
- **More**: Additional nodes for various tasks

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL
- RabbitMQ

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/workflow-automation.git
cd workflow-automation
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install pip-tools
pip-sync
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Initialize the database:
```bash
alembic upgrade head
```

6. Initialize credential types:
```bash
python manage.py init_credential_types
```

7. Create a superuser (admin account):
```bash
python manage.py createsuperuser
```

## Running the Application

1. Start RabbitMQ:
```bash
# If using Docker:
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

2. Start Celery workers:
```bash
cd project_root_folder
celery -A celery_app worker --loglevel=info
```

3. Start the API server:
```bash
cd project_root_folder
uvicorn main:app --reload
```

## API Documentation

Once the server is running, access the interactive API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Creating Your First Workflow

### 1. Create a workflow using the API:

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
  "name": "Simple API Workflow",
  "description": "Fetch data from an external API",
  "nodes": [
    {
      "id": "7a95f350-158a-4509-af3b-3bfe95eeda01",
      "name": "Start",
      "type": "start",
      "position": [100, 250],
      "parameters": {},
      "is_start": true
    },
    {
      "id": "a4b8c7d6-e5f6-4321-b0c1-a2b3c4d5e6f7",
      "name": "HTTP",
      "type": "http_request",
      "position": [300, 250],
      "parameters": {
        "url": "https://api.example.com/data",
        "method": "GET",
        "headerParameters": {
          "Accept": "application/json"
        }
      }
    },
    {
      "id": "32f58e9a-cb41-4d67-8f39-12ab34cd56ef",
      "name": "End",
      "type": "end",
      "position": [500, 250],
      "parameters": {},
      "is_end": true
    }
  ],
  "connections": {
    "Start": {
      "main": [
        [
          {
            "node": "HTTP",
            "index": 0,
            "type": "main"
          }
        ]
      ]
    },
    "HTTP": {
      "main": [
        [
          {
            "node": "End",
            "index": 0,
            "type": "main"
          }
        ]
      ]
    }
  }
}'
```

### 2. Execute the workflow:
this api is not complete. be carefull.
```bash
curl -X POST http://localhost:8000/api/workflows/{workflow_id}/execute \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Or connect via WebSocket for real-time execution:

```javascript
const token = "your.jwt.token";
const socket = new WebSocket(`ws://localhost:8000/ws/workflows/execute/{workflow_id}?token=${token}`);

socket.onmessage = (event) => {
  console.log("Execution update:", JSON.parse(event.data));
};
```

## Creating Custom Nodes

1. Create a new node class in nodes:

```python
from typing import Dict, Any, List
from models import NodeExecutionData
from .base import BaseNode

class MyCustomNode(BaseNode):
    """
    A custom node implementation
    """
    
    def execute(self) -> List[List[NodeExecutionData]]:
        # Get input data
        items = self.get_input_data(self.node_data.name, "main", 0)
        
        # Process data
        result = []
        for item in items:
            # Your custom logic here
            processed_data = {"result": "processed " + str(item.json_data)}
            result.append(NodeExecutionData(json_data=processed_data))
            
        return [result]
```

2. Register your node in __init__.py:

```python
from .my_custom_node import MyCustomNode

node_definitions = {
    # ...existing nodes...
    'my_custom': {'node_class': MyCustomNode, 'type': 'regular'},
}
```

## Administration Commands

The system provides several management commands to help with administration tasks:

### Initialize Credential Types

Populates the database with standard credential types needed for nodes (OAuth2, HTTP auth, etc.):

```bash
python manage.py init_credential_types
```

This command:
- Creates standard credential types like OAuth2, HTTP Basic Auth, API Key, etc.
- Updates existing credential types with any schema changes
- Must be run during initial setup and after updates that modify credential schemas

### Create Superuser

Creates an administrator account for accessing the admin interface:

```bash
python manage.py createsuperuser
```

This interactive command will prompt you for:
- Username
- Password (with confirmation)
- Whether the user should have superuser privileges

Example:
