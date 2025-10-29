#
# Master makefile to check all of the projects in this repo.
#

lint:
	for dir in lab? ; do (cd $$dir && pwd && make lint) ; done

distclean:
	for dir in lab? ; do (cd $$dir && pwd && make distclean) ; done

update:
	@echo Checking for post recent compatiable version of each python module
	@echo Tehn will lock and install
	for dir in lab? ; do (cd $$dir && pwd && poetry update) ; done
