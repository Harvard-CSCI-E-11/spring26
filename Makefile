#
# Master makefile to check all of the projects in this repo.
#


lint:
	for dir in lab2 lab3 lab4 lab5 lab6 lab7 ; do (cd $$dir && pwd && make lint) ; done
