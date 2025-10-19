"""
Creates the student database and fills it with fake data
"""

from os.path import abspath,dirname,join
import sqlite3
import random
from faker import Faker

DB_FILE = join(dirname(abspath(__file__)),'students.db')

def student_database_connection():
    """Return a connection to the student database.
    If it doesn't exist, create the scehema.
    If it has no data in it, fill it.
    Note: the connection *should* get closed to prevent a memory leak.
    """
    conn  = sqlite3.connect( DB_FILE )
    c  = conn.cursor()
    try:
        # Create the table
        c.execute("Create table students(name,email,student_id,gpa,sat);")
        conn.commit()
    except sqlite3.OperationalError:
        # Table must already exist!
        pass

    r = c.execute("select count(*) from students").fetchone()
    if r[0]==0:
        make_fake_student_data(conn)
    return conn


def make_fake_student_data( conn ):
    """Given a database connection, create some fake recoreds.
    :param conn: sqlite3 database connection
    """
    c = conn.cursor()
    fake = Faker()
    # Generate 100 fake student records
    for _ in range(100):
        name = fake.name()
        email = fake.email(safe=False)
        student_id = f"S{fake.random_int(min=10000, max=99999)}"
        gpa = round(random.uniform(2.0, 4.0), 2)
        sat_score = random.randint(400, 1600)
        c.execute("insert into students values (?,?,?,?,?);",
                    (name,email,student_id,gpa,sat_score))
    conn.commit()

def show_fake_student_data( conn ):
    """Show the student data"""
    c = conn.cursor()
    for row in c.execute("select * from students"):
        print("\t".join([str(x) for x in row]))

if __name__=="__main__":
    print("student data:")
    show_fake_student_data(student_database_connection())
