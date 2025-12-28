#
# Master makefile to check all of the projects in this repo.
#

ALLDIRS := $(wildcard lab*) etc/e11-cli $(wildcard etc/e11-cli/lambda-*) etc/e11-cli/e11admin

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

lock-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && pwd && poetry lock) ; done

install:
	(cd etc/e11-cli; make lint && pipx install . --force)

clean-all:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd $$dir && poetry env remove) ; done
