import os

import e11
import e11.__main__

def test_patched_config(_isolate_env):
    cp = e11.__main__.get_config()
    assert cp['student']['email'] == 'test@example.org' # from conftest.py
    assert cp['student']['smashedemail'] == 'testexampleorg' # from conftest.py
    assert cp['student']['public_ip'] == '127.0.0.1' # from conftest.py
