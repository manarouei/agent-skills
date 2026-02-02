import requests
import json
import logging
import base64
import time
from urllib.parse import urlencode
from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class GoogleDriveNode(BaseNode):
    """
    Google Drive node for file and folder operations
    """
    
    type = "googleDrive"
    version = 3.0
    
    description = {
        "displayName": "Google Drive",
        "name": "googleDrive",
        "icon": "file:googleDrive.svg",
        "group": ["input", "output"],
        "description": "Access data on Google Drive",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "googleDriveApi",
                "required": True
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "File", "value": "file"},
                    {"name": "Folder", "value": "folder"}
                ],
                "default": "file",
                "description": "The resource to operate on"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Download", "value": "download"},
                    {"name": "List", "value": "list"},
                    {"name": "Share", "value": "share"},
                    {"name": "Update", "value": "update"},
                    {"name": "Upload", "value": "upload"}
                ],
                "default": "list",
                "description": "The operation to perform"
            },
            # File operations
            {
                "name": "fileId",
                "type": NodeParameterType.STRING,
                "display_name": "File ID",
                "default": "",
                "description": "The ID of the file",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["delete", "download", "share", "update"]
                    }
                }
            },
            {
                "name": "fileName",
                "type": NodeParameterType.STRING,
                "display_name": "File Name",
                "default": "",
                "description": "Name of the file",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["create", "upload", "download"]
                    }
                }
            },
            {
                "name": "binaryData",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Binary Data",
                "default": False,
                "description": "If the data is binary data",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["upload"]
                    }
                }
            },
            {
                "name": "binaryPropertyName",
                "type": NodeParameterType.STRING,
                "display_name": "Binary Property",
                "default": "data",
                "description": "Name of the binary property which contains the data for the file to be uploaded",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["upload"],
                        "binaryData": [True]
                    }
                }
            },
            {
                "name": "fileContent",
                "type": NodeParameterType.STRING,
                "display_name": "File Content",
                "default": "",
                "description": "The content of the file",
                "typeOptions": {
                    "rows": 5
                },
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["upload"],
                        "binaryData": [False]
                    }
                }
            },
            {
                "name": "parentId",
                "type": NodeParameterType.STRING,
                "display_name": "Parent Folder ID",
                "default": "",
                "description": "ID of the parent folder. If not set, the file will be created in the root folder",
                "displayOptions": {
                    "show": {
                        "resource": ["file"],
                        "operation": ["create", "upload"]
                    }
                }
            },
            # Folder operations
            {
                "name": "folderId",
                "type": NodeParameterType.STRING,
                "display_name": "Folder ID",
                "default": "",
                "description": "The ID of the folder",
                "displayOptions": {
                    "show": {
                        "resource": ["folder"],
                        "operation": ["delete", "list", "share", "update"]
                    }
                }
            },
            {
                "name": "folderName",
                "type": NodeParameterType.STRING,
                "display_name": "Folder Name",
                "default": "",
                "description": "Name of the folder",
                "displayOptions": {
                    "show": {
                        "resource": ["folder"],
                        "operation": ["create", "update"]
                    }
                }
            },
            # List options
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results or only up to a given limit",
                "displayOptions": {
                    "show": {
                        "operation": ["list"]
                    }
                }
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 100,
                "description": "Max number of results to return",
                "typeOptions": {
                    "minValue": 1
                },
                "displayOptions": {
                    "show": {
                        "operation": ["list"],
                        "returnAll": [False]
                    }
                }
            },
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Search Query",
                "default": "",
                "description": "Search query to filter files/folders",
                "displayOptions": {
                    "show": {
                        "operation": ["list"]
                    }
                }
            },
            # Share options
            {
                "name": "shareType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Share Type",
                "options": [
                    {"name": "Anyone with Link", "value": "anyone"},
                    {"name": "Domain", "value": "domain"},
                    {"name": "User", "value": "user"},
                    {"name": "Group", "value": "group"}
                ],
                "default": "anyone",
                "description": "Type of sharing permission",
                "displayOptions": {
                    "show": {
                        "operation": ["share"]
                    }
                }
            },
            {
                "name": "role",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Role",
                "options": [
                    {"name": "Reader", "value": "reader"},
                    {"name": "Writer", "value": "writer"},
                    {"name": "Commenter", "value": "commenter"}
                ],
                "default": "reader",
                "description": "Permission role",
                "displayOptions": {
                    "show": {
                        "operation": ["share"]
                    }
                }
            },
            {
                "name": "emailAddress",
                "type": NodeParameterType.STRING,
                "display_name": "Email Address",
                "default": "",
                "description": "Email address of the user or group",
                "displayOptions": {
                    "show": {
                        "operation": ["share"],
                        "shareType": ["user", "group"]
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "googleDriveApi",
                "required": True
            }
        ]
    }
    
    icon = "googleDrive.svg"
    color = "#0F9D58"
    
    # Add this as a class attribute
    GOOGLE_MIME_TYPES = {
        # Google Workspace conversions
        '.docx': 'application/vnd.google-apps.document',
        '.doc': 'application/vnd.google-apps.document',
        '.odt': 'application/vnd.google-apps.document',
        '.rtf': 'application/vnd.google-apps.document',
        '.txt': 'application/vnd.google-apps.document',
        '.html': 'application/vnd.google-apps.document',
        '.epub': 'application/vnd.google-apps.document',
        
        '.xlsx': 'application/vnd.google-apps.spreadsheet',
        '.xls': 'application/vnd.google-apps.spreadsheet',
        '.ods': 'application/vnd.google-apps.spreadsheet',
        '.csv': 'application/vnd.google-apps.spreadsheet',
        '.tsv': 'application/vnd.google-apps.spreadsheet',
        
        '.pptx': 'application/vnd.google-apps.presentation',
        '.ppt': 'application/vnd.google-apps.presentation',
        '.odp': 'application/vnd.google-apps.presentation',
        
        # Standard mime types for non-convertible files
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.mp3': 'audio/mpeg',
        '.zip': 'application/zip',
    }
    
    def __init__(self, *args, **kwargs):
        """Initialize with framework args and set up API URLs"""
        super().__init__(*args, **kwargs)
        self.base_url = "https://www.googleapis.com/drive/v3"
        self.upload_url = "https://www.googleapis.com/upload/drive/v3"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Google Drive operations"""
        try:
            input_data = self.get_input_data()
            result_items = []
            
            for i, item in enumerate(input_data):
                try:
                    # Use parameter() instead of get_node_parameter to properly evaluate expressions
                    resource = self.get_parameter("resource", i, "file")
                    operation = self.get_parameter("operation", i, "list")
                    
                    if resource == 'file':
                        if operation == 'create':
                            result = self._create_file(i)
                        elif operation == 'delete':
                            result = self._delete_file(i)
                        elif operation == 'download':
                            result = self._download_file(i)
                        elif operation == 'list':
                            result = self._list_files(i)
                        elif operation == 'share':
                            result = self._share_file(i)
                        elif operation == 'update':
                            result = self._update_file(i)
                        elif operation == 'upload':
                            result = self._upload_file(i)
                        else:
                            raise ValueError(f"Unsupported file operation: {operation}")
                    
                    elif resource == 'folder':
                        if operation == 'create':
                            result = self._create_folder(i)
                        elif operation == 'delete':
                            result = self._delete_folder(i)
                        elif operation == 'list':
                            result = self._list_folder_contents(i)
                        elif operation == 'share':
                            result = self._share_folder(i)
                        elif operation == 'update':
                            result = self._update_folder(i)
                        else:
                            raise ValueError(f"Unsupported folder operation: {operation}")
                    
                    else:
                        raise ValueError(f"Unsupported resource: {resource}")
                    
                    result_items.append(result)
                    
                except Exception as e:
                    logger.error(f"Google Drive Node - Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_parameter("resource", i, "file"),
                            "operation": self.get_parameter("operation", i, "list"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Google Drive Node - Execute error: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Google Drive node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        """Check if credentials have access token (n8n's approach)"""
        # Handle nested structure from credential system
        if 'data' in credentials_data:
            credentials_data = credentials_data['data']
        
        oauth_token_data = credentials_data.get('oauthTokenData')
        if not isinstance(oauth_token_data, dict):
            return False
        return 'access_token' in oauth_token_data

    def get_credential_type(self):
        return self.properties["credentials"][0]['name']

    def _is_token_expired(self, oauth_data: Dict[str, Any]) -> bool:
        """Check if the current token is expired"""
        if "expires_at" not in oauth_data:
            return False
        # Add 30 second buffer
        return time.time() > (oauth_data["expires_at"] - 30)
    
    def refresh_token(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh OAuth2 access token with proper invalid_grant handling"""
            
        if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
            raise ValueError("No refresh token available")

        oauth_data = data["oauthTokenData"]

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": oauth_data["refresh_token"],
        }
        
        headers = {}
        
        # Add client credentials based on authentication method
        if data.get("authentication", "header") == "header":
            auth_header = base64.b64encode(
                f"{data['clientId']}:{data['clientSecret']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {auth_header}"
        else:
            token_data.update({
                "client_id": data["clientId"],
                "client_secret": data["clientSecret"]
            })
        
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        try:
            response = requests.post(
                data["accessTokenUrl"],
                data=urlencode(token_data),
                headers=headers,
            )
            
            if response.status_code == 200:
                new_token_data = response.json()
                
                # Update token data (preserve existing data)
                updated_oauth_data = oauth_data.copy()
                updated_oauth_data["access_token"] = new_token_data["access_token"]
                
                if "expires_in" in new_token_data:
                    updated_oauth_data["expires_at"] = time.time() + new_token_data["expires_in"]
                
                # Only update refresh token if a new one is provided
                if "refresh_token" in new_token_data:
                    updated_oauth_data["refresh_token"] = new_token_data["refresh_token"]
                
                # Preserve any additional token data
                for key, value in new_token_data.items():
                    if key not in ["access_token", "expires_in", "refresh_token"]:
                        updated_oauth_data[key] = value
                
                # Save updated token data
                data["oauthTokenData"] = updated_oauth_data
                    
                self.update_credentials(self.get_credential_type(), data)

                return data
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {"error": response.text}
                
                error_code = error_data.get("error", "")
                # Handle invalid_grant - user needs to reconnect
                if error_code == "invalid_grant":
                    raise ValueError(f"OAuth token invalid (invalid_grant). User must reconnect their Google Drive account.")
                
                raise Exception(f"Token refresh failed with status {response.status_code}: {error_data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Token refresh request failed: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Token refresh failed: {str(e)}")

    def _get_access_token(self) -> str:
        """Get a valid access token for Google Drive API from the credentials"""
        try:
            credentials = self.get_credentials("googleDriveApi")
            if not credentials:
                raise ValueError("Google Drive API credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("Google Drive API access token not found")

            oauth_token_data = credentials.get('oauthTokenData', {})
            if self._is_token_expired(oauth_token_data):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting Google Drive access token: {str(e)}")
            raise ValueError(f"Failed to get Google Drive access token: {str(e)}")

    def google_api_request(self, method: str, url: str, body: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to Google API"""
        access_token = self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            if response.content:
                return response.json()
            else:
                return {"success": True}
                
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        if isinstance(error_data['error'], dict):
                            error_msg = f"Google Drive API Error: {error_data['error'].get('message', 'Unknown error')}"
                        else:
                            error_msg = f"Google Drive API Error: {error_data['error']}"
            except:
                pass
            logger.error(f"Google API request failed: {error_msg}")
            raise ValueError(error_msg)
        

    def _list_files(self, item_index: int) -> NodeExecutionData:
        """List files in Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            return_all = self.get_parameter('returnAll', item_index, False)
            limit = None if return_all else self.get_parameter('limit', item_index, 100)
            query = self.get_parameter('query', item_index, '')
            
            params = {
                'fields': 'nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime,parents,webViewLink,webContentLink)'
            }
            
            if query:
                params['q'] = query
            
            if limit:
                params['pageSize'] = limit
            
            url = f"{self.base_url}/files"
            response = self.google_api_request('GET', url, params=params)

            return NodeExecutionData(
                json_data={
                    "files": response.get('files', []),
                    "nextPageToken": response.get('nextPageToken'),
                    "totalFiles": len(response.get('files', []))
                }
            )
            
        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise

    def _get_mime_type(self, file_name: str, convert_to_google: bool = True) -> str:
        """
        Get mime type for file based on extension.
        
        Args:
            file_name: Name of the file
            convert_to_google: Whether to convert to Google Workspace formats when possible
            
        Returns:
            Appropriate mime type string
        """
        if not file_name:
            return 'application/octet-stream'
            
        # Get file extension (case insensitive)
        ext = '.' + file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        if convert_to_google and ext in self.GOOGLE_MIME_TYPES:
            mime_type = self.GOOGLE_MIME_TYPES[ext]
            # Only convert office documents to Google formats
            if 'google-apps' in mime_type:
                return mime_type
        
        # Fallback to standard mime types
        standard_types = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.zip': 'application/zip',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        
        return standard_types.get(ext, 'application/octet-stream')

    def _upload_file(self, item_index: int) -> NodeExecutionData:
        """Upload a file to Google Drive"""
        try:
            access_token = self._get_access_token()
            
            file_name = self.get_parameter("fileName", item_index, "")
            parent_id = self.get_parameter("parentId", item_index, "")
            use_binary_data = self.get_parameter("binaryData", item_index, False)
            
            if not file_name:
                raise ValueError("File name is required")
            
            metadata = {"name": file_name}
            
            # Get appropriate mime type (converts to Google formats when applicable)
            google_mime_type = self._get_mime_type(file_name, convert_to_google=True)
            if google_mime_type != 'application/octet-stream':
                metadata["mimeType"] = google_mime_type

            if parent_id and isinstance(parent_id, str) and parent_id.strip() and not (parent_id.startswith('=') and ('None' in parent_id or 'null' in parent_id)):
                metadata["parents"] = [parent_id]
    
            # Get file content and original mime type
            if use_binary_data:
                binary_prop = self.get_parameter("binaryPropertyName", item_index, "data")
                input_items = self.get_input_data() or []
                current = input_items[item_index] if 0 <= item_index < len(input_items) else None
                bin_map: Dict[str, Any] = getattr(current, "binary_data", None) if current else None

                if not bin_map or binary_prop not in bin_map:
                    raise ValueError(f"Binary property '{binary_prop}' not found")

                binary_data = bin_map.get(binary_prop)
                file_content = self._binary_entry_to_bytes(binary_data)
                
                # Use original mime type for upload, not the Google conversion
                mime_type = binary_data.get('mimeType') or self._get_mime_type(file_name, convert_to_google=False)
            else:
                file_content = self.get_parameter("fileContent", item_index, "").encode('utf-8')
                mime_type = 'text/plain'

            # Upload to Google Drive
            url = "https://www.googleapis.com/upload/drive/v3/files"
            params = {
                "uploadType": "multipart",
                "fields": "id,name,mimeType,size,createdTime,modifiedTime,parents,webViewLink,webContentLink"
            }

            boundary = f"---boundary---{int(time.time())}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}"
            }
            
            # Build the multipart body
            body = b''
            body += f"--{boundary}\r\n".encode('utf-8')
            body += f"Content-Type: application/json; charset=UTF-8\r\n\r\n".encode('utf-8')
            body += json.dumps(metadata).encode('utf-8')
            body += f"\r\n--{boundary}\r\n".encode('utf-8')
            body += f"Content-Type: {mime_type}\r\n\r\n".encode('utf-8')
            body += file_content
            body += f"\r\n--{boundary}--".encode('utf-8')
            
            response = requests.post(url, params=params, headers=headers, data=body, timeout=60)
            response.raise_for_status()
            
            file_data = response.json()
            
            return NodeExecutionData(json_data={
                "id": file_data.get('id'),
                "name": file_data.get('name'),
                "mimeType": file_data.get('mimeType'),
                "size": file_data.get('size'),
                "webViewLink": file_data.get('webViewLink'),
                "webContentLink": file_data.get('webContentLink'),
                "createdTime": file_data.get('createdTime')
            }, binary_data=None)

        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

    def _download_file(self, item_index: int) -> NodeExecutionData:
        """Download a file from Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            file_id = self.get_parameter("fileId", item_index, "")
            file_name = self.get_parameter("fileName", item_index, "")
            
            if not file_id:
                raise ValueError("File ID is required")
            
            # First get file metadata
            metadata_url = f"{self.base_url}/files/{file_id}"
            metadata = self.google_api_request('GET', metadata_url)
            
            # Handle Google Workspace files differently
            mime_type = metadata.get('mimeType', '')
            
            if mime_type.startswith('application/vnd.google-apps.'):
                # Export Google Workspace files in appropriate format
                export_formats = {
                    'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'application/vnd.google-apps.drawing': 'image/png',
                }
                
                export_mime_type = export_formats.get(mime_type, 'application/pdf')
                download_url = f"{self.base_url}/files/{file_id}/export?mimeType={export_mime_type}"
                actual_mime_type = export_mime_type
            else:
                # Regular file download
                download_url = f"{self.base_url}/files/{file_id}?alt=media"
                actual_mime_type = mime_type
            
            access_token = self._get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(download_url, headers=headers, timeout=60)
            response.raise_for_status()
            
            # Encode content as base64 for binary data
            content_base64 = base64.b64encode(response.content).decode('utf-8')

            return NodeExecutionData(
                json_data={
                    "id": metadata.get('id'),
                    "name": metadata.get('name'),
                    "mimeType": actual_mime_type,
                    "originalMimeType": mime_type,
                    "size": len(response.content)
                },
                binary_data={
                    "data": self.compress_data(content_base64),
                    "mimeType": actual_mime_type,
                    "fileName": file_name if file_name else metadata.get('name', 'download'),
                    "size": len(response.content)
                }
            )

        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise

    def _create_folder(self, item_index: int) -> NodeExecutionData:
        """Create a folder in Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            folder_name = self.get_parameter("folderName", item_index, "")
            parent_id = self.get_parameter("parentId", item_index, "")
            
            
            if not folder_name:
                raise ValueError("Folder name is required")
            
            metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            
            # Handle parent ID properly, checking for None, empty strings, and expressions that failed
            if parent_id and isinstance(parent_id, str) and parent_id.strip() and not (parent_id.startswith('=') and ('None' in parent_id or 'null' in parent_id)):
                metadata["parents"] = [parent_id]
            
            url = f"{self.base_url}/files"
            response = self.google_api_request('POST', url, body=metadata)

            return NodeExecutionData(
                json_data={
                    "id": response.get('id'),
                    "name": response.get('name'),
                    "mimeType": response.get('mimeType'),
                    "webViewLink": response.get('webViewLink'),
                    "createdTime": response.get('createdTime')
                }
            )
            
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise

    def _delete_file(self, item_index: int) -> NodeExecutionData:
        """Delete a file from Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            file_id = self.get_parameter("fileId", item_index, "")
            if not file_id:
                raise ValueError("File ID is required")
            
            url = f"{self.base_url}/files/{file_id}"
            self.google_api_request('DELETE', url)

            return NodeExecutionData(
                json_data={
                    "success": True,
                    "fileId": file_id,
                    "message": "File deleted successfully"
                }
            )

        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise

    def _delete_folder(self, item_index: int) -> NodeExecutionData:
        """Delete a folder from Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            folder_id = self.get_parameter("folderId", item_index, "")
            if not folder_id:
                raise ValueError("Folder ID is required")
            
            url = f"{self.base_url}/files/{folder_id}"
            self.google_api_request('DELETE', url)

            return NodeExecutionData(
                json_data={
                    "success": True,
                    "folderId": folder_id,
                    "message": "Folder deleted successfully"
                }
            )
            
        except Exception as e:
            logger.error(f"Error deleting folder: {str(e)}")
            raise

    def _share_file(self, item_index: int) -> NodeExecutionData:
        """Share a file in Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            file_id = self.get_parameter("fileId", item_index, "")
            share_type = self.get_parameter("shareType", item_index, "anyone")
            role = self.get_parameter("role", item_index, "reader")
            email_address = self.get_parameter("emailAddress", item_index, "")
            
            if not file_id:
                raise ValueError("File ID is required")
            
            permission = {
                "role": role,
                "type": share_type
            }
            
            if share_type in ["user", "group"] and email_address:
                permission["emailAddress"] = email_address
            
            url = f"{self.base_url}/files/{file_id}/permissions"
            response = self.google_api_request('POST', url, body=permission)
            
            return NodeExecutionData(
                json_data={
                    "success": True,
                    "fileId": file_id,
                    "permissionId": response.get('id'),
                    "shareType": share_type,
                    "role": role
                }
            )

        except Exception as e:
            logger.error(f"Error sharing file: {str(e)}")
            raise

    def _share_folder(self, item_index: int) -> NodeExecutionData:
        """Share a folder in Google Drive"""
        try:
            # Use get_parameter to properly evaluate expressions
            folder_id = self.get_parameter("folderId", item_index, "")
            share_type = self.get_parameter("shareType", item_index, "anyone")
            role = self.get_parameter("role", item_index, "reader")
            email_address = self.get_parameter("emailAddress", item_index, "")
            
            if not folder_id:
                raise ValueError("Folder ID is required")
            
            permission = {
                "role": role,
                "type": share_type
            }
            
            if share_type in ["user", "group"] and email_address:
                permission["emailAddress"] = email_address
            
            url = f"{self.base_url}/files/{folder_id}/permissions"
            response = self.google_api_request('POST', url, body=permission)

            return NodeExecutionData(
                json_data={
                    "success": True,
                    "folderId": folder_id,
                    "permissionId": response.get('id'),
                    "shareType": share_type,
                    "role": role
                }
            )

        except Exception as e:
            logger.error(f"Error sharing folder: {str(e)}")
            raise

    def _list_folder_contents(self, item_index: int) -> NodeExecutionData:
        """List contents of a folder"""
        try:
            # Use get_parameter to properly evaluate expressions
            folder_id = self.get_parameter("folderId", item_index, "")
            return_all = self.get_parameter('returnAll', item_index, False)
            limit = None if return_all else self.get_parameter('limit', item_index, 100)
                   
            params = {
                'fields': 'nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime,parents,webViewLink,webContentLink)'
            }
            
            # Handle folder ID properly, checking for None, empty strings, and expressions that failed
            if folder_id and isinstance(folder_id, str) and folder_id.strip() and not (folder_id.startswith('=') and ('None' in folder_id or 'null' in folder_id)):
                # Use valid folder ID with proper quoting
                params['q'] = f"'{folder_id}' in parents"
            else:
                # Use 'root' as default when no folder specified
                params['q'] = "'root' in parents"
                
            if limit:
                params['pageSize'] = limit
        
            url = f"{self.base_url}/files"
            response = self.google_api_request('GET', url, params=params)

            return NodeExecutionData(
                json_data={
                    "folderId": folder_id if folder_id and isinstance(folder_id, str) and folder_id.strip() else "root",
                    "files": response.get('files', []),
                    "nextPageToken": response.get('nextPageToken'),
                    "totalFiles": len(response.get('files', []))
                }
            )
            
        except Exception as e:
            logger.error(f"Error listing folder contents: {str(e)}")
            raise
