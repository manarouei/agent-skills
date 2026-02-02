"""
Command to synchronize node classes with dynamic_nodes table.
"""
import inspect
from typing import List, Type

from commands.base import BaseCommand
from commands import register_command
from database.models import DynamicNode
from nodes.base import BaseNode

# Import the node_definitions registry directly from nodes package
from nodes import node_definitions

from sqlalchemy.future import select
from database.config import get_async_session


class SyncNodesCommand(BaseCommand):
    """Command to sync node classes with dynamic_nodes table"""
    
    name = "sync_nodes"
    help = "Synchronize available node classes with the dynamic_nodes table"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing nodes in the database'
        )
    
    async def handle(self, *args, **options) -> str:
        """Execute the command"""
        force = options.get('force', False)
        
        print("Getting node classes from registry...")
        node_classes = self.get_node_classes_from_registry()
        
        print(f"Found {len(node_classes)} node classes")
        
        # Get a database session - properly await the coroutine
        session = await get_async_session()
        try:
            # Get existing nodes
            result = await session.execute(select(DynamicNode))
            existing_nodes = {node.type: node for node in result.scalars().all()}
            
            created = 0
            updated = 0
            skipped = 0
            
            for node_class in node_classes:
                try:
                    # Extract node information
                    node_type = getattr(node_class, "type", None)
                    if not node_type:
                        print(f"Skipping {node_class.__name__}: Missing type attribute")
                        continue
                    
                    version = getattr(node_class, "version", 1)
                    description = getattr(node_class, "description", {})
                    properties = getattr(node_class, "properties", {})
                    icon = getattr(node_class, "icon", None)
                    color = getattr(node_class, "color", None)
                    
                    # Determine category from description or class name
                    category = (
                        description.get("group", ["uncategorized"])[0]
                        if description and isinstance(description.get("group"), list)
                        else "uncategorized"
                    )
                    
                    # Check if node has inputs or not (is_start)
                    is_start = False
                    is_end = False
                    if description:
                        # Node is a start node if it has no inputs
                        is_start = not description.get("inputs")
                        
                        # Node is an end node if it has no outputs
                        is_end = not description.get("outputs")
                    
                    # Get display name
                    name = (
                        description.get("displayName", node_class.__name__)
                        if description
                        else node_class.__name__
                    )
                    
                    # Check if node already exists
                    if node_type in existing_nodes:
                        if force:
                            # Update existing node
                            db_node = existing_nodes[node_type]
                            db_node.version = version
                            db_node.name = name
                            db_node.description = description
                            db_node.properties = properties
                            db_node.category = category
                            db_node.is_start = is_start
                            db_node.is_end = is_end
                            # Don't update icon unless specified
                            if icon:
                                db_node.icon = icon
                            if color:
                                db_node.color = color
                            
                            updated += 1
                        else:
                            skipped += 1
                            continue
                    else:
                        # Create new node
                        db_node = DynamicNode(
                            type=node_type,
                            version=version,
                            name=name,
                            description=description,
                            properties=properties,
                            category=category,
                            is_start=is_start,
                            is_end=is_end
                        )
                        if icon:
                            db_node.icon = icon
                        if color:
                            db_node.color = color
                            
                        session.add(db_node)
                        created += 1
                
                except Exception as e:
                    print(f"Error processing node class {node_class.__name__}: {str(e)}")
            
            # Commit changes
            await session.commit()
            
        finally:
            # Properly close the session
            await session.close()
        
        return f"Node synchronization complete: {created} created, {updated} updated, {skipped} skipped"
    
    def get_node_classes_from_registry(self) -> List[Type[BaseNode]]:
        """Get all node classes from the node_definitions registry"""
        node_classes = []
        
        # Get node classes from the registry
        for node_type, node_info in node_definitions.items():
            node_class = node_info.get('node_class')
            if node_class and issubclass(node_class, BaseNode) and node_class != BaseNode:
                node_classes.append(node_class)
                
        return node_classes


# Register the command
register_command("sync_nodes", SyncNodesCommand)
