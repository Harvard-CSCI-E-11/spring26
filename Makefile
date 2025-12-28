#
# Master makefile to check all of the projects in this repo.
#

ALLDIRS := $(wildcard lab*) etc/e11-cli $(wildcard etc/e11-cli/lambda-*) etc/e11-cli/e11admin

lint-all-legacy:
	for dir in $(ALLDIRS) ; do (echo "=== $$dir ===" ; cd  $$dir && make lint) ; done

lint-all:
	@fail=0; \
	for dir in $(ALLDIRS); do \
		printf "Linting %s... \033[K\r" "$$dir"; \
		if ! out=$$(cd $$dir && make -s lint </dev/null 2>&1); then \
			printf "\n"; \
			echo "=== $$dir ==="; \
			echo "$$out"; \
			fail=1; \
		fi; \
	done; \
	if [ $$fail -eq 1 ]; then \
		printf "Linting failed.\033[K\n"; \
		exit 1; \
	else \
		printf "Linting complete.\033[K\n"; \
	fi

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
