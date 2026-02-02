#!/usr/bin/env python3
"""Test resource extraction from GitHub TypeScript source."""
import sys
sys.path.insert(0, '.')
import re

# Manually load just the helper functions we need
def _extract_ts_value(content: str, start_pos: int) -> str:
    """Extract a TypeScript value starting from start_pos, handling nested braces/brackets."""
    if start_pos >= len(content):
        return ""
    
    # Skip whitespace
    while start_pos < len(content) and content[start_pos] in ' \t\n\r':
        start_pos += 1
    
    if start_pos >= len(content):
        return ""
    
    char = content[start_pos]
    
    # Handle string literals
    if char in ('"', "'", '`'):
        quote = char
        end = start_pos + 1
        while end < len(content):
            if content[end] == '\\' and end + 1 < len(content):
                end += 2
                continue
            if content[end] == quote:
                return content[start_pos:end + 1]
            end += 1
        return content[start_pos:end]
    
    # Handle object/array literals with brace matching
    if char in ('{', '['):
        close_char = '}' if char == '{' else ']'
        depth = 1
        end = start_pos + 1
        in_string = False
        string_char = None
        
        while end < len(content) and depth > 0:
            c = content[end]
            
            if in_string:
                if c == '\\' and end + 1 < len(content):
                    end += 2
                    continue
                if c == string_char:
                    in_string = False
            else:
                if c in ('"', "'", '`'):
                    in_string = True
                    string_char = c
                elif c == char:
                    depth += 1
                elif c == close_char:
                    depth -= 1
            end += 1
        
        return content[start_pos:end]
    
    # Handle simple values (numbers, booleans, identifiers) - read until delimiter
    end = start_pos
    while end < len(content) and content[end] not in ',}]\n\r':
        end += 1
    return content[start_pos:end].strip()

# Read the GitHub source
with open('input_sources/github/Github.node.ts') as f:
    content = f.read()

# Find resource parameter
resource_start = None
for match in re.finditer(r"name:\s*['\"]resource['\"]", content):
    pos = match.start()
    brace_pos = content.rfind('{', 0, pos)
    if brace_pos != -1:
        resource_start = brace_pos
        break

if resource_start:
    block = _extract_ts_value(content, resource_start)
    print(f"Resource block found, length: {len(block)}")
    
    # Extract options
    options = []
    options_match = re.search(r"options:\s*\[", block)
    if options_match:
        options_start = options_match.end() - 1
        options_content = _extract_ts_value(block, options_start)
        print(f"Options content length: {len(options_content)}")
        
        for opt_match in re.finditer(
            r"\{\s*name:\s*['\"]([^'\"]+)['\"].*?value:\s*['\"]([^'\"]+)['\"]",
            options_content,
            re.DOTALL
        ):
            options.append({
                "name": opt_match.group(1),
                "value": opt_match.group(2)
            })
    
    print(f"Found {len(options)} resource options:")
    for opt in options:
        print(f"  - {opt['name']}: {opt['value']}")
else:
    print("Resource parameter NOT FOUND")
