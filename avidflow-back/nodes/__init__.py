from .http_request import HttpRequestNode
from .merge import MergeNode
from .start import StartNode
from .end import EndNode
from .if_node import IfNode
from .openai import OpenAiNode
from .set import SetNode
from .telegram import TelegramNode
from .telegram_trigger import TelegramTriggerNode
from .twitter import TwitterNode
from .webhook import WebhookNode
from .googleCalendar import GoogleCalendarNode
from .gmail import GmailNode
from .switch import SwitchNode
from .googleDocs import GoogleDocsNode
from .linkedin import LinkedInNode
from .grok import GrokNode
from .gemini import GeminiNode
from .wooCommerce import WooCommerceNode

from .stickyNote import StickyNoteNode

from .googleSheets import GoogleSheetsNode
from .googleDrive import GoogleDriveNode
from .googleForm import GoogleFormNode

from .wordpress import WordPressNode
from .deepseek import DeepSeekNode

from .bale import BaleNode
from .baleTrigger import BaleTrigger

from .iterator import IteratorNode
from .filtering import FilterNode
from .htmlExtractor import HtmlExtractorNode
from .splitInBatches import SplitInBatchesNode
from .subworkflow import ExecuteWorkflowNode
from .supabase import SupabaseNode
from .loop import LoopNode

# from .schedule import ScheduleNode
from .wait import WaitNode
from .chat import ChatNode

from .rssFeed import RssFeedReadNode
from .rssFeedTrigger import RssFeedReadTriggerNode

from .schedule import ScheduleNode

from .form_submission_trigger import OnFormSubmissionNode
from .gmail_trigger import GmailTriggerNode

from .chat_models import OpenAIChatModelNode
from .chat_models.sakuy_meli_chat_model import SakuyMeliChatModelNode
from .memory import BufferMemoryNode
from .memory import RedisMemoryNode
from .ai_agent import AIAgentNode

from .postgres import PostgresNode
from .mysql import MySQLNode
from .trello import TrelloNode

from .mcpClientTool import McpClientToolNode
from .qdrantVectorStore import QdrantVectorStoreNode
from .embeddings_openai import EmbeddingsOpenAINode
from .document_default_data_loader import DocumentDefaultDataLoaderNode

# New nodes for agent workflow migration
from .rerankers import RerankerCohereNode
from .text_processors import PersianTextProcessorNode
from .validators import OutputValidatorNode

from .shopify import ShopifyNode
from .openProject import OpenProjectNode

from .slack import SlackNode
from .redis import RedisNode
from .kavenegar import KavenegarNode
from .hesabfa import HesabfaNode
from .neshan import NeshanNode
from .wallex import WallexNode
from .airtable import AirtableNode

from .github import GithubNode

from .local_gpt import LocalGptNode

