"""
Create a database from the bad password attempts in a logfile created using:
sudo journalctl --output=short-full  --since "14 days ago" -g  'Invalid user' > attacks2.log
"""

import sqlite3
import os
import re
from datetime import datetime, timezone
import time

DATABASE_FILE="logs.db"
SCHEMA="""
DROP TABLE IF EXISTS logs;
CREATE TABLE IF NOT EXISTS logs (rowid INTEGER PRIMARY KEY,
           t INT,
           user TEXT,
           host TEXT,
           port INT);
"""

SSH_LOG_RE = re.compile(r"^... (\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d) ... (\S+) sshd.(\d+).: Invalid user (\S+) from (\S+) port (\d+)$")


if __name__=="__main__":
    con = sqlite3.connect(DATABASE_FILE)
    cur = con.cursor()
    cur.executescript(SCHEMA)
    with open("attacks2.log") as f:
        for line in f:
            m = SSH_LOG_RE.search(line)
            if m:
                when = m.group(1)
                log_host = m.group(2)
                pid  = m.group(3)
                user = m.group(4)
                host = m.group(5)
                port = m.group(6)
                dt = datetime.strptime( when, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
                time_t = int(dt.timestamp())
                con.execute("INSERT INTO logs (t,user,host,port) VALUES (?,?,?,?)",
                            (time_t, user, host, port))
    con.commit()
    con.close()
