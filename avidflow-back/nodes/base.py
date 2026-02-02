from typing import Dict, Any, Optional, List, Callable
from abc import ABC
from datetime import datetime
from utils.encryption import decrypt_credential_data, encrypt_credential_data
from enum import Enum
from utils.expression_evaluator import ExpressionEngine, ExpressionError
from pydantic import BaseModel, TypeAdapter
from database.config import get_sync_session_manual
from database.crud import CredentialCRUD
from models import Node, WorkflowModel, NodeExecutionData, ConnectionType
import json
import base64
import zlib
import logging

logger = logging.getLogger(__name__)


class NodeParameterType(str, Enum):
    """Enumeration of node parameter types"""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OPTIONS = "options"
    MULTI_OPTIONS = "multiOptions"
    COLOR = "color"
    JSON = "json"
    COLLECTION = "collection"
    DATETIME = "dateTime"
    NODE = "node"
    RESOURCE_LOCATOR = "resourceLocator"
    NOTICE = "notice"
    ARRAY = "array"
    CODE = "code"


class NodeParameter(BaseModel):
    """Base model for node parameters"""

    name: str
    type: str
    required: bool = False
    default: Optional[Any] = None
    value: Optional[Any] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    placeholder: Optional[str] = None
    type_options: Optional[Dict[str, Any]] = None
    options: Optional[List[Dict[str, Any]]] = None
    display_options: Optional[Dict[str, Any]] = None


class NodeCredential(BaseModel):
    """Base model for node credentials"""

    name: str
    type: str
    required: bool = False
    display_name: Optional[str] = None
    testing: Optional[bool] = None


class NodeIO(BaseModel):
    """Base model for node input/output"""

    name: str = "main"
    type: str = "main"
    required: bool = True
    max_connections: Optional[int] = None
    display_name: Optional[str] = None


class NodeRunMode(str, Enum):
    """Enumeration of node run modes"""

    DEFAULT = "default"  # Run node once
    FOREACH = "foreach"  # Run node once for each item
    PARALLEL = "parallel"  # Run node in parallel


class GetNodeParameterOptions(BaseModel):
    """Options for parameter retrieval"""
    context_node: Optional[str] = None
    ensure_type: Optional[str] = None
    extract_value: bool = False
    raw_expressions: bool = False


class NodeReference:
    """Helper class for accessing node data in expressions"""
    
    def __init__(self, node_name: str, execution_data: Dict[str, Any]):
        self.node_name = node_name
        self.execution_data = execution_data
        self._all_outputs = self._get_all_outputs()
    
    def _get_all_outputs(self) -> List[List[NodeExecutionData]]:
        """Get all outputs from the referenced node"""
        if self.node_name not in self.execution_data:
            return []
        
        node_exec_data = self.execution_data[self.node_name]
        
        # node_exec_data is List[List[NodeExecutionData]]
        if isinstance(node_exec_data, list):
            validated_outputs = []
            for output_index, output_data in enumerate(node_exec_data):
                if isinstance(output_data, list):
                    try:
                        adapter = TypeAdapter(List[NodeExecutionData])
                        validated_output = adapter.validate_python(output_data)
                        validated_outputs.append(validated_output)
                    except Exception as e:
                        logger.error(f"Validation failed for {self.node_name} output[{output_index}]: {e}")
                        validated_outputs.append([])
                else:
                    validated_outputs.append([])
            return validated_outputs
        
        return []
    
    def _get_node_data(self, output_index: int = 0) -> List[NodeExecutionData]:
        """Get execution data for a specific output index"""
        if len(self._all_outputs) > output_index:
            return self._all_outputs[output_index]
        return []
    
    @property
    def json(self) -> Dict[str, Any]:
        """Get JSON data from the first item of the first output"""
        node_data = self._get_node_data(0)  # Main output
        if node_data:
            first_item = node_data[0]
            return first_item.json_data if hasattr(first_item, 'json_data') else {}
        return {}
    
    @property
    def binary(self) -> Dict[str, Any]:
        """Get binary data from the first item of the first output"""
        node_data = self._get_node_data(0)  # Main output
        if node_data:
            first_item = node_data[0]
            return first_item.binary_data if hasattr(first_item, 'binary_data') else {}
        return {}
    
    @property
    def item(self) -> 'NodeItem':
        """Get the first item from the first output as a NodeItem object"""
        node_data = self._get_node_data(0)  # Main output
        return NodeItem(node_data, 0) if node_data else NodeItem([], 0)
    
    @property
    def first(self) -> 'NodeItem':
        """Alias for item (first item from first output)"""
        return self.item
    
    @property
    def last(self) -> 'NodeItem':
        """Get the last item from the first output"""
        node_data = self._get_node_data(0)  # Main output
        if node_data:
            return NodeItem(node_data, len(node_data) - 1)
        return NodeItem([], 0)
    
    @property
    def all(self) -> List['NodeItem']:
        """Get all items from the first output"""
        node_data = self._get_node_data(0)  # Main output
        return [NodeItem(node_data, i) for i in range(len(node_data))]
    
    def itemMatching(self, index: int) -> 'NodeItem':
        """Get item at specific index from the first output"""
        node_data = self._get_node_data(0)  # Main output
        return NodeItem(node_data, index) if index < len(node_data) else NodeItem([], 0)
    
    def output(self, output_index: int) -> 'NodeOutput':
        """Get a specific output by index (for multi-output nodes like IF)"""
        return NodeOutput(self._get_node_data(output_index))

