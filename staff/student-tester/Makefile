.PHONY: testall
testall:
	make students
	/Users/simsong/venv/bin/python3 tester.py

.PHONY: venv
venv:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt

.PHONY: students
students:
	aws --profile=fas s3 sync s3://cscie-11/students/ students/
