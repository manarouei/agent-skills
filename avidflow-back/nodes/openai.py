from typing import Dict, List, Optional, Any, Union, Generator
from models import NodeExecutionData
import requests
import time
import json
import base64
import os
import re
import traceback
from utils.serialization import deep_serialize
from .base import *


class OpenAiNode(BaseNode):
    """
    OpenAI node for integration with OpenAI's API services.
    """
    
    type = "openai"
    version = 1.1
    
    description = {
        "displayName": "OpenAI",
        "name": "openAi",
        "group": ["transform"],
        "subtitle": "={{$parameter['operation'] + ': ' + $parameter['resource']}}",
        "description": "Consume OpenAI API",
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "required": True,
                "options": [
                    {
                        "name": "Chat",
                        "value": "chat"
                    },
                    {
                        "name": "Text",
                        "value": "text"
                    },
                    {
                        "name": "Image",
                        "value": "image"
                    },
                    {
                        "name": "Audio",
                        "value": "audio"
                    },
                    {
                        "name": "File",
                        "value": "file"
                    },
                    {
                        "name": "Assistants",
                        "value": "assistants"
                    },
                    {
                        "name": "Batch",
                        "value": "batch"
                    },
                    {
                        "name": "Text to Speech",
                        "value": "tts"
                    }
                ],
                "default": "chat"
            },
            # Chat resource operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "options": [
                    {
                        "name": "Complete",
                        "value": "complete"
                    }
                ],
                "default": "complete"
            },
            # Text resource operations
            {
                "name": "textOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["text"]
                    }
                },
                "options": [
                    {
                        "name": "Complete",
                        "value": "complete"
                    },
                    {
                        "name": "Moderate",
                        "value": "moderate"
                    }
                ],
                "default": "complete"
            },
            # Image resource operations
            {
                "name": "imageOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["image"]
                    }
                },
                "options": [
                    {
                        "name": "Create",
                        "value": "create"
                    },
                    {
                        "name": "Variation",
                        "value": "variation"
                    }
                ],
                "default": "create"
            },
            # Audio resource operations
            {
                "name": "audioOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                },
                "options": [
                    {
                        "name": "Transcribe",
                        "value": "transcribe"
                    },
                    {
                        "name": "Translate",
                        "value": "translate"
                    }
                ],
                "default": "transcribe"
            },
            # File operations
            {
                "name": "fileOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["file"]
                    }
                },
                "options": [
                    {"name": "Upload", "value": "upload"},
                    {"name": "List", "value": "list"},
                    {"name": "Retrieve", "value": "retrieve"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Get Content", "value": "content"}
                ],
                "default": "upload"
            },
            # Chat models
            {
                "name": "chatModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "gpt-4o",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "options": [
                    {"name": "GPT-4o", "value": "gpt-4o"},
                    {"name": "GPT-4o mini", "value": "gpt-4o-mini"},
                    {"name": "GPT-4 Turbo", "value": "gpt-4-turbo"},
                    {"name": "GPT-4", "value": "gpt-4"},
                    {"name": "GPT-3.5 Turbo", "value": "gpt-3.5-turbo"}
                ]
            },
            # Text models
            {
                "name": "textModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "gpt-4o",
                "display_options": {
                    "show": {
                        "resource": ["text"],
                        "textOperation": ["complete"]
                    }
                },
                "options": [
                    {"name": "GPT-4o", "value": "gpt-4o"},
                    {"name": "GPT-4o mini", "value": "gpt-4o-mini"},
                    {"name": "GPT-4 Turbo", "value": "gpt-4-turbo"},
                    {"name": "GPT-3.5 Turbo", "value": "gpt-3.5-turbo"}
                ]
            },
            # Moderation models
            {
                "name": "moderationModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "text-moderation-latest",
                "display_options": {
                    "show": {
                        "resource": ["text"],
                        "textOperation": ["moderate"]
                    }
                },
                "options": [
                    {"name": "Text Moderation Latest", "value": "text-moderation-latest"},
                    {"name": "Text Moderation Stable", "value": "text-moderation-stable"}
                ]
            },
            # Image models
            {
                "name": "imageModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "dall-e-3",
                "display_options": {
                    "show": {
                        "resource": ["image"]
                    }
                },
                "options": [
                    {"name": "DALL-E 3", "value": "dall-e-3"},
                    {"name": "DALL-E 2", "value": "dall-e-2"}
                ]
            },
            # Whisper model parameter
            {
                "name": "whisperModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "whisper-1",
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                },
                "options": [
                    {"name": "Whisper 1", "value": "whisper-1"}
                ]
            },
            # Chat parameters
            {
                "name": "messages",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Messages",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "options": [
                    {
                        "name": "role",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Role",
                        "options": [
                            {"name": "System", "value": "system"},
                            {"name": "User", "value": "user"},
                            {"name": "Assistant", "value": "assistant"}
                        ],
                        "default": "user"
                    },
                    {
                        "name": "content",
                        "type": NodeParameterType.STRING,
                        "display_name": "Content",
                        "default": ""
                    }
                ],
                "typeOptions": {
                    "multipleValues": True
                }
            },
            {
                "name": "systemMessage",
                "type": NodeParameterType.STRING,
                "display_name": "System Message",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                }
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                }
            },
            # Text parameters
            {
                "name": "prompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["text", "image"],
                        "textOperation": ["complete"],
                        "imageOperation": ["create"]
                    }
                }
            },
            {
                "name": "input",
                "type": NodeParameterType.STRING,
                "display_name": "Input",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["text"],
                        "textOperation": ["moderate"]
                    }
                }
            },
            # Image parameters
            {
                "name": "numberOfImages",
                "type": NodeParameterType.NUMBER,
                "display_name": "Number of Images",
                "default": 1,
                "display_options": {
                    "show": {
                        "resource": ["image"]
                    }
                }
            },
            {
                "name": "image",
                "type": NodeParameterType.STRING,
                "display_name": "Image",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["image"],
                        "imageOperation": ["variation"]
                    }
                }
            },
            {
                "name": "responseFormat",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Response Format",
                "default": "url",
                "display_options": {
                    "show": {
                        "resource": ["image"]
                    }
                },
                "options": [
                    {"name": "URL", "value": "url"},
                    {"name": "Binary Data", "value": "b64_json"}
                ]
            },
            # DALL-E 2 image sizes
            {
                "name": "dalleSize",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Size",
                "default": "1024x1024",
                "display_options": {
                    "show": {
                        "resource": ["image"],
                        "imageModel": ["dall-e-2"]
                    }
                },
                "options": [
                    {"name": "256x256", "value": "256x256"},
                    {"name": "512x512", "value": "512x512"},
                    {"name": "1024x1024", "value": "1024x1024"}
                ]
            },
            # DALL-E 3 image sizes
            {
                "name": "dalle3Size",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Size",
                "default": "1024x1024",
                "display_options": {
                    "show": {
                        "resource": ["image"],
                        "imageModel": ["dall-e-3"]
                    }
                },
                "options": [
                    {"name": "1024x1024", "value": "1024x1024"},
                    {"name": "1792x1024", "value": "1792x1024"},
                    {"name": "1024x1792", "value": "1024x1792"}
                ]
            },
            # DALL-E 3 quality
            {
                "name": "quality",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Quality",
                "default": "standard",
                "display_options": {
                    "show": {
                        "resource": ["image"],
                        "imageModel": ["dall-e-3"]
                    }
                },
                "options": [
                    {"name": "Standard", "value": "standard"},
                    {"name": "HD", "value": "hd"}
                ]
            },
            # DALL-E 3 style
            {
                "name": "style",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Style",
                "default": "vivid",
                "display_options": {
                    "show": {
                        "resource": ["image"],
                        "imageModel": ["dall-e-3"]
                    }
                },
                "options": [
                    {"name": "Vivid", "value": "vivid"},
                    {"name": "Natural", "value": "natural"}
                ]
            },
            # Specialized model purposes (informational)
            {
                "name": "modelPurpose",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model Purpose",
                "default": "general",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "options": [
                    {"name": "General Purpose (GPT-4o)", "value": "general"},
                    {"name": "Cost Effective (GPT-4o mini)", "value": "cost-effective"},
                    {"name": "Vision & Images (GPT-4o)", "value": "vision"},
                    {"name": "Coding & Technical (GPT-4o)", "value": "coding"}
                ],
                "description": "Informational only - select the appropriate model above based on your use case"
            },
            # Common parameters
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "maxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Tokens",
                "default": 100,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "frequencyPenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Frequency Penalty",
                "default": 0,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "presencePenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Presence Penalty",
                "default": 0,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "topP",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top P",
                "default": 1,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "n",
                "type": NodeParameterType.NUMBER,
                "display_name": "Number of Completions",
                "default": 1,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"],
                        "textOperation": ["complete"]
                    }
                }
            },
            {
                "name": "simplifyOutput",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Simplify Output",
                "default": True,
                "description": "Whether to return a simplified version of the response"
            },
            # Audio parameters
            {
                "name": "audioFile",
                "type": NodeParameterType.STRING,
                "display_name": "Audio File",
                "description": "Path to audio file, URL, or base64-encoded audio data",
                "default": "https://samplelib.com/lib/preview/mp3/sample-3s.mp3",
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                }
            },
            {
                "name": "language",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Language",
                "description": "Language of the audio file. Default is auto-detect.",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                },
                "options": [
                    {"name": "Auto-detect", "value": ""},
                    {"name": "English", "value": "en"},
                    {"name": "Spanish", "value": "es"},
                    {"name": "French", "value": "fr"},
                    {"name": "German", "value": "de"},
                    {"name": "Chinese", "value": "zh"},
                    {"name": "Japanese", "value": "ja"},
                    {"name": "Russian", "value": "ru"},
                    {"name": "Portuguese", "value": "pt"}
                ]
            },
            {
                "name": "audioResponseFormat",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Response Format",
                "default": "json",
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                },
                "options": [
                    {"name": "JSON", "value": "json"},
                    {"name": "Text", "value": "text"},
                    {"name": "SRT", "value": "srt"},
                    {"name": "VTT", "value": "vtt"},
                    {"name": "Verbose JSON", "value": "verbose_json"}
                ]
            },
            {
                "name": "audioPrompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "description": "Optional text to guide the model's style or continue a previous audio segment",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                }
            },
            {
                "name": "audioTemperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0,
                "display_options": {
                    "show": {
                        "resource": ["audio"]
                    }
                }
            },
            {
                "name": "tools",
                "type": NodeParameterType.JSON,
                "display_name": "Tools (Function Calling)",
                "default": [],
                "display_options": {"show": {"resource": ["chat"], "operation": ["complete"]}},
                "description": "List of tool/function definitions"
            },
            {
                "name": "tool_choice",
                "type": NodeParameterType.STRING,
                "display_name": "Tool Choice",
                "default": "auto",
                "display_options": {"show": {"resource": ["chat"], "operation": ["complete"]}},
                "description": "Which tool to call: 'auto', 'none', or function name"
            },
            {
                "name": "visionImage",
                "type": NodeParameterType.STRING,
                "display_name": "Vision Input Image",
                "display_options": {"show": {"resource": ["chat"], "operation": ["complete"], "chatModel": ["gpt-4o"]}},
                "description": "Image URL, path or base64 for vision"
            },
            # File endpoints
            {
                "name": "fileOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "File Operation",
                "display_options": {"show": {"resource": ["file"]}},
                "options": [{"name": "Upload", "value": "upload"}, {"name": "List", "value": "list"}, {"name": "Retrieve", "value": "retrieve"}, {"name": "Delete", "value": "delete"}, {"name": "Get Content", "value": "content"}]
            },
            {
                "name": "filePath",
                "type": NodeParameterType.STRING,
                "display_name": "File Path",
                "display_options": {"show": {"resource": ["file"], "fileOperation": ["upload"]}},
            },
            {
                "name": "filePurpose",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Purpose",
                "default": "fine-tune",
                "display_options": {
                    "show": {
                        "resource": ["file"],
                        "fileOperation": ["upload"]
                    }
                },
                "options": [
                    {"name": "Fine-tuning", "value": "fine-tune"},
                    {"name": "Assistant", "value": "assistants"}
                ]
            },
            {
                "name": "fileId",
                "type": NodeParameterType.STRING,
                "display_name": "File ID",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["file"],
                        "fileOperation": ["retrieve", "delete", "content"]
                    }
                }
            },
            # Assistants operations
            {
                "name": "assistantsOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["assistants"]
                    }
                },
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Retrieve", "value": "retrieve"},
                    {"name": "List", "value": "list"},
                    {"name": "Update", "value": "update"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Create Thread", "value": "create_thread"},
                    {"name": "Create Message", "value": "create_message"},
                    {"name": "Run Assistant", "value": "run"}
                ],
                "default": "create"
            },
            # Assistants parameters
            {
                "name": "assistantModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "gpt-4o",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create", "update"]
                    }
                },
                "options": [
                    {"name": "GPT-4o", "value": "gpt-4o"},
                    {"name": "GPT-4 Turbo", "value": "gpt-4-turbo"},
                    {"name": "GPT-3.5 Turbo", "value": "gpt-3.5-turbo"}
                ]
            },
            {
                "name": "assistantName",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create", "update"]
                    }
                }
            },
            {
                "name": "assistantInstructions",
                "type": NodeParameterType.STRING,
                "display_name": "Instructions",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create", "update", "run"]
                    }
                }
            },
            {
                "name": "assistantTools",
                "type": NodeParameterType.JSON,
                "display_name": "Tools",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create", "update", "run"]
                    }
                },
                "description": "List of tools (code_interpreter, retrieval, function)"
            },
            {
                "name": "assistantFileIds",
                "type": NodeParameterType.JSON,
                "display_name": "File IDs",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create", "update"]
                    }
                },
                "description": "List of file IDs to attach to the assistant"
            },
            {
                "name": "assistantId",
                "type": NodeParameterType.STRING,
                "display_name": "Assistant ID",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["retrieve", "update", "delete", "run"]
                    }
                }
            },
            {
                "name": "assistantLimit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 20,
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["list"]
                    }
                }
            },
            {
                "name": "assistantOrder",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Order",
                "default": "desc",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["list"]
                    }
                },
                "options": [
                    {"name": "Ascending", "value": "asc"},
                    {"name": "Descending", "value": "desc"}
                ]
            },
            {
                "name": "threadMessages",
                "type": NodeParameterType.JSON,
                "display_name": "Messages",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_thread"]
                    }
                },
                "description": "Initial messages for the thread"
            },
            {
                "name": "threadMetadata",
                "type": NodeParameterType.JSON,
                "display_name": "Metadata",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_thread"]
                    }
                }
            },
            {
                "name": "threadId",
                "type": NodeParameterType.STRING,
                "display_name": "Thread ID",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_message", "run"]
                    }
                }
            },
            {
                "name": "messageRole",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Role",
                "default": "user",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_message"]
                    }
                },
                "options": [
                    {"name": "User", "value": "user"}
                ]
            },
            {
                "name": "messageContent",
                "type": NodeParameterType.STRING,
                "display_name": "Content",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_message"]
                    }
                }
            },
            {
                "name": "messageFileIds",
                "type": NodeParameterType.JSON,
                "display_name": "File IDs",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_message"]
                    }
                }
            },
            {
                "name": "messageMetadata",
                "type": NodeParameterType.JSON,
                "display_name": "Metadata",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["create_message"]
                    }
                }
            },
            {
                "name": "runTools",
                "type": NodeParameterType.JSON,
                "display_name": "Tools",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["run"]
                    }
                }
            },
            {
                "name": "runMetadata",
                "type": NodeParameterType.JSON,
                "display_name": "Metadata",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["assistants"],
                        "assistantsOperation": ["run"]
                    }
                }
            },
            # Batch operations
            {
                "name": "batchOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["batch"]
                    }
                },
                "options": [
                    {"name": "Process", "value": "process"}
                ],
                "default": "process"
            },
            {
                "name": "batchType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Batch Type",
                "default": "chat",
                "display_options": {
                    "show": {
                        "resource": ["batch"]
                    }
                },
                "options": [
                    {"name": "Chat Completions", "value": "chat"}
                ]
            },
            {
                "name": "batchData",
                "type": NodeParameterType.JSON,
                "display_name": "Batch Data",
                "default": [],
                "display_options": {
                    "show": {
                        "resource": ["batch"]
                    }
                },
                "description": "Array of items to process in batch"
            },
            {
                "name": "batchModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "gpt-4o",
                "display_options": {
                    "show": {
                        "resource": ["batch"],
                        "batchType": ["chat"]
                    }
                },
                "options": [
                    {"name": "GPT-4o", "value": "gpt-4o"},
                    {"name": "GPT-4o mini", "value": "gpt-4o-mini"},
                    {"name": "GPT-4 Turbo", "value": "gpt-4-turbo"},
                    {"name": "GPT-3.5 Turbo", "value": "gpt-3.5-turbo"}
                ]
            },
            {
                "name": "batchTemperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "display_options": {
                    "show": {
                        "resource": ["batch"]
                    }
                }
            },
            {
                "name": "batchMaxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Tokens",
                "default": 100,
                "display_options": {
                    "show": {
                        "resource": ["batch"]
                    }
                }
            },
            # TTS operations
            {
                "name": "ttsOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                },
                "options": [
                    {"name": "Generate", "value": "generate"}
                ],
                "default": "generate"
            },
            {
                "name": "ttsModel",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "default": "tts-1",
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                },
                "options": [
                    {"name": "TTS-1", "value": "tts-1"},
                    {"name": "TTS-1 HD", "value": "tts-1-hd"}
                ]
            },
            {
                "name": "ttsInput",
                "type": NodeParameterType.STRING,
                "display_name": "Input Text",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                }
            },
            {
                "name": "ttsVoice",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Voice",
                "default": "alloy",
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                },
                "options": [
                    {"name": "Alloy", "value": "alloy"},
                    {"name": "Echo", "value": "echo"},
                    {"name": "Fable", "value": "fable"},
                    {"name": "Onyx", "value": "onyx"},
                    {"name": "Nova", "value": "nova"},
                    {"name": "Shimmer", "value": "shimmer"}
                ]
            },
            {
                "name": "ttsResponseFormat",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Response Format",
                "default": "mp3",
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                },
                "options": [
                    {"name": "MP3", "value": "mp3"},
                    {"name": "Opus", "value": "opus"},
                    {"name": "AAC", "value": "aac"},
                    {"name": "FLAC", "value": "flac"}
                ]
            },
            {
                "name": "ttsSpeed",
                "type": NodeParameterType.NUMBER,
                "display_name": "Speed",
                "default": 1.0,
                "display_options": {
                    "show": {
                        "resource": ["tts"]
                    }
                }
            },
            # Add streaming support parameter
            {
                "name": "stream",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Stream Response",
                "default": False,
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "description": "Whether to stream the response in real-time"
            }
        ],
        "credentials": [
            {
                "name": "openAiApi",
                "required": True
            }
        ]
    }
    

    icon = "file:openAi.svg"
    color = "#404040"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute OpenAI node operations"""
        
        try:
            # Get parameters
            resource = self.get_node_parameter("resource", 0, "chat")
            # Get operation based on resource
            operation = self._get_operation_for_resource(resource)

            input_data = self.get_input_data()
            
            # Pre-process parameters with expressions
            try:
                self._process_parameters_expressions(input_data)
            except Exception as e:
                traceback.print_exc()
 
            result = self._process_resource_operation(resource, operation, input_data)

            # Check if result contains an error
            if isinstance(result, dict) and "error" in result:
                return self._prepare_error_data(result["error"])

            # Serialize the result for proper JSON handling
            serialized_result = deep_serialize(result)
            return [[NodeExecutionData(json_data=serialized_result)]]

        except Exception as e:
            traceback.print_exc()
            return self._prepare_error_data(f"Error executing OpenAI node: {str(e)}")

    def _get_operation_for_resource(self, resource):
        """Get the appropriate operation for the given resource"""
        if resource == "chat":
            return self.get_node_parameter("operation", 0, "complete")
        elif resource == "text":
            return self.get_node_parameter("textOperation", 0, "complete")
        elif resource == "image":
            return self.get_node_parameter("imageOperation", 0, "create")
        elif resource == "audio":
            return self.get_node_parameter("audioOperation", 0, "transcribe")
        elif resource == "file":
            return self.get_node_parameter("fileOperation", 0, "upload")
        elif resource == "assistants":
            return self.get_node_parameter("assistantsOperation", 0, "create")
        elif resource == "batch":
            return self.get_node_parameter("batchOperation", 0, "process")
        elif resource == "tts":
            return self.get_node_parameter("ttsOperation", 0, "generate")
        else:
            return "complete"

    def _process_resource_operation(self, resource, operation, input_data):
        """Process the requested resource operation"""
        try:
            if resource == "chat":
                return self._process_chat(operation, input_data)
            elif resource == "text":
                return self._process_text(operation, input_data)
            elif resource == "image":
                return self._process_image(operation, input_data)
            elif resource == "audio":
                return self._process_audio(operation, input_data)
            elif resource == "file":
                return self._process_file(operation, input_data)
            elif resource == "assistants":
                return self._process_assistants(operation, input_data)
            elif resource == "batch":
                return self._process_batch(operation, input_data)
            elif resource == "tts":
                return self._process_tts(operation, input_data)
            else:
                return {"error": f"Resource {resource} is not supported"}
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing {resource}.{operation}: {str(e)}"}

    def _prepare_error_data(self, error_message: str) -> List[List[NodeExecutionData]]:
        """Create error data structure for failed OpenAI executions"""
        return [[NodeExecutionData(json_data={"error": error_message})]]

    def _safe_get_node_data(self, node_name, path=None, default=None):
        """
        Safely get data from another node with robust error handling
        
        Args:
            node_name: Name of the node to get data from
            path: Dot-notation path to the specific property (e.g., "data.0.content")
            default: Default value to return if data not found
            
        Returns:
            The requested data or default value
        """
        try:
            # First attempt: Try direct lookup through workflow_context if available
            if hasattr(self, 'workflow_context') and self.workflow_context:
                if 'node_data' in self.workflow_context and node_name in self.workflow_context['node_data']:
                    node_data = self.workflow_context['node_data'][node_name]          
                    if node_data and len(node_data) > 0:
                        first_item = node_data[0]
                        
                        # Extract JSON data
                        if isinstance(first_item, dict) and 'json_data' in first_item:
                            json_data = first_item['json_data']
                        elif hasattr(first_item, 'json_data'):
                            json_data = first_item.json_data
                        elif isinstance(first_item, dict) and 'json' in first_item:
                            json_data = first_item['json']
                        elif hasattr(first_item, 'json'):
                            json_data = first_item.json
                        else:
                            json_data = first_item
                            
                        # Return full data if no path specified
                        if not path:
                            return json_data
                            
                        # Navigate path
                        if isinstance(json_data, dict) and 'data' in json_data and isinstance(json_data['data'], list) and len(json_data['data']) > 0:
                            if path == 'data.0.content' and 'content' in json_data['data'][0]:
                                return json_data['data'][0]['content']
        
            # Second attempt: Use the get_node_data method
            try:
                node_data = self.get_node_data(node_name)
                if node_data and len(node_data) > 0:
                    # Inspect the structure
                    first_item = node_data[0]
                    
                    # Extract JSON data
                    json_data = None
                    if hasattr(first_item, 'json_data'):
                        json_data = first_item.json_data
                    elif hasattr(first_item, 'json'):
                        json_data = first_item.json
                    elif isinstance(first_item, dict) and 'json_data' in first_item:
                        json_data = first_item['json_data']
                    elif isinstance(first_item, dict) and 'json' in first_item:
                        json_data = first_item['json']
                    else:
                        json_data = first_item
                    
                    # Return full data if no path specified
                    if not path:
                        return json_data
                    
                    # Common path pattern: data.0.content
                    if path == 'data.0.content' and isinstance(json_data, dict) and 'data' in json_data:
                        if isinstance(json_data['data'], list) and len(json_data['data']) > 0:
                            if 'content' in json_data['data'][0]:
                                return json_data['data'][0]['content']
            except Exception:
                pass
        
            return default
        
        except Exception:
            traceback.print_exc()
            return default

    def _process_parameters_expressions(self, input_data):
        """Process all parameter expressions before execution with enhanced fallbacks"""
        resource = self.get_node_parameter("resource", 0)
        
        try:
            # Special handling for text resource with completion operation
            if resource == "text" and self.get_node_parameter("textOperation", 0) == "complete":
                # Check if we need to process prompt parameter
                prompt_param = self.get_node_parameter("prompt", 0, "")
                
                if "$node[" in prompt_param and ".json[\"data\"][0][\"content\"]" in prompt_param:
                    # Extract node name
                    match = re.search(r'\$node\["([^"]+)"\]', prompt_param)
                    if match:
                        node_name = match.group(1)
                        
                        # Try to get content directly using our helper
                        content = self._safe_get_node_data(node_name, "data.0.content", None)
                        
                        if content:
                            # Create the final prompt with the extracted content
                            if prompt_param.startswith('{{"'):
                                # Extract the prefix part
                                prefix = ""
                                if " + " in prompt_param:
                                    prefix_part = prompt_param.split(" + ")[0]
                                    if prefix_part.startswith("{{\"") and prefix_part.endswith("\"}}"):
                                        prefix = prefix_part[3:-3]  # Remove {{ and }}
                            
                            final_prompt = f"{prefix}{content}"
                            self.node_parameters["prompt"] = final_prompt
                        # Remove this fallback entirely
                        # else:
                        #    self.node_parameters["prompt"] = "Generate a short story about artificial intelligence and its impact on society."
            
            # Special handling for image resource with create operation
            elif resource == "image" and self.get_node_parameter("imageOperation", 0) == "create":
                # Check if we need to process prompt parameter
                prompt_param = self.get_node_parameter("prompt", 0, "")
                
                if "$node[" in prompt_param and ".json[\"data\"][0][\"content\"]" in prompt_param:
                    
                    # Extract node name
                    match = re.search(r'\$node\["([^"]+)"\]', prompt_param)
                    if match:
                        node_name = match.group(1)
                        # Try to get content directly using our helper
                        content = self._safe_get_node_data(node_name, "data.0.content", None)
                        
                        if content:
                            # Create the final prompt with the extracted content
                            if prompt_param.startswith('{{"'):
                                # Extract the prefix part
                                prefix = ""
                                if " + " in prompt_param:
                                    prefix_part = prompt_param.split(" + ")[0]
                                    if prefix_part.startswith("{{\"") and prefix_part.endswith("\"}}"):
                                        prefix = prefix_part[3:-3]  # Remove {{ and }}
                        
                        final_prompt = f"{prefix}{content}"
                        self.node_parameters["prompt"] = final_prompt
                    # Remove this fallback entirely
                    # else:
                    #    self.node_parameters["prompt"] = "A creative visualization of artificial intelligence with digital neurons and connections."
    
            # Special handling for TTS resource
            elif resource == "tts":
                # Check if we need to process ttsInput parameter
                tts_input_param = self.get_node_parameter("ttsInput", 0, "")
                
                if "$node[" in tts_input_param and ".json[\"data\"][0][\"content\"]" in tts_input_param:
                    # Extract node name
                    match = re.search(r'\$node\["([^"]+)"\]', tts_input_param)
                    if match:
                        node_name = match.group(1)
                        
                        # Try to get content directly using our helper
                        content = self._safe_get_node_data(node_name, "data.0.content", None)
                        
                        if content:
                            self.node_parameters["ttsInput"] = content
                        # Remove this fallback entirely
                        # else:
                        #    self.node_parameters["ttsInput"] = "This is a text to speech sample about artificial intelligence and its potential."
            
        except Exception:
            traceback.print_exc()

    def _process_chat(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle chat operations with support for function calling"""
        try:
            if operation == "complete":
                # Get credentials
                credentials = self.get_credentials("openAiApi")
                
                if not credentials:
                    return {"error": "No credentials found. Please set up OpenAI API credentials."}

                # Extract API key and base URL
                api_key = credentials.get("apiKey")
                base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

                if not api_key:
                    return {"error": "API key is required for OpenAI integration"}

                # Prepare headers
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # Add organization header if provided
                if credentials.get("organizationId"):
                    headers["OpenAI-Organization"] = credentials["organizationId"]
                
                # Get parameters
                model = self.get_node_parameter("chatModel", 0, "gpt-4o")
                temperature = self.get_node_parameter("temperature", 0, 0.7)
                max_tokens = self.get_node_parameter("maxTokens", 0, 100)
                frequency_penalty = self.get_node_parameter("frequencyPenalty", 0, 0)
                presence_penalty = self.get_node_parameter("presencePenalty", 0, 0)
                top_p = self.get_node_parameter("topP", 0, 1)
                n = self.get_node_parameter("n", 0, 1)
                simplify_output = self.get_node_parameter("simplifyOutput", 0, True)
                stream = self.get_node_parameter("stream", 0, False)
                
                # Prepare messages
                messages = []
                
                # Add system message if provided
                system_message = self.get_node_parameter("systemMessage", 0, "")
                if system_message:
                    messages.append({
                        "role": "system",
                        "content": system_message
                    })
                
                # Add messages from collection if available
                collection_messages = self.get_node_parameter("messages", 0, [])
                if isinstance(collection_messages, list):
                    for msg in collection_messages:
                        if isinstance(msg, dict) and "role" in msg and "content" in msg:
                            messages.append({
                                "role": msg["role"],
                                "content": msg["content"]
                            })
                
                # Add user message if provided
                message_content = self.get_node_parameter("message", 0, "")
                if message_content:
                    messages.append({
                        "role": "user",
                        "content": message_content
                    })
                
                # If no messages are provided, add a default user message
                if not messages:
                    messages.append({
                        "role": "user",
                        "content": "Hello"
                    })
                
                # Check for tools/functions
                tools = self.get_node_parameter("tools", 0, [])
                tool_choice = self.get_node_parameter("tool_choice", 0, "auto")
                
                # Check for vision image
                vision_image = self.get_node_parameter("visionImage", 0, "")
                
                # Add vision image to messages if provided
                if vision_image and model in ["gpt-4o", "gpt-4-vision"]:
                    # Find the last user message or create one
                    user_message_found = False
                    for i in range(len(messages) - 1, -1, -1):
                        if messages[i]["role"] == "user":
                            # If vision model is used, convert the content to multimodal format
                            if isinstance(messages[i]["content"], str):
                                messages[i]["content"] = [
                                    {"type": "text", "text": messages[i]["content"]},
                                    {"type": "image_url", "image_url": {"url": vision_image}}
                                ]
                            elif isinstance(messages[i]["content"], list):
                                messages[i]["content"].append({"type": "image_url", "image_url": {"url": vision_image}})
                            user_message_found = True
                            break
                    
                    if not user_message_found:
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What's in this image?"},
                                {"type": "image_url", "image_url": {"url": vision_image}}
                            ]
                        })
                
                # Prepare request data
                data = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                    "top_p": top_p,
                    "n": n
                }
                
                # Add tools if provided
                if tools and len(tools) > 0:
                    if isinstance(tools, dict):
                        tools = [tools]
                    data["tools"] = tools
                    
                    # Add tool_choice if specified
                    if tool_choice != "auto":
                        if tool_choice == "none":
                            data["tool_choice"] = "none"
                        else:
                            try:
                                if isinstance(tool_choice, str) and tool_choice.startswith("{"):
                                    # Parse JSON string
                                    tool_choice_obj = json.loads(tool_choice)
                                    data["tool_choice"] = tool_choice_obj
                                else:
                                    # Use simple function name
                                    data["tool_choice"] = {"type": "function", "function": {"name": tool_choice}}
                            except:
                                # Default to auto if parsing fails
                                data["tool_choice"] = "auto"
                
                # Make API request
                try:
                    if stream:
                        # Handle streaming response
                        data["stream"] = True
                        chunks = []
                        full_content = ""
                        tool_calls_data = []
                        
                        # Stream the response
                        response = requests.post(
                            f"{base_url}/chat/completions",
                            headers=headers,
                            json=data,
                            stream=True
                        )
                        
                        if response.status_code >= 400:
                            return {"error": f"OpenAI API error: {response.text}"}
                        
                        for line in response.iter_lines():
                            if not line:
                                continue
                            
                            line = line.decode('utf-8')
                            if line.startswith('data: '):
                                line = line[6:]  # Remove 'data: ' prefix
                            
                            if line == '[DONE]':
                                break
                                
                            try:
                                chunk = json.loads(line)
                                chunks.append(chunk)
                                
                                # Extract content and tool calls
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    choice = chunk['choices'][0]
                                    delta = choice.get('delta', {})
                                    
                                    # Add content
                                    if 'content' in delta and delta['content']:
                                        full_content += delta['content']
                                    
                                    # Process tool calls
                                    if 'tool_calls' in delta:
                                        for tool_call in delta['tool_calls']:
                                            if len(tool_calls_data) <= tool_call.get('index', 0):
                                                tool_calls_data.append({
                                                    "id": tool_call.get('id', ''),
                                                    "type": tool_call.get('type', 'function'),
                                                    "function": {
                                                        "name": "",
                                                        "arguments": ""
                                                    }
                                                })
                                            
                                            current_tool = tool_calls_data[tool_call.get('index', 0)]
                                            
                                            if 'id' in tool_call:
                                                current_tool['id'] = tool_call['id']
                                            
                                            if 'function' in tool_call:
                                                function_data = tool_call['function']
                                                if 'name' in function_data:
                                                    current_tool['function']['name'] = function_data['name']
                                                if 'arguments' in function_data:
                                                    current_tool['function']['arguments'] += function_data['arguments']
                            except json.JSONDecodeError:
                                continue
                        
                        # Construct final result
                        return {
                            "content": full_content,
                            "tool_calls": tool_calls_data
                        }
                    else:
                        # Regular non-streaming request
                        response = requests.post(
                            f"{base_url}/chat/completions",
                            headers=headers,
                            json=data
                        )
                        
                        if response.status_code >= 400:
                            return {"error": f"OpenAI API error: {response.text}"}
                            
                        result = response.json()
                        
                        # Process the result based on simplify_output setting
                        if simplify_output:
                            choices = result.get("choices", [])
                            first_choice = choices[0] if choices else {}
                            message = first_choice.get("message", {})
                            
                            # Extract content
                            content = message.get("content", "")
                            
                            # Extract tool calls if available
                            tool_calls = message.get("tool_calls", [])
                            
                            # Format the result
                            response_data = {
                                "content": content,
                                "model": result.get("model", model),
                                "tool_calls": tool_calls
                            }
                            
                            # Add usage data if available
                            if "usage" in result:
                                response_data["usage"] = result["usage"]
                            
                            return response_data
                        else:
                            return result
                                
                except Exception as e:
                    traceback.print_exc()
                    return {"error": f"Error in chat completion: {str(e)}"}
            
            return {"error": f"Operation {operation} is not supported for chat resource"}
                
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing chat: {str(e)}"}

    def _process_text(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle text operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}

            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Add organization header if provided
            if credentials.get("organizationId"):
                headers["OpenAI-Organization"] = credentials["organizationId"]
            
            # Get common parameters
            simplify_output = self.get_node_parameter("simplifyOutput", 0, True)
            
            if operation == "complete":
                # Get parameters for text completion
                model = self.get_node_parameter("textModel", 0, "gpt-4o")
                prompt = self.get_node_parameter("prompt", 0, "")
                max_tokens = self.get_node_parameter("maxTokens", 0, 100)
                temperature = self.get_node_parameter("temperature", 0, 0.7)
                frequency_penalty = self.get_node_parameter("frequencyPenalty", 0, 0)
                presence_penalty = self.get_node_parameter("presencePenalty", 0, 0)
                top_p = self.get_node_parameter("topP", 0, 1)
                n = self.get_node_parameter("n", 0, 1)
                
                # Use chat completions API with messages format instead of legacy completions
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                    "top_p": top_p,
                    "n": n
                }
                
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=data
                )
                
                # Process chat completions response for text mode
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}

                result = response.json()
                
                if simplify_output:
                    choices = result.get("choices", [])
                    response_data = []
                    
                    for choice in choices:
                        message = choice.get("message", {})
                        response_data.append({
                            "text": message.get("content", ""),
                            "index": choice.get("index", 0)
                        })
                    
                    # Add usage data if available
                    final_result = {"data": response_data}
                    if "usage" in result:
                        final_result["usage"] = result["usage"]
                    
                    return final_result
                else:
                    return result
            
            elif operation == "moderate":
                # Get parameters for content moderation
                model = self.get_node_parameter("moderationModel", 0, "text-moderation-latest")
                input_text = self.get_node_parameter("input", 0, "")
                
                data = {
                    "model": model,
                    "input": input_text
                }
                
                response = requests.post(
                    f"{base_url}/moderations",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}

                result = response.json()
                
                if simplify_output:
                    # Extract the useful parts of the moderation result
                    results = result.get("results", [])
                    response_data = []
                    
                    for item in results:
                        flagged = item.get("flagged", False)
                        categories = item.get("categories", {})
                        category_scores = item.get("category_scores", {})
                        
                        response_data.append({
                            "flagged": flagged,
                            "categories": categories,
                            "scores": category_scores
                        })
                    
                    return {"data": response_data}
                else:
                    return result
                
            return {"error": f"Operation {operation} is not supported for text resource"}
        
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing text: {str(e)}"}

    def _process_image(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle image operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}

            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Add organization header if provided
            if credentials.get("organizationId"):
                headers["OpenAI-Organization"] = credentials["organizationId"]
                
            if operation == "create":
                # Get parameters
                model = self.get_node_parameter("imageModel", 0, "dall-e-2")
                prompt = self.get_node_parameter("prompt", 0, "")
                response_format = self.get_node_parameter("responseFormat", 0, "url")
                
                # Get size based on the model
                if model == "dall-e-2":
                    size = self.get_node_parameter("dalleSize", 0, "1024x1024")
                else:
                    size = self.get_node_parameter("dalle3Size", 0, "1024x1024")
                    
                num_images = self.get_node_parameter("numberOfImages", 0, 1)
                
                # Prepare request data
                data = {
                    "model": model,
                    "prompt": prompt,
                    "n": num_images,
                    "size": size,
                    "response_format": response_format
                }
                
                # Add DALL-E 3 specific parameters
                if model == "dall-e-3":
                    quality = self.get_node_parameter("quality", 0, "standard")
                    style = self.get_node_parameter("style", 0, "vivid")
                    data["quality"] = quality
                    data["style"] = style
                
                response = requests.post(
                    f"{base_url}/images/generations",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}

                result = response.json()
                
                # Return processed result
                return {"data": result.get("data", [])}
                
            elif operation == "variation":
                # Get parameters
                image = self.get_node_parameter("image", 0, "")
                response_format = self.get_node_parameter("responseFormat", 0, "url")
                
                if not image:
                    return {"error": "Image is required for variation"}
                
                # Handle image input
                image_data = None
                if image.startswith(('http://', 'https://')):
                    # Download image from URL
                    try:
                        image_response = requests.get(image)
                        if image_response.status_code != 200:
                            return {"error": f"Failed to download image: HTTP {image_response.status_code}"}
                        image_data = base64.b64encode(image_response.content).decode('utf-8')
                    except requests.exceptions.RequestException as e:
                        return {"error": f"Error downloading image: {str(e)}"}
                elif image.startswith('data:image'):
                    # Extract base64 content
                    try:
                        image_data = image.split(',')[1]
                    except IndexError:
                        return {"error": "Invalid base64 image format"}
                elif os.path.exists(image):
                    # Read from file
                    try:
                        with open(image, 'rb') as f:
                            image_data = base64.b64encode(f.read()).decode('utf-8')
                    except Exception as e:
                        return {"error": f"Error reading image file: {str(e)}"}
                else:
                    return {"error": "Invalid image source. Provide a URL, base64 string, or file path."}
                
                # Prepare multipart form data
                files = {
                    'image': ('image.png', base64.b64decode(image_data), 'image/png')
                }
                
                data = {
                    'n': self.get_node_parameter("numberOfImages", 0, 1),
                    'size': self.get_node_parameter("dalleSize", 0, "1024x1024"),
                    'response_format': response_format
                }
                
                # Make API request
                response = requests.post(
                    f"{base_url}/images/variations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files=files,
                    data=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}

                result = response.json()
                
                # Return processed result
                return {"data": result.get("data", [])}
                
            return {"error": f"Operation {operation} is not supported for image resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing image: {str(e)}"}

    def _process_audio(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle audio operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}
                
            # Get parameters
            model = self.get_node_parameter("whisperModel", 0, "whisper-1")
            audio_file = self.get_node_parameter("audioFile", 0, "")
            language = self.get_node_parameter("language", 0, "")
            response_format = self.get_node_parameter("audioResponseFormat", 0, "json")
            prompt = self.get_node_parameter("audioPrompt", 0, "")
            temperature = self.get_node_parameter("audioTemperature", 0, 0)
            
            if not audio_file:
                return {"error": "Audio file is required"}
                
            # Handle audio file input
            audio_data = None
            if audio_file.startswith(('http://', 'https://')):
                # Download audio from URL
                try:
                    audio_response = requests.get(audio_file, timeout=10)
                    
                    if audio_response.status_code == 404:
                        return {"error": f"Audio file not found at URL: {audio_file}. Please provide a valid audio URL."}
                    elif audio_response.status_code != 200:
                        return {"error": f"Failed to download audio: HTTP {audio_response.status_code}"}
                        
                    audio_data = audio_response.content
                except requests.exceptions.RequestException as e:
                    return {"error": f"Network error downloading audio: {str(e)}"}
            elif audio_file.startswith('data:audio') or audio_file.startswith('data:application'):
                # Extract base64 content
                try:
                    audio_data = base64.b64decode(audio_file.split(',')[1])
                except Exception as e:
                    return {"error": f"Error processing base64 audio: {str(e)}"}
            elif os.path.exists(audio_file):
                # Read from file
                try:
                    with open(audio_file, 'rb') as f:
                        audio_data = f.read()
                except Exception as e:
                    return {"error": f"Error reading audio file: {str(e)}"}
            else:
                return {"error": "Invalid audio source. Provide a URL, base64 string, or file path."}
                
            # Determine operation
            endpoint = ""
            if operation == "transcribe":
                endpoint = "transcriptions"
            elif operation == "translate":
                endpoint = "translations"
            else:
                return {"error": f"Unsupported audio operation: {operation}"}
                
            # Prepare form data
            files = {
                'file': ('audio.mp3', audio_data, 'audio/mpeg')
            }
            
            data = {
                'model': model,
                'response_format': response_format
            }
            
            if language:
                data['language'] = language
                
            if prompt:
                data['prompt'] = prompt
                
            if temperature is not None:
                data['temperature'] = temperature
                
            # Make API request
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            response = requests.post(
                f"{base_url}/audio/{endpoint}",
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code >= 400:
                return {"error": f"OpenAI API error: {response.text}"}
                
            # Handle different response formats
            if response_format == "json" or response_format == "verbose_json":
                result = response.json()
                return result
            else:
                # For text, srt, vtt
                return {"text": response.text, "usage": {"type": "duration", "seconds": len(audio_data) // 16000}}
                
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing audio: {str(e)}"}

    def _process_file(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle file operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}
                
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            # Add organization header if provided
            if credentials.get("organizationId"):
                headers["OpenAI-Organization"] = credentials["organizationId"]
                
            if operation == "list":
                # List files
                response = requests.get(
                    f"{base_url}/files",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "upload":
                # Upload a file
                file_path = self.get_node_parameter("filePath", 0, "")
                purpose = self.get_node_parameter("filePurpose", 0, "fine-tune")
                
                if not file_path:
                    return {"error": "File path is required"}
                
                # Check if file exists
                if not os.path.exists(file_path):
                    return {"error": f"File not found: {file_path}"}
                
                # Prepare multipart form data
                files = {
                    'file': (os.path.basename(file_path), open(file_path, 'rb'))
                }
                
                data = {
                    'purpose': purpose
                }
                
                # Make API request
                response = requests.post(
                    f"{base_url}/files",
                    headers=headers,
                    files=files,
                    data=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "retrieve":
                # Retrieve file info
                file_id = self.get_node_parameter("fileId", 0, "")
                
                if not file_id:
                    return {"error": "File ID is required"}
                    
                # Make API request
                response = requests.get(
                    f"{base_url}/files/{file_id}",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "delete":
                # Delete a file
                file_id = self.get_node_parameter("fileId", 0, "")
                
                if not file_id:
                    return {"error": "File ID is required"}
                    
                # Make API request
                response = requests.delete(
                    f"{base_url}/files/{file_id}",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "content":
                # Get file content
                file_id = self.get_node_parameter("fileId", 0, "")
                
                if not file_id:
                    return {"error": "File ID is required"}
                    
                # Make API request
                response = requests.get(
                    f"{base_url}/files/{file_id}/content",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                # Try to parse as JSON, fall back to text
                try:
                    result = response.json()
                    return {"content": result}
                except:
                    return {"content": response.text}
                
            return {"error": f"Operation {operation} is not supported for file resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing file: {str(e)}"}

    def _process_assistants(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle assistants operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}
                
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "assistants=v1"
            }
            
            # Add organization header if provided
            if credentials.get("organizationId"):
                headers["OpenAI-Organization"] = credentials["organizationId"]
                
            if operation == "create":
                # Create an assistant
                model = self.get_node_parameter("assistantModel", 0, "gpt-4o")
                name = self.get_node_parameter("assistantName", 0, "")
                instructions = self.get_node_parameter("assistantInstructions", 0, "")
                tools = self.get_node_parameter("assistantTools", 0, [])
                file_ids = self.get_node_parameter("assistantFileIds", 0, [])
                
                # Prepare request data
                data = {
                    "model": model
                }
                
                if name:
                    data["name"] = name
                
                if instructions:
                    data["instructions"] = instructions
                
                if tools:
                    data["tools"] = tools
                
                if file_ids:
                    data["file_ids"] = file_ids
                
                # Make API request
                response = requests.post(
                    f"{base_url}/assistants",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "retrieve":
                # Retrieve an assistant
                assistant_id = self.get_node_parameter("assistantId", 0, "")
                
                if not assistant_id:
                    return {"error": "Assistant ID is required"}
                    
                # Make API request
                response = requests.get(
                    f"{base_url}/assistants/{assistant_id}",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "list":
                # List assistants
                limit = self.get_node_parameter("assistantLimit", 0, 20)
                order = self.get_node_parameter("assistantOrder", 0, "desc")
                
                # Make API request
                response = requests.get(
                    f"{base_url}/assistants?limit={limit}&order={order}",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "update":
                # Update an assistant
                assistant_id = self.get_node_parameter("assistantId", 0, "")
                
                if not assistant_id:
                    return {"error": "Assistant ID is required"}
                    
                model = self.get_node_parameter("assistantModel", 0, "")
                name = self.get_node_parameter("assistantName", 0, "")
                instructions = self.get_node_parameter("assistantInstructions", 0, "")
                tools = self.get_node_parameter("assistantTools", 0, [])
                file_ids = self.get_node_parameter("assistantFileIds", 0, [])
                
                # Prepare request data
                data = {}
                
                if model:
                    data["model"] = model
                
                if name:
                    data["name"] = name
                
                if instructions:
                    data["instructions"] = instructions
                
                if tools:
                    data["tools"] = tools
                
                if file_ids:
                    data["file_ids"] = file_ids
                
                # Make API request
                response = requests.post(
                    f"{base_url}/assistants/{assistant_id}",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "delete":
                # Delete an assistant
                assistant_id = self.get_node_parameter("assistantId", 0, "")
                
                if not assistant_id:
                    return {"error": "Assistant ID is required"}
                    
                # Make API request
                response = requests.delete(
                    f"{base_url}/assistants/{assistant_id}",
                    headers=headers
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "create_thread":
                # Create a thread
                messages = self.get_node_parameter("threadMessages", 0, [])
                metadata = self.get_node_parameter("threadMetadata", 0, {})
                
                # Prepare request data
                data = {}
                
                if messages:
                    data["messages"] = messages
                
                if metadata:
                    data["metadata"] = metadata
                
                # Make API request
                response = requests.post(
                    f"{base_url}/threads",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "create_message":
                # Create a message in a thread
                thread_id = self.get_node_parameter("threadId", 0, "")
                
                if not thread_id:
                    return {"error": "Thread ID is required"}
                    
                role = self.get_node_parameter("messageRole", 0, "user")
                content = self.get_node_parameter("messageContent", 0, "")
                file_ids = self.get_node_parameter("messageFileIds", 0, [])
                metadata = self.get_node_parameter("messageMetadata", 0, {})
                
                # Prepare request data
                data = {
                    "role": role,
                    "content": content
                }
                
                if file_ids:
                    data["file_ids"] = file_ids
                
                if metadata:
                    data["metadata"] = metadata
                
                # Make API request
                response = requests.post(
                    f"{base_url}/threads/{thread_id}/messages",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            elif operation == "run":
                # Run an assistant
                thread_id = self.get_node_parameter("threadId", 0, "")
                assistant_id = self.get_node_parameter("assistantId", 0, "")
                
                if not thread_id:
                    return {"error": "Thread ID is required"}
                    
                if not assistant_id:
                    return {"error": "Assistant ID is required"}
                    
                instructions = self.get_node_parameter("assistantInstructions", 0, "")
                tools = self.get_node_parameter("runTools", 0, [])
                metadata = self.get_node_parameter("runMetadata", 0, {})
                
                # Prepare request data
                data = {
                    "assistant_id": assistant_id
                }
                
                if instructions:
                    data["instructions"] = instructions
                
                if tools:
                    data["tools"] = tools
                
                if metadata:
                    data["metadata"] = metadata
                
                # Make API request
                response = requests.post(
                    f"{base_url}/threads/{thread_id}/runs",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                    
                result = response.json()
                return result
                
            return {"error": f"Operation {operation} is not supported for assistants resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing assistants: {str(e)}"}

    def _process_batch(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle batch operations"""
        try:
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            
            if not credentials:
                return {"error": "No credentials found. Please set up OpenAI API credentials."}

            # Extract API key and base URL
            api_key = credentials.get("apiKey")
            base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

            if not api_key:
                return {"error": "API key is required for OpenAI integration"}

            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Add organization header if provided
            if credentials.get("organizationId"):
                headers["OpenAI-Organization"] = credentials["organizationId"]
                
            if operation == "process":
                # Process batch items
                batch_type = self.get_node_parameter("batchType", 0, "chat")
                batch_data = self.get_node_parameter("batchData", 0, [])
                
                if not batch_data or not isinstance(batch_data, list):
                    return {"error": "Batch data must be a non-empty array"}
                
                # Get batch parameters based on type
                if batch_type == "chat":
                    model = self.get_node_parameter("batchModel", 0, "gpt-4o")
                    temperature = self.get_node_parameter("batchTemperature", 0, 0.7)
                    max_tokens = self.get_node_parameter("batchMaxTokens", 0, 100)
                    
                    # Process each batch item
                    results = []
                    for item in batch_data:
                        # Skip invalid items
                        if not isinstance(item, dict) or "messages" not in item:
                            results.append({"error": "Invalid batch item format. Must contain 'messages' array."})
                            continue
                        
                        # Prepare request data
                        messages = item.get("messages", [])
                        system_message = item.get("systemMessage", "")
                        
                        # Add system message if provided
                        all_messages = []
                        if system_message:
                            all_messages.append({
                                "role": "system",
                                "content": system_message
                            })
                        
                        # Add regular messages
                        all_messages.extend(messages)
                        
                        data = {
                            "model": model,
                            "messages": all_messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }
                        
                        # Make API request
                        try:
                            response = requests.post(
                                f"{base_url}/chat/completions",
                                headers=headers,
                                json=data
                            )
                            
                            if response.status_code >= 400:
                                results.append({"error": f"OpenAI API error: {response.text}"})
                                continue
                                
                            result = response.json()
                            
                            # Process result
                            choice = result.get("choices", [{}])[0]
                            message = choice.get("message", {})
                            content = message.get("content", "")
                            
                            # Create simplified result
                            processed_result = {
                                "content": content,
                                "finish_reason": choice.get("finish_reason", ""),
                                "original_item": item
                            }
                            
                            results.append(processed_result)
                            
                        except Exception as e:
                            results.append({"error": f"Error processing batch item: {str(e)}"})
                    
                    return {"results": results}
                
                return {"error": f"Batch type {batch_type} is not supported"}
            
            return {"error": f"Operation {operation} is not supported for batch resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing batch: {str(e)}"}

    def _process_tts(self, operation: str, input_data: List[NodeExecutionData]) -> Dict:
        """Handle text-to-speech operations"""
        try:
            if operation == "generate":
                # Get credentials
                credentials = self.get_credentials("openAiApi")
                
                if not credentials:
                    return {"error": "No credentials found. Please set up OpenAI API credentials."}

                # Extract API key and base URL
                api_key = credentials.get("apiKey")
                base_url = credentials.get("baseUrl", "https://api.openai.com/v1")

                if not api_key:
                    return {"error": "API key is required for OpenAI integration"}
                
                # Get parameters
                model = self.get_node_parameter("ttsModel", 0, "tts-1")
                input_text = self.get_node_parameter("ttsInput", 0, "")
                voice = self.get_node_parameter("ttsVoice", 0, "alloy")
                response_format = self.get_node_parameter("ttsResponseFormat", 0, "mp3")
                speed = self.get_node_parameter("ttsSpeed", 0, 1.0)
                
                if not input_text:
                    return {"error": "Input text is required for TTS generation"}
                
                # Prepare headers
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # Prepare request data
                data = {
                    "model": model,
                    "input": input_text,
                    "voice": voice,
                    "response_format": response_format,
                    "speed": speed
                }
                
                # Make API request
                response = requests.post(
                    f"{base_url}/audio/speech",
                    headers=headers,
                    json=data
                )
                
                if response.status_code >= 400:
                    return {"error": f"OpenAI API error: {response.text}"}
                
                # Return binary audio data
                # Note: In a real implementation, you'd need to handle the binary response appropriately
                return {
                    "message": "TTS generation successful",
                    "format": response_format,
                    "input_text": input_text[:100] + "..." if len(input_text) > 100 else input_text
                }
                
            return {"error": f"Operation {operation} is not supported for TTS resource"}
            
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Error processing TTS: {str(e)}"}

    def get_node_data(self, node_name: str) -> List[NodeExecutionData]:
        """
        Get data from another node in the workflow
        
        Args:
            node_name: Name of the node to get data from
            
        Returns:
            List of NodeExecutionData from the specified node or empty list if not found
        """
        try:
            # Check if workflow_context is available
            if not hasattr(self, 'workflow_context') or not self.workflow_context:
                return []
                
            # Check if node_data exists in workflow_context
            if 'node_data' not in self.workflow_context:
                return []
                
            # Check if the requested node exists
            if node_name not in self.workflow_context['node_data']:
                return []
                
            # Return the node data
            node_data = self.workflow_context['node_data'][node_name]
            return node_data
        
        except Exception as e:
            traceback.print_exc()
            return []