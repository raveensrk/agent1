#!/usr/bin/env python3
# harness-check: {"id": "lemmax_lint", "applies": ["*.org"], "quadrant": "feedback/computational"}
"""Run lemmax's harness check on the edited .org files.

lemmax lives in its own repo now (~/repos/lemmax); the check is its
lemmax/hooks/lemmax_lint.py, reached as `lmx hook lemmax_lint.py`. It prints
path:line: message for each finding in a theory file that opts in.
With no lmx on PATH there is nothing to check.

    lemmax_lint.py FILE...      (or paths on stdin)
"""
import os
import shutil
import sys

if shutil.which("lmx"):
    os.execvp("lmx", ["lmx", "hook", "lemmax_lint.py", *sys.argv[1:]])
