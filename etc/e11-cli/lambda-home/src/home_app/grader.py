"""
Remote grader
"""


import base64
import json
import logging
import os
import time
import sys
from typing import Any, Dict, Tuple
from os.path import dirname

import boto3

from e11.e11core.context import build_ctx
from e11.e11core.loader import discover_and_run
from e11.e11core import ssh as e11ssh

from .common import get_logger,smash_email,add_user_log,User,Session

LOGGER = get_logger("grader")

def grade_student_vm(*,user:User, lab:str, key_pem:str):
    """Run grading by SSHing into the student's VM and executing tests via shared runner."""

    add_user_log(None, user_id, 'Grading lab {lab} starts')

    smashed = smash_email(user.email)

    # Build context and mark grader mode
    os.environ["E11_MODE"] = "grader"
    ctx = build_ctx(lab)
    if smashed: ctx["smashedemail"] = smashed
    ctx["public_ip"] = user.ipaddr  # ensure provided IP used

    LOGGER.info("SSH connect to %s (lab=%s)", ctx.get("public_ip"), lab)
    e11ssh.configure(host=ctx["public_ip"], username="ubuntu", port=22, pkey_pem=key_pem, timeout=10)
    e11ssh.set_working_dir(ctx["labdir"])

    try:
        summary = discover_and_run(ctx)
        add_user_log(None, user.user_id, 'Grading lab {lab} ends')
        return summary
    finally:
        e11ssh.close()
