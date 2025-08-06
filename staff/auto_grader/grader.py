"""
grader
"""

def get_students():
    """Return a dataframe of all students read from the class list"""
    return None

def get_vm_info(student):
    """Given a student, return vm ipaddress"""

def grade_lab1():
    """Grading plan:
    1 - Student registered VM
    2 - VM pings
    3 - Can log into VM on ssh port 22 as course admin
    4 - Cannot log into VM on ssh port 80 as course admin
    5 - Cannot log into VM on port 22 as hacker.
    """


def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    parser.add_argument("lab", help="Which lab to grade", type=int)
    args = parser.parse_args()


    students = get_students()
    for studnet in students:
        if args.lab==1:
            grade_lab1(students, student)
        else:
            raise ValueError("Invalid lab")

    write_grades

if __name__=="__main__":
    main()
