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
rekognition = boto3.client("rekognition")


def recognize_celebrities(bucket_name, object_key):
    """
    Recognizes celebrities in an image stored in an S3 bucket using Amazon Rekognition.

    Args:
        bucket_name (str): The name of the S3 bucket.
        object_key (str): The key of the JPEG file in the S3 bucket.

    Returns:
        list: A list of dictionaries containing information about recognized celebrities.
    """

    # Call the recognize_celebrities API
    try:
        current_app.logger.info(
            "rekognize bucket_name=%s object_key=%s", bucket_name, object_key
        )
        response = rekognition.recognize_celebrities(
            Image={"S3Object": {"Bucket": bucket_name, "Name": object_key}}
        )
        # Extract and return details about recognized celebrities as a block of HTML
        return response.get("CelebrityFaces", [])
    except BotoCoreError as e:
        current_app.logger.error("Error: %s", e)
        return []


# The actual celebrity recognizer.
def annotate_row(db,row):
    """
    For each row:
    1. If we don't celeb info for it, generate the JSON and store that in the database
    2. If we get an error, delete the image from the database
    3. Add a signed url for the s3key
    """
    conn = db.get_db_conn()
    if row["attribs"]:
        celeb = json.loads(row["attribs"])
        del row["attribs"]  # remove undecoded
    else:
        # Get the celeb
        try:
            celeb = recognize_celebrities(S3_BUCKET, row["s3key"])
            conn.execute(
                "UPDATE images set attribs=? where s3key=?",
                (json.dumps(celeb), row["s3key"]),
            )
            conn.commit()
        except rekognition.exceptions.InvalidS3ObjectException as e:
            current_app.logger.error(
                "InvalidS3ObjectException: s3key=%s. e=%s", row["s3key"], str(e)
            )  # pylint: disable=line-too-long
    row["celeb"] = celeb
