#!/usr/bin/env python3
"""Debug script to check parsed_sections from pipeline."""
import json
import sys

result_file = sys.argv[1] if len(sys.argv) > 1 else 'artifacts/node-discord-dee667bd/pipeline_result.json'

with open(result_file) as f:
    data = json.load(f)

# Find the ingest step result
for step in data.get('step_results', []):
    if step.get('step_name') == 'ingest':
        print('=== Ingest Step Output ===')
        outputs = step.get('outputs', {})
        print('Output Keys:', list(outputs.keys()))
        ps = outputs.get('parsed_sections', {})
        print('parsed_sections keys:', list(ps.keys()) if ps else 'None')
        if ps:
            for k, v in ps.items():
                if isinstance(v, list):
                    print(f'  {k}: list({len(v)} items)')
                elif isinstance(v, dict):
                    print(f'  {k}: dict({list(v.keys())})')
                elif isinstance(v, str) and len(v) > 100:
                    print(f'  {k}: str({len(v)} chars)')
                else:
                    print(f'  {k}: {v}')
        break
