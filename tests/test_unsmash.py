import tempfile
import os
import sys
from os.path import dirname,abspath,join

PARENT_DIR = dirname(dirname(abspath(__file__)))

sys.path.append(PARENT_DIR)

import unsmash                  # noqa: E402 F401

INFILE="""
My host is smashedemail.csci-e-11.org
My host is also smashedemail-lab3.csci-e-11.org
"""

EMAIL="student@fas.harvard.edu"

OUTFILE="""
My host is studentfas.csci-e-11.org
My host is also studentfas-lab3.csci-e-11.org
"""

def test_unsmash():
    smashed_email = unsmash.make_smashed_email(EMAIL)
    assert  smashed_email == "studentfas"
    with tempfile.TemporaryDirectory() as td:
        with open( join(td,"infile"), 'w') as infile:
            infile.write(INFILE)

        unsmash.transform_file(join(td,"infile"), smashed_email)
        with open( join(td,"infile"), 'r') as outfile:
            buf = outfile.read()

        assert OUTFILE == buf
