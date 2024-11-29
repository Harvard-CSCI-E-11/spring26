import sqlite3
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
con  = sqlite3.connect("/home/ec2-user/students.db")
cur  = con.cursor()
try:
    cur.execute("Create table students(name,email,student_id,gpa,sat);")
except sqlite3.OperationalError:
    cur.execute("delete from students;")

# Generate 100 fake student records
for _ in range(100):
    name = fake.name()
    email = fake.email(safe=False)
    student_id = f"S{fake.random_int(min=10000, max=99999)}"
    gpa = round(random.uniform(2.0, 4.0), 2)
    sat_score = random.randint(400, 1600)
    cur.execute("insert into students values (?,?,?,?,?);",
                (name,email,student_id,gpa,sat_score))
con.commit()
