#
# Master makefile to check all of the projects in this repo.
#

lint:
	for dir in lab? ; do (cd $$dir && pwd && make lint) ; done

check-all:
	for dir in lab? ; do (cd $$dir && pwd && make check) ; done
	(cd etc/e11-cli; make check)
	(cd etc/e11-cli/lambda-home; make check)
	(cd staff/leaderboard; make check)

distclean:
	for dir in lab? ; do (cd $$dir && pwd && make distclean) ; done
	(cd etc/e11-cli && make distclean)
	(cd etc/e11-cli/lambda-home && make distclean)
	(cd etc/e11-cli/lambda-users-db && make distclean)
	(cd staff/leaderboard && make distclean)

update:
	@echo Checking for post recent compatiable version of each python module
	@echo Tehn will lock and install
	for dir in lab? ; do (cd $$dir && pwd && poetry update) ; done
