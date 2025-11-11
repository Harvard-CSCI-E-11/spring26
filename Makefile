#
# Master makefile to check all of the projects in this repo.
#

ALLDIRS := $(wildcard lab?) etc/e11-cli etc/e11-cli/lambda-home etc/e11-cli/lambda-users-db staff/leaderboard

lint-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && make lint) ; done

check-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && make check) ; done

distclean-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && make distclean) ; done

update-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && pwd && poetry update) ; done

sync-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && pwd && poetry sync) ; done
