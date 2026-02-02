#!/usr/bin/env python3
"""
Agent Skills - Main entry point.

This is a thin wrapper around the CLI.

Usage:
    python main.py --help
    python main.py pipeline run type1-convert -c test-001 -s ./node.ts
    python main.py workflow run ./workflow.json
    python main.py validate gate -c test-001
"""

from src.agent_skills.cli.main import main

if __name__ == "__main__":
    main()
