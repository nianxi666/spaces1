.PHONY: help install run test test-setup mock-app test-basic clean

help:
	@echo "WebSocket Spaces Testing Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install       - Install all dependencies"
	@echo ""
	@echo "Running:"
	@echo "  make run           - Start the Flask app (port 5001)"
	@echo "  make mock-app      - Start mock inference app"
	@echo "  make test-setup    - Create a test WebSocket space"
	@echo ""
	@echo "Testing:"
	@echo "  make test-basic    - Run basic functionality tests"
	@echo "  make test-verbose  - Run tests with verbose output"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         - Remove temporary files"
	@echo ""
	@echo "Full Testing Flow:"
	@echo "  1. Terminal 1: make run"
	@echo "  2. Terminal 2: make test-setup"
	@echo "  3. Terminal 3: make mock-app SPACE=TestSpace_..."
	@echo "  4. Browser:   http://localhost:5001 and test the space"
	@echo ""

install:
	pip install -r requirements.txt
	pip install python-socketio python-engineio

run:
	python run.py

run-debug:
	python -c "from project import create_app; app = create_app(); app.run(host='0.0.0.0', port=5001, debug=True)"

mock-app:
	@if [ -z "$(SPACE)" ]; then \
		echo "Usage: make mock-app SPACE='YourSpaceName'"; \
		exit 1; \
	fi
	python mock_app.py --host http://localhost:5001 --spaces "$(SPACE)" --verbose

test-setup:
	python test_websockets.py --setup-space --host http://localhost:5001

test-basic:
	python test_websockets.py --host http://localhost:5001

test-verbose:
	python test_websockets.py --host http://localhost:5001 --verbose

test-all: test-basic test-verbose

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -delete
	rm -f .DS_Store
	rm -f *.log

.DEFAULT_GOAL := help
