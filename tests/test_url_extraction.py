"""Test URL extraction patterns for code-convert."""

import re
import pytest


def _extract_base_url_from_ts(ts_code: str) -> str:
    """Extract base URL from TypeScript source - mirrors code-convert logic."""
    base_url = None
    
    # Pattern 1: uri: with quotes
    uri_match = re.search(r"uri:\s*['\"`]([^'\"$`]+)", ts_code)
    if uri_match:
        base_url = uri_match.group(1)
    
    # Pattern 2: url: with template string (backtick)
    if not base_url:
        url_template_match = re.search(r"url:\s*`(https?://[^$`]+)", ts_code)
        if url_template_match:
            base_url = url_template_match.group(1)
    
    # Pattern 3: url: with quotes
    if not base_url:
        url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", ts_code)
        if url_match:
            base_url = url_match.group(1)
    
    # Fallback
    if not base_url:
        base_url = "https://api.example.com"
    
    # Clean up any remaining template parts
    base_url = re.sub(r"\$\{[^}]+\}", "", base_url)
    
    return base_url


class TestDiscordUrlExtraction:
    """Test extracting Discord API URL from TypeScript source."""
    
    def test_discord_template_string(self):
        """Discord uses url: with template string and ${endpoint}."""
        ts_code = '''
        const options: IRequestOptions = {
            headers,
            method,
            url: `https://discord.com/api/v10${endpoint}`,
            json: true,
        };
        '''
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://discord.com/api/v10"
    
    def test_discord_multipart_url(self):
        """Discord multipart also uses template string."""
        ts_code = '''
        const options: IRequestOptions = {
            headers,
            method,
            formData,
            url: `https://discord.com/api/v10${endpoint}`,
        };
        '''
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://discord.com/api/v10"


class TestTraditionalUrlExtraction:
    """Test extracting URLs from traditional patterns."""
    
    def test_uri_with_single_quotes(self):
        """Traditional uri: pattern with single quotes."""
        ts_code = """
        const options = {
            uri: 'https://api.notion.com/v1',
            method: 'GET'
        };
        """
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://api.notion.com/v1"
    
    def test_uri_with_double_quotes(self):
        """Traditional uri: pattern with double quotes."""
        ts_code = '''
        const options = {
            uri: "https://api.github.com",
            method: "POST"
        };
        '''
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://api.github.com"
    
    def test_url_with_single_quotes(self):
        """Simple url: pattern with single quotes."""
        ts_code = """
        const options = {
            url: 'https://api.stripe.com/v1',
            method: 'GET'
        };
        """
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://api.stripe.com/v1"
    
    def test_url_with_template_and_variables(self):
        """URL template that includes variables that should be stripped."""
        ts_code = '''
        const options = {
            url: `https://api.slack.com/api/${method}`,
            headers
        };
        '''
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://api.slack.com/api/"


class TestFallbackBehavior:
    """Test fallback when no URL found."""
    
    def test_no_url_returns_placeholder(self):
        """When no URL pattern found, return placeholder."""
        ts_code = """
        // No URL here
        const x = 5;
        """
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://api.example.com"
    
    def test_empty_string_returns_placeholder(self):
        """Empty source returns placeholder."""
        result = _extract_base_url_from_ts("")
        assert result == "https://api.example.com"


class TestRealDiscordSourceFile:
    """Test with actual Discord source content."""
    
    def test_discord_api_ts_content(self):
        """Test extraction from actual discord.api.ts content."""
        # Actual content from input_sources/discord/v2/transport/discord.api.ts
        ts_code = '''
import type FormData from 'form-data';
import type {
    IDataObject,
    IExecuteFunctions,
} from 'n8n-workflow';

export async function discordApiRequest(
    this: IHookFunctions | IExecuteFunctions,
    method: IHttpRequestMethods,
    endpoint: string,
    body?: IDataObject,
    qs?: IDataObject,
) {
    const options: IRequestOptions = {
        headers,
        method,
        qs,
        body,
        url: `https://discord.com/api/v10${endpoint}`,
        json: true,
    };
    
    return response;
}
        '''
        result = _extract_base_url_from_ts(ts_code)
        assert result == "https://discord.com/api/v10"
        assert "example.com" not in result
