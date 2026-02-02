"""
Binary File Download Pattern for AvidFlow

Pattern extracted from: bale.py, telegram.py
Use case: Download files from APIs and store as binary data

SYNC-CELERY SAFE: Uses requests with timeout, no async/await
"""

import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# MIME type to file extension mapping (Office documents, PDFs, etc.)
OFFICE_MIME_TO_EXT = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "audio/mpeg": ".mp3",
}


def download_file_to_binary(
    url: str,
    credentials: Dict[str, Any],
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """
    Download file from URL and return as binary data.
    
    Args:
        url: Full URL to download from
        credentials: Credential dict with access token
        timeout: Request timeout in seconds
        
    Returns:
        Dict with binary data:
        {
            "data": base64_string,
            "mimeType": "image/jpeg",
            "fileName": "file.jpg",
            "fileSize": 12345
        }
        Or None if download fails
        
    Example:
        binary_data = download_file_to_binary(
            "https://api.example.com/files/12345",
            credentials,
            timeout=30
        )
        if binary_data:
            return NodeExecutionData(
                json_data={"status": "downloaded"},
                binary_data={"file": binary_data}
            )
    """
    try:
        # Build auth headers
        access_token = credentials.get("accessToken", "")
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        
        # Make synchronous request with timeout (Celery+gevent safe)
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Get content type and determine extension
        content_type = response.headers.get("content-type", "application/octet-stream")
        mime_type = content_type.split(";")[0].strip()
        
        # Determine file extension
        extension = OFFICE_MIME_TO_EXT.get(mime_type, "")
        if not extension:
            # Try to extract from URL
            if "." in url:
                extension = "." + url.split(".")[-1].split("?")[0]
            else:
                extension = ".bin"
        
        # Convert to base64 for storage
        import base64
        file_data = base64.b64encode(response.content).decode('utf-8')
        
        return {
            "data": file_data,
            "mimeType": mime_type,
            "fileName": f"downloaded{extension}",
            "fileSize": len(response.content),
        }
        
    except requests.Timeout:
        logger.error(f"Timeout downloading file from {url}")
        return None
    except requests.RequestException as e:
        logger.error(f"Error downloading file: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        return None


def get_file_from_message_api(
    file_id: str,
    api_base: str,
    credentials: Dict[str, Any],
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """
    Pattern for APIs that provide file_id and require separate getFile call.
    Common in Telegram, Bale, Discord APIs.
    
    Args:
        file_id: Unique file identifier from message
        api_base: Base API URL (e.g., https://api.telegram.org/bot{token})
        credentials: Credential dict
        timeout: Request timeout
        
    Returns:
        Binary data dict or None
        
    Example from TypeScript:
        const fileInfo = await getFile.call(this, file_id);
        const binaryData = await downloadFile.call(this, fileInfo.file_path);
        
    Converted to Python:
        # Step 1: Get file info
        file_info = get_file_info(file_id, api_base, credentials)
        if not file_info:
            return None
            
        # Step 2: Download file
        file_path = file_info.get('file_path')
        download_url = f"{api_base}/file/{file_path}"
        return download_file_to_binary(download_url, credentials, timeout)
    """
    try:
        # Step 1: Get file metadata
        access_token = credentials.get("accessToken", "")
        url = f"{api_base}/getFile"
        
        response = requests.post(
            url,
            json={"file_id": file_id},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout
        )
        response.raise_for_status()
        
        result = response.json()
        if not result.get("ok") or not result.get("result"):
            logger.error(f"Failed to get file info for {file_id}")
            return None
        
        file_path = result["result"].get("file_path")
        if not file_path:
            return None
        
        # Step 2: Download file content
        download_url = f"{api_base}/file/{file_path}"
        return download_file_to_binary(download_url, credentials, timeout)
        
    except Exception as e:
        logger.error(f"Error getting file from message API: {e}")
        return None
