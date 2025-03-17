.PHONY: testall
testall:
	make students
	/Users/simsong/venv/bin/python3 tester.py

.PHONY: students
students:
	aws --profile=fas s3 sync s3://cscie-11/students/ students/
