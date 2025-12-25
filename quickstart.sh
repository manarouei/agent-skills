#!/bin/bash
# Quick start script for local development

set -e

echo "🚀 Agentic System Quick Start"
echo "=============================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env and add your AGENTIC_ANTHROPIC_API_KEY"
    exit 1
fi

# Check if API key is set
if grep -q "your-anthropic-api-key-here" .env; then
    echo "❌ Please set AGENTIC_ANTHROPIC_API_KEY in .env file"
    exit 1
fi

echo "✅ Environment configuration found"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# Start infrastructure
echo ""
echo "🐳 Starting infrastructure (RabbitMQ + Redis)..."
docker compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if services are healthy
if ! docker compose ps | grep -q "healthy"; then
    echo "⚠️  Services may not be fully healthy yet. Continuing anyway..."
fi

echo "✅ Infrastructure ready"
echo ""
echo "📦 Installing Python dependencies..."
pip install -e ".[dev]" > /dev/null 2>&1 || pip install -e .

echo "✅ Dependencies installed"
echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Start FastAPI server:"
echo "     uvicorn agentic_system.api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  2. In another terminal, start Celery worker:"
echo "     celery -A agentic_system.integrations.tasks worker --loglevel=info"
echo ""
echo "  3. Access API docs:"
echo "     http://localhost:8000/docs"
echo ""
echo "  4. RabbitMQ Management UI:"
echo "     http://localhost:15672 (guest/guest)"
echo ""
echo "  5. Run tests:"
echo "     pytest"
echo ""
echo "📚 See README.md for full documentation"
