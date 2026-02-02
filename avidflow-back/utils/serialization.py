import uuid
from typing import Any, List, Dict
from models.node import NodeExecutionData


def deep_serialize(obj: Any) -> Any:
    """
    Recursively serialize Pydantic models to dictionaries
    
    Args:
        obj: Any object that might contain Pydantic models
        
    Returns:
        JSON-serializable version of the object
    """
    if hasattr(obj, 'model_dump'):
        return deep_serialize(obj.model_dump(mode='json'))
    elif isinstance(obj, dict):
        return {k: deep_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_serialize(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(deep_serialize(i) for i in obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    else:
        return obj
    

def to_dict_without_binary(data: List[List[NodeExecutionData]]) -> List[List[Dict[str, Any]]]:
    return [
        [node.model_dump(mode='json', exclude={"binary_data"}) for node in inner_list]
        for inner_list in data
    ]