"""image_controller: Controlls all aspects of uploading, downloading,
listing, and processing JPEG images.

"""

################################################################
##
# Image APIs. All of these need to only be POST to avoid an api_key
# from being written into the logfile
##

import os
import json
import socket

import click
import boto3
from botocore.exceptions import BotoCoreError,ClientError

from flask import request, jsonify, current_app, redirect

from .db import get_db
from . import apikey
from . import message_controller

S3_BUCKET = socket.gethostname().replace('.','-') + '-lab5-bucket'
MAX_IMAGE_SIZE=10_000_000
JPEG_MIME_TYPE = 'image/jpeg'

# Define the Cross Origin Resource Sharing Policy for the S3 bucket.
# This tells the browser that it is safe to retrieve the S3 objects it gets the redirect
# from the application.
# See:
# https://en.wikipedia.org/wiki/Cross-origin_resource_sharing
# https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS

CORS_CONFIGURATION = {
    'CORSRules': [
        {
            'AllowedOrigins': ['*'],               # Allow all origins with presigned POST and GETs
            'AllowedMethods': ['GET', 'POST', 'PUT'],     # Methods to allow
            'AllowedHeaders': ['*'],               # Allow all headers
            'MaxAgeSeconds': 3000                  # Cache duration for preflight requests
        }
    ]
}


def recognize_celebrities(bucket_name, object_key):
    """
    Recognizes celebrities in an image stored in an S3 bucket using Amazon Rekognition.

    Args:
        bucket_name (str): The name of the S3 bucket.
        object_key (str): The key of the JPEG file in the S3 bucket.

    Returns:
        list: A list of dictionaries containing information about recognized celebrities.
    """
    # Initialize the Rekognition client
    rekognition_client = boto3.client('rekognition')

    # Call the recognize_celebrities API
    try:
        response = rekognition_client.recognize_celebrities(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            }
        )
        # Extract and return details about recognized celebrities as a block of HTML
        return response.get('CelebrityFaces', [])
    except BotoCoreError as e:
        print(f"Error: {e}")
        return None

@click.command('init-s3')
def create_bucket_and_apply_cors():
    """Check to see if the bucket exists and create it if it does not."""
    s3 = boto3.client('s3')

    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            # Bucket does not exist; create it
            s3.create_bucket(Bucket=S3_BUCKET)
            click.echo(f'Created bucket {S3_BUCKET}')
        else:
            print(f"Error checking bucket: {e}")
            raise

    # Apply the CORS policy to the S3 bucket
    s3.put_bucket_cors( Bucket=S3_BUCKET,
                        CORSConfiguration=CORS_CONFIGURATION )
    click.echo(f'CORS policy applied to {S3_BUCKET}')

def list_images():
    """Return an array of dicts for all the images.

    NOTE: For a production system, we would want to include OFFSET and
    LIMIT to restrict to ~100 responses.

    """
    db = get_db()
    return db.execute('SELECT * FROM images').fetchall()

def get_image_info(image_id):
    """Return a dict for a specific image."""
    db = get_db()
    return db.execute('SELECT * FROM images WHERE image_id=?',(image_id,)).fetchone()

def new_image(api_key_id, linked_message_id, s3key):
    """Create a new image in the database"""
    db = get_db()
    cur  = db.cursor()
    cur.execute("""
        INSERT into images (s3key,linked_message_id, created_by)
        VALUES (?, ?, ?)
        """,(s3key,linked_message_id, api_key_id))
    db.commit()
    return cur.lastrowid        # return the row inserted into images

def init_app(app):
    """Initialize the app and register the paths."""
    def presigned_url_for_s3key(s3key):
        s3 = boto3.session.Session().client( "s3" )
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET,
                    'Key': s3key},
            ExpiresIn=3600)     # give an hour
        return presigned_url

    @app.route('/api/post-image', methods=['POST'])
    def api_new_image():
        """Use the AWS S3 API to get a presigned post that the client can use to upload to S3
        :param api_key: the user's api_key
        :param api_secret_key: the user's api_secret_key
        :param message: the message to post
        :return: JSON containing the post to use for uploading the image.
                 The client will post the image directly to S3.
                 if error, JSON containing 'error:<message>'
        """

        # If the bucket does not exist, tell the user
        s3 = boto3.session.Session().client( "s3" )
        try:
            s3.head_bucket(Bucket=S3_BUCKET)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                error_message = 'S3 bucket does not exist'
            else:
                error_message = f'S3 error: {e}'
            return {'error':error_message}

        # First validate the API key and post the message
        api_key_id = apikey.validate_api_key_request()
        message    = request.values.get('message')
        message_id = message_controller.post_message(api_key_id, message)

        # Now get params for the signed S3 POST
        s3key = "images/" + os.urandom(8).hex() + ".jpeg"
        presigned_post = s3.generate_presigned_post(
            Bucket=S3_BUCKET,
            Key=s3key,
            Conditions=[
                {"Content-Type": JPEG_MIME_TYPE}, # Explicitly allow Content-Type header
                ["content-length-range", 1, current_app.config['MAX_IMAGE_SIZE']]
            ],
            Fields= { 'Content-Type': JPEG_MIME_TYPE },
            ExpiresIn=120)      # in seconds

        # Finally, record the image in the database and get its image_id
        image_id = new_image(api_key_id, message_id, s3key)

        # Return the presigned_post and the image_id to the client
        app.logger.info("delivered presigned api_key_id=%s s3_key=%s image_id=%s",
                        api_key_id,presigned_post,image_id)
        return jsonify({'presigned_post':presigned_post,'image_id':image_id})

    app.cli.add_command(create_bucket_and_apply_cors)


