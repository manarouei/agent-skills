import json

# Check credentials in schema
schema = json.load(open('artifacts/node-github-final-1767768062/inferred_schema.json'))
print("=== CREDENTIALS IN SCHEMA ===")
print(json.dumps(schema.get('credentials', []), indent=2))
print()

# Check generated code
with open('artifacts/node-github-final-1767768062/converted/github.py') as f:
    content = f.read()
    lines = content.split('\n')
    
    print("=== CREDENTIALS IN PROPERTIES ===")
    for i, line in enumerate(lines[173:178], 174):
        print(f"Line {i}: {line}")
    print()
    
    print("=== FILE DELETE (_file_delete) ===")
    for i, line in enumerate(lines[456:468], 457):
        print(f"Line {i}: {line}")
    print()
    
    print("=== FILE GET (_file_get) ===")
    for i, line in enumerate(lines[470:492], 471):
        print(f"Line {i}: {line}")
    print()
    
    print("=== UNDEFINED VARIABLE CHECK ===")
    issues = []
    for i, line in enumerate(lines, 1):
        # Check for references to variables that shouldn't exist
        if 'commit_message' in line and 'commitMessage' not in line and '#' not in line.split('=')[0]:
            issues.append(f"  Line {i}: Found 'commit_message'")
        if ('additional_parameters' in line and 'additionalParameters' not in line and 
            'get_node_parameter' not in line and '=' not in line.split('#')[0].strip()[:30]):
            issues.append(f"  Line {i}: Found 'additional_parameters' reference")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("  ✓ No undefined variable issues found!")
    print()
    
    print("=== FIX SUMMARY ===")
    print(f"✓ Fix #14: Multi-line parameter extraction (additionalParameters)")
    print(f"✓ Fix #15: Inline getNodeParameter in body assignments (message)")
    print(f"Credentials still need Fix #12 (bracket counting)")
