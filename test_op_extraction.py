#!/usr/bin/env python3
"""Debug operation extraction from GitHub TypeScript source."""
import re

# Read GitHub source
with open('input_sources/github/Github.node.ts') as f:
    content = f.read()

# Find execute method
exec_match = re.search(r'async execute\s*\([^)]*\)[^{]*\{', content)
if exec_match:
    print(f'Execute starts at position {exec_match.start()}')
    print(f'Match: {content[exec_match.start():exec_match.end()]}')
    
    # Extract body using brace matching
    start = exec_match.end()
    depth = 1
    end = start
    while end < len(content) and depth > 0:
        if content[end] == '{':
            depth += 1
        elif content[end] == '}':
            depth -= 1
        end += 1
    
    execute_body = content[start-1:end]
    print(f'Execute body length: {len(execute_body)}')
    
    # Try resource pattern
    resource_pattern = r"if\s*\(\s*resource\s*===?\s*['\"](\w+)['\"]\s*\)"
    resource_matches = list(re.finditer(resource_pattern, execute_body))
    print(f'Resource matches: {len(resource_matches)}')
    for m in resource_matches[:5]:
        print(f'  - {m.group(1)}')
else:
    print("Execute method NOT FOUND")
