.PHONY: install test lint format deploy clean package help

help:
	@echo "Available targets:"
	@echo "  install  - Install Python dependencies"
	@echo "  test     - Run tests with pytest"
	@echo "  lint     - Check code quality with flake8 and black"
	@echo "  format   - Format code with black"
	@echo "  deploy   - Deploy to AWS using Serverless Framework"
	@echo "  clean    - Remove build artifacts and caches"
	@echo "  package  - Create deployment package locally"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --cov=utils --cov-report=html --cov-report=term

lint:
	flake8 lambda_function.py utils/
	black --check lambda_function.py utils/

format:
	black lambda_function.py utils/ tests/

deploy: clean check-env
	@echo "Deploying with Serverless Framework..."
	@if [ -z "$$SPREADSHEET_ID" ]; then \
		echo "Error: SPREADSHEET_ID environment variable is not set"; \
		echo "Run: source .env or export SPREADSHEET_ID=..."; \
		exit 1; \
	fi
	serverless deploy --verbose

remove:
	serverless remove

logs:
	serverless logs -f api -t

invoke-local:
	serverless invoke local -f api --data '{"httpMethod": "POST", "path": "/fetch-transactions"}'

clean:
	rm -rf package/
	rm -rf .serverless/
	rm -rf lambda.zip
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete

package: clean
	@echo "Creating Lambda package..."
	mkdir -p package
	pip install -r requirements.txt -t package/
	cp lambda_function.py package/
	cp -r utils package/
	cd package && zip -r ../lambda.zip . -x "*.pyc" -x "*__pycache__*"
	@echo "Package created: lambda.zip"

# Local development helpers
setup-dev:
	pip install -r requirements.txt
	npm install -g serverless
	serverless plugin install -n serverless-python-requirements

validate:
	@echo "Validating serverless.yml..."
	serverless print --config serverless.yml

check-env:
	@echo "Checking environment variables..."
	@[ -n "$$SPREADSHEET_ID" ] && echo "✓ SPREADSHEET_ID set" || echo "✗ SPREADSHEET_ID NOT set"
	@[ -n "$$SHEET_NAME" ] && echo "✓ SHEET_NAME set" || echo "✗ SHEET_NAME NOT set"
	@[ -n "$$GOOGLE_CREDENTIALS_JSON" ] && echo "✓ GOOGLE_CREDENTIALS_JSON set" || echo "✗ GOOGLE_CREDENTIALS_JSON NOT set"
	@[ -n "$$CA_ACCOUNT_NUMBER" ] && echo "✓ CA_ACCOUNT_NUMBER set" || echo "✗ CA_ACCOUNT_NUMBER NOT set"
	@[ -n "$$CA_PASSWORD" ] && echo "✓ CA_PASSWORD set" || echo "✗ CA_PASSWORD NOT set"
	@[ -n "$$CA_DEPARTMENT" ] && echo "✓ CA_DEPARTMENT set" || echo "✗ CA_DEPARTMENT NOT set"

info:
	serverless info