class NodeOutput:
    """Helper class for accessing specific output data"""
    
    def __init__(self, output_data: List[NodeExecutionData]):
        self.output_data = output_data
    
    @property
    def json(self) -> Dict[str, Any]:
        """Get JSON data from the first item"""
        if self.output_data:
            first_item = self.output_data[0]
            return first_item.json_data if hasattr(first_item, 'json_data') else {}
        return {}
    
    @property
    def first(self) -> 'NodeItem':
        """Get the first item"""
        return NodeItem(self.output_data, 0) if self.output_data else NodeItem([], 0)
    
    @property
    def last(self) -> 'NodeItem':
        """Get the last item"""
        if self.output_data:
            return NodeItem(self.output_data, len(self.output_data) - 1)
        return NodeItem([], 0)
    
    @property
    def all(self) -> List['NodeItem']:
        """Get all items"""
        return [NodeItem(self.output_data, i) for i in range(len(self.output_data))]
    
    def itemMatching(self, index: int) -> 'NodeItem':
        """Get item at specific index"""
        return NodeItem(self.output_data, index) if index < len(self.output_data) else NodeItem([], 0)


class NodeItem:
    """Helper class for accessing individual item data"""
    
    def __init__(self, node_data: List[NodeExecutionData], index: int):
        self.node_data = node_data
        self.index = index
        self._item_data = self._get_item_data()
    
    def _get_item_data(self) -> Optional[NodeExecutionData]:
        """Get the item data at the specified index"""
        if self.node_data and 0 <= self.index < len(self.node_data):
            return self.node_data[self.index]
        return None
    
    @property
    def json(self) -> Dict[str, Any]:
        """Get JSON data from this item"""
        if self._item_data and hasattr(self._item_data, 'json_data'):
            return self._item_data.json_data
        return {}
    
    @property
    def binary(self) -> Dict[str, Any]:
        """Get binary data from this item"""
        if self._item_data and hasattr(self._item_data, 'binary_data'):
            return self._item_data.binary_data or {}
        return {}


