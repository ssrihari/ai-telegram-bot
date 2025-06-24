.PHONY: help setup run run-bg stop deploy login

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install development prerequisites (Fly CLI, Python deps)
	@echo "Setting up development environment..."
	@# Install Fly CLI if not present
	@if ! command -v flyctl > /dev/null 2>&1; then \
		echo "Installing Fly CLI..."; \
		curl -L https://fly.io/install.sh | sh; \
		echo "Add these exports to your shell profile:"; \
		echo 'export FLYCTL_INSTALL="$(shell echo $$HOME)/.fly"'; \
		echo 'export PATH="$$FLYCTL_INSTALL/bin:$$PATH"'; \
	else \
		echo "Fly CLI already installed"; \
	fi
	@# Install Python dependencies
	@if [ -f requirements.txt ]; then \
		echo "Installing Python dependencies..."; \
		pip install -r requirements.txt; \
	else \
		echo "No requirements.txt found"; \
	fi
	@echo "Setup complete!"

run: ## Start the FastAPI server
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

run-bg: ## Start the FastAPI server in background
	@echo "Starting FastAPI server in background..."
	@uvicorn main:app --host 0.0.0.0 --port 8000 --reload & echo $$! > .server.pid
	@echo "Server started with PID $$(cat .server.pid)"

stop: ## Stop the FastAPI server
	@if [ -f .server.pid ]; then \
		echo "Stopping server with PID $$(cat .server.pid)..."; \
		kill $$(cat .server.pid) 2>/dev/null || echo "Process not found"; \
		rm -f .server.pid; \
	else \
		echo "Stopping any server on port 8000..."; \
		lsof -ti:8000 | xargs kill 2>/dev/null || echo "No server running on port 8000"; \
	fi

login: ## Login to Fly.io
	flyctl auth login

deploy: ## Deploy to Fly.io
	@echo "Deploying to Fly.io..."
	@if ! flyctl status > /dev/null 2>&1; then \
		echo "App not found, launching new app..."; \
		flyctl launch --no-deploy; \
	fi
	@echo "Setting secrets..."
	@if [ -f .env ]; then \
		flyctl secrets set TELEGRAM_BOT_TOKEN=$$(grep TELEGRAM_BOT_TOKEN .env | cut -d'=' -f2) || echo "Failed to set TELEGRAM_BOT_TOKEN"; \
		flyctl secrets set OPENAI_API_KEY=$$(grep OPENAI_API_KEY .env | cut -d'=' -f2) || echo "Failed to set OPENAI_API_KEY"; \
		flyctl secrets set OPENAI_MODEL=$$(grep OPENAI_MODEL .env | cut -d'=' -f2) || echo "Failed to set OPENAI_MODEL"; \
	fi
	@if [ -f persona.md ]; then \
		flyctl secrets set SYSTEM_PROMPT="$$(cat persona.md)" || echo "Failed to set SYSTEM_PROMPT"; \
	fi
	flyctl deploy