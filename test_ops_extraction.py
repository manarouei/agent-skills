#!/usr/bin/env python3
"""Test operation extraction from GitHub node."""
import re

def _extract_brace_block(text, start_pos):
    brace_start = text.find('{', start_pos)
    if brace_start == -1:
        return ''
    
    depth = 1
    pos = brace_start + 1
    in_string = False
    string_char = None
    
    while pos < len(text) and depth > 0:
        c = text[pos]
        
        if not in_string and c in ('"', "'", '`'):
            in_string = True
            string_char = c
        elif in_string:
            if c == '\\':
                pos += 1
            elif c == string_char:
                in_string = False
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        
        pos += 1
    
    return text[brace_start + 1:pos - 1]

def _extract_execute_body(ts_code):
    match = re.search(r'async\s+execute\s*\([^)]*\)\s*:\s*Promise<[^>]+>\s*\{', ts_code)
    if not match:
        match = re.search(r'async\s+execute\s*\([^)]*\)\s*\{', ts_code)
    
    if not match:
        return ''
    
    brace_start = match.end() - 1
    depth = 1
    pos = brace_start + 1
    in_string = False
    string_char = None
    
    while pos < len(ts_code) and depth > 0:
        c = ts_code[pos]
        
        if not in_string and c in ('"', "'", '`'):
            in_string = True
            string_char = c
        elif in_string:
            if c == '\\':
                pos += 1
            elif c == string_char:
                in_string = False
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        
        pos += 1
    
    return ts_code[brace_start + 1:pos - 1]

def _extract_operations(execute_body):
    operations = []
    resource_pattern = r"if\s*\(\s*resource\s*===?\s*['\"](\w+)['\"]\s*\)"
    operation_pattern = r"if\s*\(\s*operation\s*===?\s*['\"](\w+)['\"]\s*\)"
    
    resource_matches = list(re.finditer(resource_pattern, execute_body))
    
    if resource_matches:
        for resource_match in resource_matches:
            resource = resource_match.group(1)
            resource_body = _extract_brace_block(execute_body, resource_match.end())
            
            for op_match in re.finditer(operation_pattern, resource_body):
                operation = op_match.group(1)
                op_body = _extract_brace_block(resource_body, op_match.end())
                operations.append((resource, operation, op_body))
    else:
        for op_match in re.finditer(operation_pattern, execute_body):
            operation = op_match.group(1)
            op_body = _extract_brace_block(execute_body, op_match.end())
            operations.append(('', operation, op_body))
    
    return operations

if __name__ == "__main__":
    with open('input_sources/github/Github.node.ts') as f:
        ts_content = f.read()

    execute_body = _extract_execute_body(ts_content)
    print(f'Execute body length: {len(execute_body)}')
    print(f'First 500 chars:')
    print(execute_body[:500])
    print('...\n')

    operations = _extract_operations(execute_body)
    print(f'Found {len(operations)} operations:')
    for res, op, code in operations[:30]:
        print(f'  {res}/{op}: {len(code)} chars')
