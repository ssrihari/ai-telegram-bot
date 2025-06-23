.PHONY: help setup

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