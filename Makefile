.PHONY: validate test smoke

validate:
	databricks bundle validate

test:
	pytest tests/unit/ --cov=src --cov-report=xml -v

smoke:
	databricks bundle run smoke_test_job --target dev
