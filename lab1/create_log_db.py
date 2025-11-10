"""
CSCI E-11: Lab #1

Create a database from the bad password attempts in a logfile created using:
sudo journalctl --output=short-full  --since "14 days ago" -g  'Invalid user' > attacks.log

Then use this program to store the results in a database.
"""

import sqlite3
import argparse
import re

from datetime import datetime, timezone

DATABASE_FILE="attacks.db"
SCHEMA="""
DROP TABLE IF EXISTS logs;
CREATE TABLE IF NOT EXISTS logs (rowid INTEGER PRIMARY KEY,
           t INT,
           user TEXT,
           host TEXT,
           port INT);
"""

# pylint: disable=line-too-long
SSH_LOG_RE = re.compile(r"^... (\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d) ... (\S+) sshd.(\d+).: Invalid user (\S+) from (\S+) port (\d+)$")


def load_file_to_sql(f,conn):
    """Loads a Linux syslog file into SQL to make analysis easier"""
    cur = conn.cursor()
    for line in f:
        m = SSH_LOG_RE.search(line)
        if m:
            when = m.group(1)
            log_host = m.group(2) # pylint: disable=unused-variable
            pid  = m.group(3)     # pylint: disable=unused-variable
            user = m.group(4)
            host = m.group(5)
            port = m.group(6)
            dt = datetime.strptime( when, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            time_t = int(dt.timestamp())
            cur.execute("INSERT INTO logs (t,user,host,port) VALUES (?,?,?,?)",
                        (time_t, user, host, port))
    conn.commit()

def main():
    """Called from __main__"""
    parser = argparse.ArgumentParser(description="Load Invalid user log entries from sshd into a SQL database",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("infile",help="input file, or - for stdin")
    args = parser.parse_args()
    infile = "/dev/stdin" if args.infile=='-' else args.infile

    with open(infile,'r',encoding='utf-8') as fin:
        conn = sqlite3.connect(DATABASE_FILE)
        c = conn.cursor()
        c.executescript(SCHEMA)
        load_file_to_sql(fin, conn)
        conn.close()

if __name__=="__main__":
    main()
