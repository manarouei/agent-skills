#!/bin/bash
#
# OAuth2 Token Refresh Test for Staging
# =====================================
#
# Usage:
#   ./test_oauth_stage.sh mock          # Run mock test
#   ./test_oauth_stage.sh mock-all      # Run all mock scenarios
#   ./test_oauth_stage.sh list          # List Google credentials
#   ./test_oauth_stage.sh check 123     # Check credential ID 123
#   ./test_oauth_stage.sh refresh 123   # Refresh credential ID 123
#   ./test_oauth_stage.sh expire 123    # Force expire credential ID 123
#

CONTAINER="workflow_backend_stage"

# Colors
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
BLUE='\033[94m'
RESET='\033[0m'
BOLD='\033[1m'

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "${RED}Error: Container ${CONTAINER} is not running${RESET}"
    echo "Available containers:"
    docker ps --format '  {{.Names}}'
    exit 1
fi

case "$1" in
    mock)
        echo -e "${BOLD}Running Mock OAuth Test...${RESET}"
        docker exec -it $CONTAINER python -c "
import time
import json
from unittest.mock import Mock, patch

# Create mock node context
def create_mock_context():
    m = Mock()
    m.name = 'Test'
    m.type = 'gmail'
    m.parameters = Mock()
    m.parameters.model_dump = Mock(return_value={})
    m.credentials = {}
    m.position = [0, 0]
    w = Mock()
    w.connections = {}
    w.id = 1
    return m, w, {}

# Mock credential
cred = {
    'clientId': 'mock.apps.googleusercontent.com',
    'clientSecret': 'mock_secret',
    'accessTokenUrl': 'https://oauth2.googleapis.com/token',
    'authentication': 'header',
    'oauthTokenData': {
        'access_token': 'old_token',
        'refresh_token': 'mock_refresh',
        'expires_at': int(time.time()) - 100,
        'token_type': 'Bearer'
    }
}

from nodes.gmail import GmailNode
n, w, e = create_mock_context()
node = GmailNode(n, w, e)

print(f'Token expired: {node._is_token_expired(cred[\"oauthTokenData\"])}')

def mock_post(*a, **k):
    r = Mock()
    r.status_code = 200
    r.json.return_value = {'access_token': f'new_token_{int(time.time())}', 'expires_in': 3600}
    r.text = '{}'
    return r

with patch('requests.post', side_effect=mock_post):
    result = node.refresh_token(cred)
    if result:
        print(f'✅ SUCCESS: Token refreshed!')
        print(f'New token: {result[\"oauthTokenData\"][\"access_token\"][:30]}...')
    else:
        print('❌ FAILED: No result')
"
        ;;

    mock-all)
        echo -e "${BOLD}Running All Mock Scenarios...${RESET}"
        docker exec -it $CONTAINER python -c "
import time
import json
from unittest.mock import Mock, patch

def create_mock_context():
    m = Mock()
    m.name = 'Test'
    m.type = 'gmail'
    m.parameters = Mock()
    m.parameters.model_dump = Mock(return_value={})
    m.credentials = {}
    m.position = [0, 0]
    w = Mock()
    w.connections = {}
    w.id = 1
    return m, w, {}

cred = {
    'clientId': 'mock.apps.googleusercontent.com',
    'clientSecret': 'mock_secret',
    'accessTokenUrl': 'https://oauth2.googleapis.com/token',
    'authentication': 'header',
    'oauthTokenData': {
        'access_token': 'old',
        'refresh_token': 'mock_refresh',
        'expires_at': int(time.time()) - 100,
    }
}

from nodes.gmail import GmailNode

scenarios = {
    'success': (200, {'access_token': 'new', 'expires_in': 3600}),
    'invalid_grant': (400, {'error': 'invalid_grant'}),
    'server_error': (500, {'error': 'internal'}),
}

