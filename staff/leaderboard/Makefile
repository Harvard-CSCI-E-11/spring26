PYTHON=python3.13
PY=.venv/bin/python

check: $(PY)
	$(PY) -m pytest --log-cli-level=DEBUG

pylint: $(PY)
	$(PY) -m pylint leaderboard_app

local-debug: $(PY)
	$(PY) -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync: $(PY)
	sam sync --code --watch

deploy: $(PY)
	make pylint
	sam validate
	sam validate --lint
	sam build
	sam deploy
	sam logs --stack-name leaderboard --tail

# Create the virtual environment and install both host requirements
# and the lambda requirements for testing
$(PY):
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -r leaderboard_app/requirements.txt

distclean:
	/bin/rm -rf .venv
	/bin/rm -f instance/message_board.db
