lint:
	python -m pylint *.py

# Create the virtual environment
venv:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	. venv/bin/activate ; python3 -m pip install -r requirements.txt

attack:
	. venv/bin/activate ; python3 attack_student_instances.py
