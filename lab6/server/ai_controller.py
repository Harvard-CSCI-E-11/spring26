"""
ai_controller: processes the uploaded image with AWS AI service

STUDENTS - You do not need to modify this file.

"""

################################################################
##
# Image APIs. All of these need to only be POST to avoid an api_key
# from being written into the logfile
##

# Neither pyright nor pylint understanding flask route decorators.
# We fix this in pyproject.toml for pylint. The coarser fix for pyright is below:
# pyright: reportUnusedFunction=false
# pyright: reportUnusedVariable=false

import json

import boto3
from botocore.exceptions import BotoCoreError

from flask import current_app

from .image_controller import S3_BUCKET

# Initialize the Rekognition client


def recognize_celebrities(image:bytes):
    """
    Recognizes celebrities in an image stored in an S3 bucket using Amazon Rekognition.

    Args:
        image: byte array of the JPEG image

    Returns:
        list: A list of dictionaries containing information about recognized celebrities.
    """

    # Call the recognize_celebrities API
        current_app.logger.error("Error: %s", e)
        return []
