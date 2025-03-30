.PHONY: all testall venv students clean

VENV = venv
PYTHON = python3

# Default target
all: testall

# Run the full test suite
testall: $(VENV) students
	$(VENV)/bin/$(PYTHON) tester.py --lab 5

# Set up virtual environment and install dependencies
$(VENV): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

# Sync student data from S3
students:
	aws --profile=fas s3 sync s3://cscie-11/students/ students/

# Clean up generated files
clean:
	rm -rf $(VENV) students out
