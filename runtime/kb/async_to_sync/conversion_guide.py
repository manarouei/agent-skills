"""
Async-to-Sync Conversion Patterns for Celery+Gevent

AvidFlow platform runs ALL workflows in synchronous Celery tasks with gevent workers.
NO async/await is supported. All I/O must be synchronous with timeouts.

This guide shows how to convert common TypeScript async patterns to Python sync patterns.
"""

# ==============================================================================
# PATTERN 1: Simple async HTTP call → requests with timeout
# ==============================================================================

# TypeScript (n8n):
"""
async function makeRequest(endpoint: string): Promise<any> {
    const response = await this.helpers.httpRequest({
        method: 'GET',
        url: `https://api.example.com${endpoint}`,
        headers: {
            'Authorization': `Bearer ${credentials.accessToken}`
        }
    });
    return response;
}
"""

# Python (AvidFlow - CORRECT):
"""
import requests

def make_request(endpoint: str, credentials: dict, timeout: int = 30) -> dict:
    '''
    SYNC-CELERY SAFE: Uses requests with timeout parameter.
    '''
    access_token = credentials.get('accessToken', '')
    response = requests.get(
        f'https://api.example.com{endpoint}',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=timeout  # CRITICAL: Always include timeout
    )
    response.raise_for_status()
    return response.json()
"""


# ==============================================================================
# PATTERN 2: Helper function call → Direct function call
# ==============================================================================

# TypeScript (n8n):
"""
const fileInfo = await getFileSha.call(this, owner, repo, path, branch);
"""

# Python (AvidFlow - CANNOT CONVERT):
"""
# NOTE: getFileSha is a helper function not available in AvidFlow platform.
# LACK OF IMPLEMENTATION: File SHA retrieval requires additional API call
# that is not implemented in current platform version.
# TODO: Implement GitHub file metadata helper in utils/github_helpers.py
# For now, mark as unimplemented:
raise NotImplementedError(
    "File SHA retrieval not supported in AvidFlow platform. "
    "This operation requires accessing GitHub's file metadata API "
    "which is not yet implemented."
)
"""


# ==============================================================================
# PATTERN 3: Pagination with async iterator → while loop
# ==============================================================================

# TypeScript (n8n):
"""
async function getAllItems(endpoint: string): Promise<any[]> {
    let allItems = [];
    let page = 1;
    
    while (true) {
        const response = await this.helpers.httpRequest({
            url: `https://api.example.com${endpoint}?page=${page}`
        });
        
        if (response.length === 0) break;
        allItems = allItems.concat(response);
        page++;
    }
    
    return allItems;
}
"""

# Python (AvidFlow - CORRECT):
"""
import requests

def get_all_items(endpoint: str, credentials: dict, timeout: int = 30) -> list:
    '''
    SYNC-CELERY SAFE: Pagination using while loop with requests.
    '''
    all_items = []
    page = 1
    access_token = credentials.get('accessToken', '')
    headers = {'Authorization': f'Bearer {access_token}'}
    
    while True:
        response = requests.get(
            f'https://api.example.com{endpoint}',
            params={'page': page},
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        
        items = response.json()
        if not items:
            break
            
        all_items.extend(items)
        page += 1
        
        # Safety limit to prevent infinite loops
        if page > 1000:
            logger.warning("Pagination limit reached (1000 pages)")
            break
    
    return all_items
"""


# ==============================================================================
# PATTERN 4: File upload with binary data → requests with files parameter
# ==============================================================================

# TypeScript (n8n):
"""
const binaryData = this.helpers.assertBinaryData(i, 'data');
const formData = {
    file: {
        value: Buffer.from(binaryData.data, 'base64'),
        options: {
            filename: binaryData.fileName,
            contentType: binaryData.mimeType
        }
    }
};

const response = await this.helpers.httpRequest({
    method: 'POST',
    url: endpoint,
    formData: formData
});
"""

# Python (AvidFlow - CORRECT):
"""
import requests
import base64
from io import BytesIO

def upload_file(
    endpoint: str,
    binary_data: dict,
    credentials: dict,
    timeout: int = 60
) -> dict:
    '''
    SYNC-CELERY SAFE: File upload using requests with files parameter.
    
    Args:
        binary_data: Dict with 'data' (base64), 'fileName', 'mimeType'
    '''
    # Decode base64 data
    file_bytes = base64.b64decode(binary_data['data'])
    file_name = binary_data.get('fileName', 'file.bin')
    mime_type = binary_data.get('mimeType', 'application/octet-stream')
    
    # Prepare multipart form data
    files = {
        'file': (file_name, BytesIO(file_bytes), mime_type)
    }
    
    access_token = credentials.get('accessToken', '')
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.post(
        endpoint,
        files=files,
        headers=headers,
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()
"""


# ==============================================================================
# PATTERN 5: Base64 encoding → Built-in base64 module
# ==============================================================================

# TypeScript (n8n):
"""
if (isBase64(fileContent)) {
    body.content = fileContent;
} else {
    body.content = Buffer.from(fileContent).toString('base64');
}
"""

# Python (AvidFlow - CORRECT):
"""
import base64

# Check if content is already base64 (basic check)
def is_base64(s: str) -> bool:
    try:
        return base64.b64encode(base64.b64decode(s)).decode() == s
    except:
        return False

# Encode if needed
file_content = "Hello, World!"
if is_base64(file_content):
    body['content'] = file_content
else:
    body['content'] = base64.b64encode(file_content.encode()).decode()
"""


# ==============================================================================
# PATTERN 6: Webhook trigger (no HTTP call) → Return execution_data
# ==============================================================================

# TypeScript (n8n):
"""
async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
    const body = this.getBodyData();
    const headers = this.getHeaderData();
    
    return {
        workflowData: [
            [
                {
                    json: body
                }
            ]
        ]
    };
}
"""

# Python (AvidFlow - CORRECT):
"""
from models import NodeExecutionData

def trigger(self) -> list[list[NodeExecutionData]]:
    '''
    Webhook trigger node: Returns execution_data passed from webhook router.
    
    SYNC-CELERY SAFE: No HTTP calls, just data transformation.
    '''
    # execution_data is set by webhook router before calling trigger()
    envelope = self.execution_data if hasattr(self, 'execution_data') else {}
    
    # Extract webhook payload
    body = envelope.get('webhookData') or envelope.get('body') or {}
    headers = envelope.get('headers') or {}
    
    # Return as NodeExecutionData
    return [[NodeExecutionData(
        json_data={
            'body': body,
            'headers': headers,
            'query': envelope.get('query', {}),
            'method': envelope.get('method', 'POST'),
        },
        binary_data=None
    )]]
"""


# ==============================================================================
# CRITICAL RULES
# ==============================================================================

"""
1. NEVER use async/await - Celery+gevent does not support it
2. ALWAYS use requests.get/post/put/delete with timeout parameter
3. ALWAYS include timeout (default 30s for API calls, 60s for uploads)
4. Use while loops for pagination, not async iterators
5. Binary data is base64-encoded strings, not Buffer objects
6. If operation requires async helper not in AvidFlow: raise NotImplementedError with clear message
7. Log all HTTP errors with logger.error() for debugging
8. Add retry logic for transient failures (use utils/retry.py patterns)
"""
