#!/usr/bin/env python3
import time
from pathlib import Path
from runtime.executor import create_executor, ExecutionStatus

repo_root = Path('.')
executor = create_executor(repo_root=repo_root, max_steps=10, register_implementations=True)

marker='tmp_marker.txt'

def long_running_skill(ctx):
    for i in range(1000):
        ctx.check_deadline()
        time.sleep(0.01)
    Path(marker).write_text('done')
    return {'result':'ok'}

executor.register_implementation('test-timeout', long_running_skill)
res = executor.execute('test-timeout', {}, 'CTX-TIMEOUT')
print('status=', res.status)
print('errors=', res.errors)
print('trace_last=', res.trace[-1] if res.trace else None)