class BaseNode(ABC):
    """Base class for all workflow nodes"""

    # Class attributes that must be defined by subclasses
    type: str
    version: int
    description: Dict[str, Any]
    properties: Dict[str, Any]

    # Optional class attributes
    icon: Optional[str] = None
    color: Optional[str] = None
    subtitle: Optional[str] = None
    documentation_url: Optional[str] = None

    def __init__(
        self, node_data: Node, workflow: WorkflowModel, execution_data: Dict[str, Any]
    ):
        self.node_data = node_data
        self.workflow = workflow
        self.execution_data = execution_data
        self._parameters: Dict[str, Any] = {}
        self._credentials: Dict[str, Any] = {}
        self._run_mode: NodeRunMode = NodeRunMode.DEFAULT
        self._execution_id: Optional[str] = None
        self._expression_engine = ExpressionEngine()
        self.input_data = self._preprocess_input_data()

        # Initialize parameters from node data if available
        if hasattr(node_data, "parameters") and node_data.parameters:
            try:
                if isinstance(node_data.parameters, str):
                    self._parameters = json.loads(node_data.parameters)
                else:
                    self._parameters = node_data.parameters.model_dump()
                # self._validate_parameters() TODO: implement this based on parameters dependecies
            except json.JSONDecodeError:
                logger.error(f"Failed to parse parameters for node {node_data.name}")
                self._parameters = {}

    def _extract_output_data(
        self, 
        source_data: List[List[NodeExecutionData]], 
        source_output_index: int, 
        connection_type: str
    ) -> List[NodeExecutionData]:
        """
        Extract output data from source based on output index.

        Args:
            source_data: List[List[NodeExecutionData]] - [output0_items, output1_items, ...]
            source_output_index: Which output index to get data from
            connection_type: Type of connection (for logging)

        Returns:
            List[NodeExecutionData] from the specified output index
        """

        try:
            # Simple bounds check and direct access
            if len(source_data) > source_output_index:
                output_items = source_data[source_output_index]

                if isinstance(output_items, list):
                    return output_items
                else:
                    logger.warning(f"Expected list at output[{source_output_index}], got {type(output_items)}")
                    return []
            else:
                logger.warning(f"Output index {source_output_index} not available (max: {len(source_data)-1})")
                return []

        except (IndexError, TypeError) as e:
            logger.error(f"Failed to extract {connection_type} data from output[{source_output_index}]: {e}")
            return []
        
    def _get_max_input_index(self, connection_type: str) -> int:
        """Get the maximum input index for this node and connection type"""
        if not hasattr(self.workflow, 'connections'):
            return 0
        
        connections = self.workflow.connections
        if hasattr(connections, 'root'):
            connections = connections.root
        
        current_node_name = self.node_data.name
        max_input_index = 0
        
        # Check for dynamic input configuration
        # number_inputs = self.get_parameter("numberInputs", 0, 0)
        # logger.warning(f"Dynamic input configuration for {current_node_name}: {number_inputs}")
        # if number_inputs and isinstance(number_inputs, int):
            # max_input_index = max(max_input_index, number_inputs - 1)
        
        # Also check actual connections
        for source_node_name, source_connections in connections.items():
            if not isinstance(source_connections, dict):
                continue
            
            if connection_type not in source_connections:
                continue
            
            for output_connections in source_connections[connection_type]:
                if not isinstance(output_connections, list):
                    continue
                
                for connection in output_connections:
                    if getattr(connection, 'node', None) == current_node_name:
                        input_index = getattr(connection, 'index', 0)
                        max_input_index = max(max_input_index, input_index)
        
        return max_input_index

    def _preprocess_input_data(self) -> Dict[str, List[List[NodeExecutionData]]]:
        """
        Preprocess execution data into n8n-style input_data structure.

        Returns:
            Dict[connection_type, List[input_arrays]] for each connection type
            Structure: {"main": [[input0_items], [input1_items], ...]}
        """

        if not self.execution_data or not hasattr(self.workflow, 'connections'):
            return {ConnectionType.MAIN: []}

        connections = self.workflow.connections
        if hasattr(connections, 'root'):
            connections = connections.root

        current_node_name = self.node_data.name

        # Initialize input_data structure
        input_data = {}

        # Find all connection types used in the workflow
        all_connection_types = set()
        for source_connections in connections.values():
            if isinstance(source_connections, dict):
                all_connection_types.update(source_connections.keys())

        # Default to main if no connection types found
        if not all_connection_types:
            all_connection_types.add(ConnectionType.MAIN)

        # Initialize each connection type with empty arrays
        for conn_type in all_connection_types:
            max_input_index = self._get_max_input_index(conn_type)
            input_data[conn_type] = [[] for _ in range(max_input_index + 1)]

        # Process all connections TO this node
        for source_node_name, source_connections in connections.items():
            if not isinstance(source_connections, dict):
                continue
            
            # Process each connection type
            for connection_type, source_outputs in source_connections.items():
                if not isinstance(source_outputs, list):
                    continue
                
                # Check each output from the source node
                for source_output_index, connection_list in enumerate(source_outputs):
                    if not isinstance(connection_list, list):
                        continue
                    
                    for connection in connection_list:
                        target_node = getattr(connection, 'node', None)
                        target_input_index = getattr(connection, 'index', 0)

                        # If this connection targets our node
                        if target_node == current_node_name:
                            # Get source node's execution data: List[List[NodeExecutionData]]
                            source_data = self.execution_data.get(source_node_name, [])

                            if source_data:
                                # FIXED: Direct access to the structure you described
                                output_items = self._extract_output_data(
                                    source_data, 
                                    source_output_index, 
                                    connection_type
                                )

                                if output_items:
                                    # Ensure connection type exists in input_data
                                    if connection_type not in input_data:
                                        input_data[connection_type] = []

                                    # Ensure we have enough input slots
                                    while len(input_data[connection_type]) <= target_input_index:
                                        input_data[connection_type].append([])

                                    # FIXED: Extend items to target input (merge multiple sources)
                                    input_data[connection_type][target_input_index].extend(output_items)

        return input_data

    def get_node_parameter(
        self, 
        parameter_name: str, 
        item_index: int = 0, 
        fallback_value: Any = None,
        options: Optional[GetNodeParameterOptions] = None
    ) -> Any:
        """
        Get a node parameter value with expression evaluation support.
        
        Args:
            parameter_name: Name of the parameter (supports dot notation like 'additionalFields.limit')
            item_index: Index of the item being processed
            fallback_value: Default value if parameter is not found
            options: Additional options for parameter retrieval
            
        Returns:
            The parameter value, potentially processed through expressions
            
        Raises:
            ValueError: If required parameter not found and no fallback provided
            ExpressionError: If expression evaluation fails
        """
        return self._get_node_parameter(parameter_name, item_index, fallback_value, options)

    def _get_node_parameter(
        self, 
        parameter_name: str, 
        item_index: int, 
        fallback_value: Any = None,
        options: Optional[GetNodeParameterOptions] = None
    ) -> Any:
        """Internal implementation of get_node_parameter"""
        
        # Get the raw parameter value using dot notation support
        value = self._get_nested_parameter(parameter_name, fallback_value)
        
        # If raw expressions requested, return value directly
        if options and options.raw_expressions:
            return value
        
        # Handle expression evaluation
        try:
            return_data = self._evaluate_expressions(
                value, 
                item_index, 
                parameter_name,
                options
            )
            
            # Clean up parameter data
            return_data = self._cleanup_parameter_data(return_data)
            
        except ExpressionError as e:
            # Special handling for Set nodes with continue_on_fail
            if (hasattr(self.node_data, 'continue_on_fail') and 
                self.node_data.continue_on_fail):
                return_data = [{"name": None, "value": None}]
            else:
                e.context["parameter"] = parameter_name
                raise e
        
        return return_data

    def _get_nested_parameter(self, parameter_name: str, fallback_value: Any = None) -> Any:
        """
        Get parameter value supporting dot notation with array indexing
        Examples: 'conditions.0.dataType', 'additionalFields.limit', 'array.2.field'
        """
        # Handle both dict and NodeParameters model
        params = self._parameters
        
        # Split parameter name by dots for nested access
        keys = parameter_name.split('.')
        current = params
        
        for key in keys:
            try:
                # Check if key is a numeric index (for arrays)
                if key.isdigit():
                    index = int(key)
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return fallback_value
                # Handle dictionary keys
                elif isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return fallback_value
            except (ValueError, IndexError, TypeError):
                return fallback_value
        
        return current

    def _evaluate_expressions(
        self, 
        value: Any, 
        item_index: int, 
        parameter_name: str,
        options: Optional[GetNodeParameterOptions] = None
    ) -> Any:
        """
        Evaluate expressions in parameter values using the production engine.
        """
        # Get current item data for expression context
        input_data = self.get_input_data()
        current_item = None
        
        if input_data and len(input_data) > item_index:
            current_item = input_data[item_index]
        
        # Build expression context
        expression_context = {
            '$json': current_item.json_data if current_item else {},
            '$binary': current_item.binary_data if current_item else {},
            '$items': self._get_all_items(),
            '$node': self._get_node_context(),
            '$workflow': self._get_workflow_context(),
            '$execution': self._get_execution_context(),
            '$now': datetime.now(),
            '$today': datetime.now().date(),
            '$parameter': {
                'name': parameter_name,
                'itemIndex': item_index
            },
            # Add node reference function
            '$node_ref': self._create_node_reference_function()
        }
        
        try:
            return self._expression_engine.evaluate_parameter(
                value, 
                expression_context, 
                item_index
            )
        except ExpressionError as e:
            e.context['parameter'] = parameter_name
            e.context['itemIndex'] = item_index
            raise e

    def _create_node_reference_function(self) -> Callable[[str], NodeReference]:
        """Create a function that returns NodeReference objects"""
        def node_ref(node_name: str) -> NodeReference:
            return NodeReference(node_name, self.execution_data)
        
        return node_ref

    def _get_item_data(self, index: int) -> Optional[NodeExecutionData]:
        """Get item data by index"""
        input_data = self.get_input_data()
        if input_data and len(input_data) > index:
            return input_data[index]
        return None

    def _get_all_items(self) -> List[NodeExecutionData]:
        """Get all input items"""
        return self.get_input_data()

    def _get_node_context(self) -> Dict[str, Any]:
        """Get node context for expressions"""
        return {
            'name': self.node_data.name,
            'type': self.node_data.type,
            'parameters': self._parameters
        }

    def _get_workflow_context(self) -> Dict[str, Any]:
        """Get workflow context for expressions"""
        return {
            'name': getattr(self.workflow, 'name', ''),
            'id': getattr(self.workflow, 'id', ''),
            'active': getattr(self.workflow, 'active', False)
        }

    def _get_execution_context(self) -> Dict[str, Any]:
        """Get execution context for expressions"""
        return {
            'id': self._execution_id or '',
            'mode': 'manual'  # or get from execution context
        }

    def _cleanup_parameter_data(self, data: Any) -> None:
        """Clean up parameter data (remove undefined values, etc.)"""
        return data

    def get_parameter(
        self, name: str, item_index: int = 0, default_value: Any = None
    ) -> Any:
        """
        Legacy method - delegates to get_node_parameter for compatibility
        """
        return self.get_node_parameter(name, item_index, default_value)

    def set_credentials(self, credentials: Dict[str, Any]) -> None:
        """Set node credentials"""
        self._credentials = credentials
        self._validate_credentials()

    def get_credentials(self, credential_type: str) -> Optional[Dict[str, Any]]:
        """Get credentials for the node by type"""
        if not hasattr(self, 'node_data') or not self.node_data:
            return None
            
        # Look for credentials in the node_data.credentials field
        credentials = getattr(self.node_data, 'credentials', None)
        if not credentials:
            return None

        if isinstance(credentials, dict) and credential_type in credentials:
            credential_info = credentials[credential_type]
           
            credential_id = None
            
            # Handle NodeCredential object
            if hasattr(credential_info, 'id') and hasattr(credential_info, 'name'):
                credential_id = credential_info.id

            # Handle dict format
            elif isinstance(credential_info, dict) and 'id' in credential_info:
                credential_id = credential_info['id']
            
            if credential_id:
                try:
                    with get_sync_session_manual() as session:
                        credential = CredentialCRUD().get_credential_sync(session, credential_id)
                        if credential:
                            credential_data = decrypt_credential_data(credential.data)
                            return credential_data
                        else:
                            logger.error('No credential found in database for id: %s', credential_id)
                except Exception as e:
                    logger.error('Error retrieving credential %s: %s', credential_id, str(e))

        return None

    def update_credentials(self, credential_type: str, credential_data: Dict[str, Any]) -> None:
        """Update node credentials"""
        if not hasattr(self, 'node_data') or not self.node_data:
            return None
            
        # Look for credentials in the node_data.credentials field
        credentials = getattr(self.node_data, 'credentials', None)
        if not credentials:
            return None

        if isinstance(credentials, dict) and credential_type in credentials:
            credential_info = credentials[credential_type]
           
            credential_id = None
            
            # Handle NodeCredential object
            if hasattr(credential_info, 'id') and hasattr(credential_info, 'name'):
                credential_id = credential_info.id

            # Handle dict format
            elif isinstance(credential_info, dict) and 'id' in credential_info:
                credential_id = credential_info['id']
            
            if credential_id:
                try:
                    with get_sync_session_manual() as session:
                        credential = CredentialCRUD().get_credential_sync(session, credential_id)
                        if credential:
                            credential.data = encrypt_credential_data(credential_data)
                            session.commit()
                            session.refresh(credential)
                            return credential.data
                        else:
                            logger.error('No credential found in database for id: %s', credential_id)
                except Exception as e:
                    logger.error('Error retrieving credential %s: %s', credential_id, str(e))

    def get_input_data(
        self, 
        input_index: int = 0, 
        connection_type: str = ConnectionType.MAIN
    ) -> List[NodeExecutionData]:
        """
        Get input data for a specific input connection (n8n compatible).

        Args:
            input_index: Index of the input connection (default: 0)
            connection_type: Type of connection (default: "main")

        Returns:
            List of NodeExecutionData items from the specified input
        """

        # Check if connection type exists in input_data
        if not hasattr(self, 'input_data') or self.input_data is None:
            logger.warning("No input_data available")
            return []

        if connection_type not in self.input_data:
            logger.warning(f"Connection type '{connection_type}' not found in input_data. Available types: {list(self.input_data.keys())}")
            return []

        # Get the connection type data
        connection_data = self.input_data[connection_type]

        # Check if input_index is valid
        if len(connection_data) <= input_index:
            logger.warning(f"Input index {input_index} not available for connection type '{connection_type}' (max: {len(connection_data)-1})")
            return []

        # Get items for the specific input index
        all_items = connection_data[input_index]

        if all_items is None:
            logger.warning(f"Input index {input_index} was not set (None) for connection type '{connection_type}'")
            return []

        # Validate and return the data
        try:
            if isinstance(all_items, list):
                adapter = TypeAdapter(List[NodeExecutionData])
                validated_items = adapter.validate_python(all_items)
                return validated_items
            else:
                logger.error(f"Expected list for {connection_type}[{input_index}], got {type(all_items)}")
                return []
        except Exception as e:
            logger.error(f"Validation failed for {connection_type}[{input_index}]: {e}")
            return []

    def set_execution_id(self, execution_id: str) -> None:
        """Set the execution ID for tracking purposes"""
        self._execution_id = execution_id
   
    def set_run_mode(self, mode: NodeRunMode) -> None:
        """Set the node running mode"""
        self._run_mode = mode

    def _validate_parameters(self) -> None:
        """Validate required parameters"""
        for param in self.properties.get("parameters", []):
            if param.get("required", False) and param["name"] not in self._parameters:
                raise ValueError(f"Required parameter '{param['name']}' not provided")

    def _validate_credentials(self) -> None:
        """Validate required credentials"""
        for cred in self.properties.get("credentials", []):
            if cred.get("required", False) and cred["name"] not in self._credentials:
                raise ValueError(f"Required credential '{cred['name']}' not provided")

    def get_connected_nodes(self) -> List[str]:
        """Get list of connected node names"""
        connections = getattr(self.node_data, "connections", {})
        connected_nodes = []

        for output_name, output_connections in connections.get("outputs", {}).items():
            for connection in output_connections:
                if "node" in connection:
                    connected_nodes.append(connection["node"])

        return connected_nodes

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute node functionality - must be implemented by subclasses"""
        raise NotImplementedError("This node does not support execute functionality")

    def trigger(self) -> List[List[NodeExecutionData]]:
        """Trigger node functionality - implemented by trigger nodes"""
        raise NotImplementedError("This node does not support trigger functionality")

    def register_schedule(self) -> Dict[str, Any]:
        """Get the schedule for the node in cron format"""
        raise NotImplementedError("This node does not support scheduling")

    def get_input_connections(self) -> List[str]:
        """Get list of input connections"""
        return [
            input_.get("name", "main") for input_ in self.description.get("inputs", [])
        ]

    def get_output_connections(self) -> List[str]:
        """Get list of output connections"""
        return [
            output.get("name", "main") for output in self.description.get("outputs", [])
        ]

    def get_node_schema(self) -> Dict[str, Any]:
        """Get node schema definition for frontend visualization"""
        return {
            "type": self.type,
            "version": self.version,
            "description": self.description,
            "properties": self.properties,
            "icon": self.icon,
            "color": self.color,
            "subtitle": self.subtitle,
            "documentationUrl": self.documentation_url,
        }
    
    def _parse_csv(self, value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [p.strip() for p in str(value).split(",") if p.strip()]

    def _binary_entry_to_bytes(self, entry: Dict[str, Any]) -> bytes:
            """
            Convert our binary entry into raw bytes.
            Supports:
            - data: base64 of raw bytes (common case)
            - data: base64(zlib.compress(base64(raw))) from our own parser fallback
            """
            data_str = entry.get("data") or ""
            if not data_str:
                return b""
            try:
                first = base64.b64decode(data_str)
            except Exception:
                # try urlsafe
                try:
                    fixed = data_str.replace("-", "+").replace("_", "/")
                    pad = len(fixed) % 4
                    if pad:
                        fixed += "=" * (4 - pad)
                    first = base64.b64decode(fixed)
                except Exception:
                    return b""
            # Try zlib-decompress → base64 → raw
            try:
                maybe_b64 = zlib.decompress(first)
                try:
                    return base64.b64decode(maybe_b64)
                except Exception:
                    return maybe_b64  # already raw
            except Exception:
                return first
            
    def compress_data(self, data: str) -> str:
        """
        Compress the data using zlib and then encode it to base64.
        """
        compressed = zlib.compress(data.encode("utf-8"), level=6)
        return base64.b64encode(compressed).decode("utf-8")


class NodeProperty(BaseModel):
    """Model for node property schema definition"""

    name: str
    display_name: str
    type: str
    default: Optional[Any] = None
    required: bool = False
    description: Optional[str] = None
    placeholder: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    type_options: Optional[Dict[str, Any]] = None
    display_options: Optional[Dict[str, Any]] = None


class CredentialsSchema(BaseModel):
    """Model for credentials schema definition"""

    name: str
    display_name: str
    properties: List[NodeProperty]
    authenticate: Optional[Dict[str, Any]] = None
    documentation_url: Optional[str] = None