# Node definitions registry
# Format: 'node_type': {'node_class': NodeClass, 'type': 'regular'|'trigger'}
node_definitions = {
    'chat': {'node_class': ChatNode, 'type': 'trigger'},
    'http_request': {'node_class': HttpRequestNode, 'type': 'regular'},
    'merge': {'node_class': MergeNode, 'type': 'regular'},
    'start': {'node_class': StartNode, 'type': 'regular'},
    'end': {'node_class': EndNode, 'type': 'regular'},
    'if': {'node_class': IfNode, 'type': 'regular'},
    'openai': {'node_class': OpenAiNode, 'type': 'regular'},
    'set': {'node_class': SetNode, 'type': 'regular'},
    'telegram': {'node_class': TelegramNode, 'type': 'regular'},
    'telegram_trigger': {'node_class': TelegramTriggerNode, 'type': 'trigger'},
    'twitter': {'node_class': TwitterNode, 'type': 'regular'},
    'webhook': {'node_class': WebhookNode, 'type': 'trigger'},
    'googleCalendar': {'node_class': GoogleCalendarNode, 'type': 'regular'},
    #'googleCalendar1': {'node_class': GoogleCalendarNode, 'type': 'regular'},
    'trello': {'node_class': TrelloNode, 'type': 'regular'},
    # Add this entry to the node_definitions dictionary
    'stickyNote': {'node_class': StickyNoteNode, 'type': 'regular'},
    'gmail': {'node_class': GmailNode, 'type': 'regular'},
    'gmail_trigger': {'node_class': GmailTriggerNode, 'type': 'trigger'},
    'switch': {'node_class': SwitchNode, 'type': 'regular'},
    'googleDocs': {'node_class': GoogleDocsNode, 'type': 'regular'},
    'linkedin': {'node_class': LinkedInNode, 'type': 'regular'},
    'grok': {'node_class': GrokNode, 'type': 'regular'},
    'googleSheets': {'node_class': GoogleSheetsNode, 'type': 'regular'},
    'wordpress': {'node_class': WordPressNode, 'type': 'regular'},
    'wooCommerce': {'node_class': WooCommerceNode, 'type': 'regular'},
    'deepseek': {'node_class': DeepSeekNode, 'type': 'regular'},
    'gemini': {'node_class': GeminiNode, 'type': 'regular'},
    'googleDrive': {'node_class': GoogleDriveNode, 'type': 'regular'},
    'googleForm': {'node_class': GoogleFormNode, 'type': 'regular'},
    'bale':{'node_class':BaleNode, 'type':'regular'},

    'iterator':{'node_class':IteratorNode, 'type':'regular'},
    'filter': {'node_class': FilterNode, 'type': 'regular'},
    'htmlExtractor': {'node_class': HtmlExtractorNode, 'type': 'regular'},
    'loop': {'node_class': LoopNode, 'type': 'regular'},

    'splitInBatches': {'node_class': SplitInBatchesNode, 'type': 'regular'},
    'subWorkflow': {'node_class': ExecuteWorkflowNode, 'type': 'regular'},

    'schedule': {'node_class': ScheduleNode, 'type': 'trigger'},
    'wait': {'node_class': WaitNode, 'type': 'regular'},
    'baleTrigger': {'node_class': BaleTrigger, 'type': 'trigger'},
    'rssFeed': {'node_class': RssFeedReadNode, 'type': 'regular'},
    'rssFeedTrigger': {'node_class': RssFeedReadTriggerNode, 'type': 'trigger'},

    'supabase': {'node_class': SupabaseNode, 'type': 'regular'},

    'form_trigger': {'node_class': OnFormSubmissionNode, 'type': 'trigger'},
    'ai_languageModel': {'node_class': OpenAIChatModelNode, 'type': 'regular'},
    'sakuy_meli_chat_model': {'node_class': SakuyMeliChatModelNode, 'type': 'regular'},
    'buffer_memory': {'node_class': BufferMemoryNode, 'type': 'regular'},
    'redis_memory': {'node_class': RedisMemoryNode, 'type': 'regular'},
    'ai_agent': {'node_class': AIAgentNode, 'type': 'regular'},
    'postgres': {'node_class': PostgresNode, 'type': 'regular'},
    'mysql': {'node_class': MySQLNode, 'type': 'regular'},

    'mcpClientTool': {'node_class': McpClientToolNode, 'type': 'regular'},
    'qdrantVectorStore': {'node_class': QdrantVectorStoreNode, 'type': 'regular'},
    'ai_embedding': {'node_class': EmbeddingsOpenAINode, 'type': 'regular'},
    'documentDefaultDataLoader': {'node_class': DocumentDefaultDataLoaderNode, 'type': 'regular'},
    
    # Agent workflow migration nodes
    'rerankerCohere': {'node_class': RerankerCohereNode, 'type': 'regular'},
    'persianTextProcessor': {'node_class': PersianTextProcessorNode, 'type': 'regular'},
    'outputValidator': {'node_class': OutputValidatorNode, 'type': 'regular'},
    'shopify': {'node_class': ShopifyNode, 'type': 'regular'},
    'openProject': {'node_class': OpenProjectNode, 'type': 'regular'},

    'slack': {'node_class': SlackNode, 'type': 'regular'},
    'redis': {'node_class': RedisNode, 'type': 'regular'},
    'kavenegar': {'node_class': KavenegarNode, 'type': 'regular'},
    'hesabfa': {'node_class': HesabfaNode, 'type': 'regular'},
    'neshan': {'node_class': NeshanNode, 'type': 'regular'},
    'wallex': {'node_class': WallexNode, 'type': 'regular'},
    'airtable': {'node_class': AirtableNode, 'type': 'regular'},

    'localGpt': {'node_class': LocalGptNode, 'type': 'regular'},

    'github':{'node_class':GithubNode, 'type':'regular'}
   
    # Add more nodes as they are implemented
}