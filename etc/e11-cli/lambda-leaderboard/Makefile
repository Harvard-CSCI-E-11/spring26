# This needs to be updated to pyproject.toml and poetry

PYTHON=.venv/bin/python3.13

check: $(PYTHON) vend-e11
	$(PYTHON) -m pytest --log-cli-level=DEBUG

lint: $(PYTHON) vend-e11
	$(PYTHON) -m pylint leaderboard_app

local-debug: $(PYTHON) vend-e11
	$(PYTHON) -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync: $(PYTHON)
	sam sync --code --watch

deploy: $(PYTHON) vend-e11
	make pylint
	sam validate
	sam validate --lint
	sam build
	sam deploy
	sam logs --stack-name leaderboard --tail

# --- Custom Vendoring
.PHONY: vend-e11
vend-e11: install
	@echo "Building src/leaderboard_app/e11.whl via pip"
	( cd .. && poetry run python -m pip wheel --no-deps -w dist . )
	@echo "Installing wheel into src/leaderboard_app/ as e11.whl"
	install -d src/leaderboard_app
	install -m 444 $$(ls -t ../dist/*.whl | head -1) src/leaderboard_app/e11.whl
	@echo "OK -> src/leaderboard_app/e11.whl"



# Create the virtual environment and install both host requirements
# and the lambda requirements for testing
$(PYTHON):
	python3.13 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -r leaderboard_app/requirements.txt

distclean:
	/bin/rm -rf .venv
	/bin/rm -f instance/message_board.db
