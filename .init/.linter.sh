#!/bin/bash
cd /home/kavia/workspace/code-generation/attendance-tracker-221712-221722/firebase_functions
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

