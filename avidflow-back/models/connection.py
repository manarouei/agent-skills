from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Literal, Any
from enum import Enum


class ConnectionType(str, Enum):
    """Types of connections between nodes"""
    AIAGENT = 'ai_agent'
    AIMODEL = 'ai_model'
    AICHAIN = 'ai_chain'
    AIDOCUMENT = 'ai_document'
    AIEMBEDDING = 'ai_embedding'
    AILANGUAGEMODEL = 'ai_languageModel'
    AIMEMORY = 'ai_memory'
    AIOUTPUTPARSER = 'ai_outputParser'
    AIRETRIEVER = 'ai_retriever'
    AITEXTSPLITTER = 'ai_textSplitter'
    AITOOL = 'ai_tool'
    AIVECTORSTORE = 'ai_vectorStore'
    MAIN = "main"


class Connection(BaseModel):
    node: str
    type: ConnectionType
    index: int = 0

NodeInputConnections = List[Optional[List[Connection]]]

class NodeConnection(BaseModel):
    source_index: int
    destination_index: int

NodeConnections = Dict[str, NodeInputConnections]

Connections = Dict[str, NodeConnections]
