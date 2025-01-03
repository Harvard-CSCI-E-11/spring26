pytest:
	. venv/bin/activate ; 	pytest .

pylint:
	. venv/bin/activate ; pylint .

deploy:
	sam validate
	sam validate --lint
	sam build
	sam deploy
	sam logs --stack-name leaderboard --watch

# Create the virtual environment and install both host requirements
# and the lambda requirements for testing
venv:
	python3 -m venv venv
	. venv/bin/activate ; pip install --upgrade pip
	. venv/bin/activate ; pip install -r requirements.txt
	. venv/bin/activate ; pip install -r src/requirements.txt

.PHONY: venv
