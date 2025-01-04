pytest:
	. venv/bin/activate ; 	pytest .

pylint:
	. venv/bin/activate ; pylint app

local-debug:
	. venv/bin/activate ; python -c 'from src.leaderboard_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync:
	sam sync --code --watch

deploy:
	make pylint
	sam validate
	sam validate --lint
	sam build
	sam deploy
	sam logs --stack-name leaderboard --tail

# Create the virtual environment and install both host requirements
# and the lambda requirements for testing
venv:
	python3.12 -m venv venv
	. venv/bin/activate ; pip install --upgrade pip
	. venv/bin/activate ; pip install -r requirements.txt
	. venv/bin/activate ; pip install -r app/requirements.txt

.PHONY: venv