results = {}
for name, (code, resp) in scenarios.items():
    n, w, e = create_mock_context()
    node = GmailNode(n, w, e)
    
    def make_mock(c, r):
        def mock_post(*a, **k):
            m = Mock()
            m.status_code = c
            m.json.return_value = r
            m.text = json.dumps(r)
            return m
        return mock_post
    
    try:
        with patch('requests.post', side_effect=make_mock(code, resp)):
            result = node.refresh_token(cred.copy())
            results[name] = '✅ PASS' if result else '❌ FAIL'
    except ValueError as e:
        if 'invalid_grant' in str(e) and name == 'invalid_grant':
            results[name] = '✅ PASS (caught invalid_grant)'
        else:
            results[name] = f'❌ FAIL: {e}'
    except Exception as e:
        if name == 'server_error':
            results[name] = '✅ PASS (caught error)'
        else:
            results[name] = f'❌ FAIL: {e}'

print()
print('='*50)
print('RESULTS')
print('='*50)
for name, result in results.items():
    print(f'  {name}: {result}')
"
        ;;

    list)
        echo -e "${BOLD}Listing Google Credentials...${RESET}"
        docker exec -it $CONTAINER python -c "
from database.config import get_sync_session_manual
from models.credential import Credential

types = ['gmailOAuth2', 'googleDriveApi', 'googleSheetsApi', 
         'googleCalendarApi', 'googleDocsApi', 'googleFormApi']

with get_sync_session_manual() as s:
    creds = s.query(Credential).filter(Credential.type.in_(types)).all()
    
    if not creds:
        print('No Google credentials found')
    else:
        print()
        print(f'{\"ID\":<6} {\"Type\":<22} {\"Name\":<30} {\"User\":<6}')
        print('-' * 70)
        for c in creds:
            print(f'{c.id:<6} {c.type:<22} {c.name[:28]:<30} {c.user_id:<6}')
        print(f'\nTotal: {len(creds)}')
"
        ;;

    check)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Credential ID required${RESET}"
            echo "Usage: $0 check <credential_id>"
            exit 1
        fi
        echo -e "${BOLD}Checking Credential ID: $2${RESET}"
        docker exec -it $CONTAINER python -c "
import time
from database.config import get_sync_session_manual
from models.credential import Credential
from utils.encryption import decrypt_data

cred_id = $2

with get_sync_session_manual() as s:
    cred = s.query(Credential).filter(Credential.id == cred_id).first()
    
    if not cred:
        print(f'❌ Credential {cred_id} not found')
        exit(1)
    
    print(f'Type: {cred.type}')
    print(f'Name: {cred.name}')
    print(f'User ID: {cred.user_id}')
    
    data = decrypt_data(cred.encrypted_data)
    oauth = data.get('oauthTokenData', {})
    
    print(f'Has access_token: {bool(oauth.get(\"access_token\"))}')
    print(f'Has refresh_token: {bool(oauth.get(\"refresh_token\"))}')
    
    exp = oauth.get('expires_at', 0)
    if exp:
        now = int(time.time())
        if exp > now:
            print(f'✅ Expires in: {(exp - now) // 60} minutes')
        else:
            print(f'⚠️  EXPIRED: {(now - exp) // 60} minutes ago')
    
    print()
    print('To refresh: $0 refresh $2')
"
        ;;

    refresh)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Credential ID required${RESET}"
            echo "Usage: $0 refresh <credential_id>"
            exit 1
        fi
        echo -e "${BOLD}Refreshing Credential ID: $2${RESET}"
        docker exec -it $CONTAINER python -c "
import time
from unittest.mock import Mock
from database.config import get_sync_session_manual
from models.credential import Credential
from utils.encryption import decrypt_data, encrypt_data

cred_id = $2

def create_mock_context():
    m = Mock()
    m.name = 'Test'
    m.type = 'gmail'
    m.parameters = Mock()
    m.parameters.model_dump = Mock(return_value={})
    m.credentials = {}
    m.position = [0, 0]
    w = Mock()
    w.connections = {}
    w.id = 1
    return m, w, {}

