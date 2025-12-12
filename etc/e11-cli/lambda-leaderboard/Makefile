# This needs to be updated to pyproject.toml and poetry

.PHONY: install lint check test clean
install:
	poetry install --with dev

install:
	@echo "--- Installing dependencies with Poetry ---"
	poetry install --with dev

check: install vend-e11
	$(PYTHON) -m pytest --log-cli-level=DEBUG

lint: install vend-e11
	$(PYTHON) -m pylint leaderboard_app

local-debug: install vend-e11
	$(PYTHON) -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync: install
	sam sync --code --watch

deploy: install vend-e11
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

distclean:
	/bin/rm -rf .venv
	/bin/rm -f instance/message_board.db
