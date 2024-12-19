import pytest
import os

def pytest_runtest_setup(item):
    if "docker" in item.keywords and os.getenv("IS_DOCKER") != "true":
        pytest.skip("Skipping Docker-only test because IS_DOCKER is not set.")


# run pytest -m 'docker' to run docker-specific tests
def pytest_collection_modifyitems(config, items):
    if not config.getoption("-m") or "docker" not in config.getoption("-m"):
        skip_docker = pytest.mark.skip(reason="Skipping Docker-only tests")
        for item in items:
            if "docker" in item.keywords:
                item.add_marker(skip_docker)