node_map = {
    'gmailOAuth2': ('nodes.gmail', 'GmailNode'),
    'googleDriveApi': ('nodes.googleDrive', 'GoogleDriveNode'),
    'googleSheetsApi': ('nodes.googleSheets', 'GoogleSheetsNode'),
    'googleCalendarApi': ('nodes.googleCalendar', 'GoogleCalendarNode'),
    'googleDocsApi': ('nodes.googleDocs', 'GoogleDocsNode'),
    'googleFormApi': ('nodes.googleForm', 'GoogleFormNode'),
}

with get_sync_session_manual() as s:
    cred = s.query(Credential).filter(Credential.id == cred_id).first()
    
    if not cred:
        print(f'❌ Credential {cred_id} not found')
        exit(1)
    
    print(f'Type: {cred.type}')
    print(f'Name: {cred.name}')
    
    if cred.type not in node_map:
        print(f'❌ Unknown type: {cred.type}')
        exit(1)
    
    data = decrypt_data(cred.encrypted_data)
    oauth = data.get('oauthTokenData', {})
    
    if not oauth.get('refresh_token'):
        print('❌ No refresh token available')
        exit(1)
    
    mod_name, cls_name = node_map[cred.type]
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    
    n, w, e = create_mock_context()
    node = cls(n, w, e)
    
    print('Refreshing token...')
    try:
        new_data = node.refresh_token(data)
        
        if new_data:
            new_oauth = new_data.get('oauthTokenData', {})
            print(f'✅ Token refreshed!')
            print(f'New token: {new_oauth.get(\"access_token\", \"\")[:30]}...')
            
            cred.encrypted_data = encrypt_data(new_data)
            s.commit()
            print('✅ Saved to database')
        else:
            print('❌ No data returned')
            
    except ValueError as e:
        if 'invalid_grant' in str(e):
            print(f'❌ TOKEN REVOKED: {e}')
            print('⚠️  User must reconnect their Google account!')
        else:
            print(f'❌ Error: {e}')
    except Exception as e:
        print(f'❌ Error: {e}')
"
        ;;

    expire)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Credential ID required${RESET}"
            echo "Usage: $0 expire <credential_id>"
            exit 1
        fi
        echo -e "${BOLD}Force Expiring Credential ID: $2${RESET}"
        docker exec -it $CONTAINER python -c "
import time
from database.config import get_sync_session_manual
from models.credential import Credential
from utils.encryption import decrypt_data, encrypt_data

cred_id = $2

with get_sync_session_manual() as s:
    cred = s.query(Credential).filter(Credential.id == cred_id).first()
    
    if not cred:
        print(f'❌ Credential {cred_id} not found')
        exit(1)
    
    data = decrypt_data(cred.encrypted_data)
    oauth = data.get('oauthTokenData', {})
    
    old_exp = oauth.get('expires_at', 'N/A')
    oauth['expires_at'] = int(time.time()) - 3600  # 1 hour ago
    
    print(f'Old expires_at: {old_exp}')
    print(f'New expires_at: {oauth[\"expires_at\"]} (1 hour ago)')
    
    data['oauthTokenData'] = oauth
    cred.encrypted_data = encrypt_data(data)
    s.commit()
    
    print('✅ Token forced to expire!')
    print(f'Now run: ./test_oauth_stage.sh refresh {cred_id}')
"
        ;;

    *)
        echo -e "${BOLD}OAuth2 Token Refresh Test for Staging${RESET}"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  mock          Run mock test (no real credentials needed)"
        echo "  mock-all      Run all mock scenarios"
        echo "  list          List all Google credentials in database"
        echo "  check <id>    Check credential status (dry run)"
        echo "  refresh <id>  Actually refresh a credential's token"
        echo "  expire <id>   Force a credential to expire (for testing)"
        echo ""
        echo "Examples:"
        echo "  $0 mock"
        echo "  $0 list"
        echo "  $0 check 123"
        echo "  $0 expire 123"
        echo "  $0 refresh 123"
        ;;
esac
