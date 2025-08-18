pytest:
	venv/bin/pytest --log-cli-level=DEBUG

pylint:
	venv/bin/pylint leaderboard_app

local-debug:
	. venv/bin/activate ; python -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

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
.PHONY: venv
venv:
	python3.13 -m venv venv
	venv/bin/pip install --upgrade pip
	venv/bin/pip install -r requirements.txt
	venv/bin/pip install -r leaderboard_app/requirements.txt
