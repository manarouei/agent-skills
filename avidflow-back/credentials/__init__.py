"""
Credentials package for n8n backend.
Each credential type has its own file with definition and testing capabilities.
"""
from typing import Dict, List, Type

from .base import BaseCredential
from .httpBasicAuth import HttpBasicAuthCredential
from .httpHeaderAuth import HttpHeaderAuthCredential
from .oAuth2Api import OAuth2ApiCredential
from .telegramApi import TelegramApiCredential
from .openAiApi import OpenAiApiCredential
from .wooCommerceApi import WooCommerceApiCredential

from .shopifyApi import ShopifyApiCredential
from .shopifyAccessTokeApi import ShopifyAccessTokenApiCredential
from .shopifyOauth2Api import ShopifyOAuth2ApiCredential

from .googleOAuth2Api import GoogleOAuth2ApiCredential
from .gmailOAuth2Api import GmailOAuth2ApiCredential
from .googleCalendarApi import GoogleCalendarApiCredential
from .googleDocsApi import GoogleDocsApiCredential
from .googleDriveApi import GoogleDriveApiCredential
from .googleSheetsApi import GoogleSheetsApiCredential
from .googleFormApi import GoogleFormApiCredential

from .trelloOAuth1Api import TrelloOAuth1ApiCredential

from .twitterOAuth2Api import TwitterOAuth2ApiCredential

from .facebookGraphApi import FacebookGraphApiCredential
from .facebookGraphAppApi import FacebookGraphAppApiCredential
from .facebookLeadAdsOAuth2Api import FacebookLeadAdsOAuth2ApiCredential

from .grokApi import GrokApiCredential
from .linkedinApi import LinkedInApiCredential
from .deepseekApi import DeepSeekApiCredential
from .geminiApi import GeminiApiCredential

from .wordpressApi import WordpressApiCredential

from .baleApi import BaleApiCredential
#from .trelloOAuth1Api import TrelloOAuth1ApiCredential
from .gitlabApi  import GitLabApiCredential
from .githubApi import GitHubApiCredential
from .slackApi import SlackApiCredential
from .slackOAuth2Api import SlackOAuth2ApiCredential

from .postgresApi import PostgresApiCredential
from .qdrantApi import QdrantApiCredential
from .cohereApi import CohereApiCredential
from .sakuyMeliApi import SakuyMeliApiCredential
from .redisApi import RedisApiCredential
from .openProjectApi import OpenProjectApiCredential
from .localGptApi import LocalGptApiCredential
from .kavenegarApi import KavenegarApiCredential
# from .postgresApi import PostgresApiCredential
from .hesabfaTokenApi import HesabfaTokenApiCredential
from .mysqlApi import MySQLApiCredential
from .neshanApi import NeshanApiCredential
from .wallexApi import WallexApiCredential
from .airtableApi import AirtableApiCredential

# Registry of all available credential types
CREDENTIAL_TYPES: Dict[str, Type[BaseCredential]] = {
    # Existing credential types
    "httpBasicAuth": HttpBasicAuthCredential,
    "httpHeaderAuth": HttpHeaderAuthCredential,
    "oAuth2Api": OAuth2ApiCredential,
    "telegramApi": TelegramApiCredential,
    "openAiApi": OpenAiApiCredential,
    "wooCommerceApi": WooCommerceApiCredential,
    
    # Shopify credential types
    "shopifyApi": ShopifyApiCredential,
    "shopifyAccessTokenApi": ShopifyAccessTokenApiCredential,
    "shopifyOAuth2Api": ShopifyOAuth2ApiCredential,
    
    # Google credential types
    "googleOAuth2Api": GoogleOAuth2ApiCredential,
    "gmailOAuth2": GmailOAuth2ApiCredential,
    "googleDocsApi": GoogleDocsApiCredential,
    "googleCalendarApi": GoogleCalendarApiCredential,
    "googleDriveApi": GoogleDriveApiCredential,
    "googleSheetsApi": GoogleSheetsApiCredential,
    "googleFormApi": GoogleFormApiCredential,
    
    "twitterOAuth2Api": TwitterOAuth2ApiCredential,
    "facebookGraphApi": FacebookGraphApiCredential,
    "facebookGraphAppApi": FacebookGraphAppApiCredential,
    "facebookLeadAdsOAuth2Api": FacebookLeadAdsOAuth2ApiCredential,
    "linkedinApi": LinkedInApiCredential,
    "deepseekApi": DeepSeekApiCredential,
    "grokApi": GrokApiCredential,
    "geminiApi": GeminiApiCredential,

    "wordpressApi": WordpressApiCredential,

    "baleApi":BaleApiCredential,
    "gitlabApi":GitLabApiCredential,
    "githubApi": GitHubApiCredential,
    "slackApi": SlackApiCredential,
    "slackOAuth2Api": SlackOAuth2ApiCredential,

    "postgresApi": PostgresApiCredential,
    "qdrantApi": QdrantApiCredential,
    "cohereApi": CohereApiCredential,
    "sakuyMeliApi": SakuyMeliApiCredential,
    "redisApi": RedisApiCredential,
    "openProjectApi": OpenProjectApiCredential,
    "localGptApi": LocalGptApiCredential,
    #  "oAuth1Api": OAuth1ApiCredential,
    "trelloOAuth1Api": TrelloOAuth1ApiCredential,
    "kavenegarApi": KavenegarApiCredential,
    "hesabfaTokenApi": HesabfaTokenApiCredential,
    "mysqlApi": MySQLApiCredential,
    'neshanApi': NeshanApiCredential,
    "wallexApi": WallexApiCredential,
    "airtableApi": AirtableApiCredential,


    #"trelloOAuth1Api": trelloOAuth1Api.TrelloOAuth1ApiCredential,
}

def get_all_credentials() -> List[Dict]:
    """Get all credential type definitions"""
    return [cred_class.get_definition() | {"is_oauth2": issubclass(cred_class, OAuth2ApiCredential)} for cred_class in CREDENTIAL_TYPES.values()]

def get_credential_by_type(credential_type: str) -> Type[BaseCredential]:
    """Get credential class by type name"""
    if credential_type not in CREDENTIAL_TYPES:
        raise ValueError(f"Credential type '{credential_type}' not found")
    return CREDENTIAL_TYPES[credential_type]
