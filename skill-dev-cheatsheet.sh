#!/bin/bash
# Quick Skill Development Cheat Sheet
# Save as: ~/skill-dev-cheatsheet.sh
# Usage: source ~/skill-dev-cheatsheet.sh

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║        SKILL DEVELOPMENT - QUICK REFERENCE CARD              ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🆕 CREATE A NEW SKILL${NC}"
echo "  make new-skill NAME=my_skill"
echo ""

echo -e "${BLUE}✅ VALIDATE & TEST${NC}"
echo "  make validate-skill NAME=my_skill"
echo "  make test-skill NAME=my_skill"
echo "  make test-skill-cov NAME=my_skill"
echo ""

echo -e "${BLUE}📝 REGISTER & INSPECT${NC}"
echo "  make register-skill NAME=my_skill"
echo "  make skill-info NAME=my_skill"
echo "  make list-skills"
echo ""

echo -e "${BLUE}🚀 RUN A SKILL (Python)${NC}"
echo "  python -c \""
echo "from agentic_system.runtime import ExecutionContext"
echo "from agentic_system.runtime.registry import get_skill_registry"
echo "from agentic_system.integrations.tasks import register_skills_and_agents"
echo ""
echo "register_skills_and_agents()"
echo "registry = get_skill_registry()"
echo "context = ExecutionContext(trace_id='t1', job_id='j1', agent_id='a1')"
echo ""
echo "result = registry.execute("
echo "    name='translate',"
echo "    input_data={'text': 'Hello!'},"
echo "    context=context"
echo ")"
echo "print(result)"
echo "\""
echo ""

echo -e "${BLUE}🤖 BOUNDED AUTONOMY${NC}"
echo "  make plan TASK='Create X' FILES='src/'"
echo "  make review FILES='src/skills/my_skill.py'"
echo "  make check-compliance FILES='src/skills/my_skill.py,tests/'"
echo ""

echo -e "${YELLOW}📚 DOCUMENTATION${NC}"
echo "  cat docs/SKILL_DEVELOPMENT.md"
echo "  cat docs/HOW_TO_RUN_SKILLS.md"
echo "  cat docs/SUCCESS_SUMMARY.md"
echo ""

echo -e "${GREEN}✨ EXAMPLE WORKFLOW${NC}"
echo "  1. make new-skill NAME=sentiment"
echo "  2. vim src/agentic_system/skills/sentiment.py"
echo "  3. make validate-skill NAME=sentiment"
echo "  4. make test-skill NAME=sentiment"
echo "  5. make register-skill NAME=sentiment"
echo "  6. make skill-info NAME=sentiment"
echo "  7. python examples/run_sentiment_skill.py"
echo ""

echo -e "${GREEN}🎯 FILE LOCATIONS${NC}"
echo "  Implementation: src/agentic_system/skills/my_skill.py"
echo "  Tests:         tests/unit/test_my_skill_skill.py"
echo "  Docs:          skills/my_skill/SKILL.md"
echo "  Examples:      examples/my_skill_example.py"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Need help? Run: make help"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
