"""
image_controller: Controlls all aspects of uploading, downloading,
listing, and processing JPEG images.

STUDENTS - You do not need to make changes in this file, but you should read it.

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

import sys
import os
import json

import click

from botocore.exceptions import ClientError

from flask import request, jsonify, abort

from . import db
from . import message_controller
from .image_validate import (
    S3_BUCKET,
    make_presigned_post,
    s3_client,
    validate_image_data_length,
    validate_image_table_row,
    )

# Define the Cross Origin Resource Sharing Policy for the S3 bucket.
# This tells the browser that it is safe to retrieve the S3 objects it gets the redirect
# from the application.
# See:
# https://en.wikipedia.org/wiki/Cross-origin_resource_sharing
# https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS

CORS_CONFIGURATION = {
    "CORSRules": [
        {
            "AllowedOrigins": ["*"],  # Allow all origins with presigned POST and GETs
            "AllowedMethods": ["GET", "POST", "PUT"],  # Methods to allow
            "AllowedHeaders": ["*"],  # Allow all headers
            "MaxAgeSeconds": 3000,  # Cache duration for preflight requests
        }
    ]
}

@click.command("init-s3")
def create_bucket_and_apply_cors():
    """Check to see if the bucket exists and create it if it does not."""

    # Check for S3_BUCKET.
    # Create the bucket if it does not exist.
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        match error_code:
            case 403:
                click.echo("")
                click.echo("****************************************************************")
                click.echo(f"Cannot create bucket {S3_BUCKET}: Permission Denied")
                click.echo(f"Bucket {S3_BUCKET} exists and is owned by another AWS account")
                click.echo(f"Edit the file {__file__} and change the definition for S3_BUCKET")
                click.echo("****************************************************************")
                click.echo("")
                sys.exit(1)
            case 404:
                # Bucket does not exist; create it
                click.echo(f"Trying to create bucket {S3_BUCKET}")
                s3_client.create_bucket(Bucket=S3_BUCKET)
                click.echo(f"Created bucket {S3_BUCKET}")
            case ec:
                print(f"Error code {ec} checking bucket {S3_BUCKET}: {e}")
                sys.exit(1)

    # Apply the CORS policy to the S3 bucket.
    # If there is an existing CORS policy, this will replace it.
    s3_client.put_bucket_cors(Bucket=S3_BUCKET, CORSConfiguration=CORS_CONFIGURATION)
    click.echo(f"CORS policy applied to {S3_BUCKET}")

def list_images():
    """Return an array of dicts for all the images.
    NOTE: For a production system, we would want to include OFFSET and
    LIMIT to restrict to ~100 responses.
    """
    conn = db.get_db_conn()
    rows = conn.execute(
        """
        SELECT message_id,messages.created AS created,
               messages.message AS message, image_id,s3key, validated, celeb_json, detected_text_json,
               strftime('%s', 'now') - strftime('%s', messages.created) AS message_age_seconds,
               strftime('%s', 'now') - strftime('%s', images.created) AS image_age_seconds
        FROM messages
        LEFT JOIN images
        WHERE messages.message_id = images.linked_message_id;
        """
    ).fetchall()

    # .fetchall() returns a list of SQLIte3 Row objects.
    # Turn this into an array of dict() objects so that they can be modified.
    return [dict(row) for row in rows]

def get_image_info(image_id):
    """Return a dict for a specific image."""
    conn = db.get_db_conn()
    return conn.execute("SELECT * FROM images WHERE image_id=?", (image_id,)).fetchone()


def new_image(api_key_id, linked_message_id, s3key):
    """Create a new image in the database"""
    conn = db.get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT into images (s3key,linked_message_id, created_by)
        VALUES (?, ?, ?)
        """,
        (s3key, linked_message_id, api_key_id),
    )
    conn.commit()
    return cur.lastrowid  # return the row inserted into images

def presign_get(s3key):
    """For an s3key, created a presigned GET URL"""
    url = s3_client.generate_presigned_url(
        "get_object",                                # the S3 command to sign
        Params={"Bucket": S3_BUCKET, "Key": s3key}, # command parameters
        ExpiresIn=3600 )                             # valid for an hour
    return url

def init_app(app):
    """Initialize the app and register the paths."""

    @app.route("/api/post-image", methods=["POST"])
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
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                error_message = "S3 bucket does not exist"
            else:
                # Log the detailed error server-side, return generic error to user.
                app.logger.error("S3 error occurred: %s", e, exc_info=True)
                error_message = "An internal S3 error has occurred"
            return {"error": error_message}

        # Validate the API key
        api_key_id = message_controller.validate_api_key_request()
        message = request.values.get("message")
        try:
            image_data_length = int(request.values.get("image_data_length",0))
        except (ValueError,TypeError):
            abort( 404 )

        app.logger.debug("/api/post-image image_data_length=%s",image_data_length)

        if not validate_image_data_length(app, image_data_length):
            abort( 404 )

        # Post the message
        message_id = message_controller.post_message(api_key_id, message)
        app.logger.info("Message '%s' posted. image_data_length=%d message_id=%s",
                        message, image_data_length, message_id)

        # Now get params for the signed S3 POST
        s3key = "images/" + os.urandom(8).hex() + ".jpeg"
        presigned_post = make_presigned_post(S3_BUCKET, s3key)
        # Finally, record the image in the database and get its image_id
        image_id = new_image(api_key_id, message_id, s3key)

        # Return the presigned_post and the image_id to the client
        app.logger.info(
            "delivered presigned api_key_id=%s s3_key=%s image_id=%s",
            api_key_id,
            presigned_post,
            image_id,
        )
        return jsonify({"presigned_post": presigned_post, "image_id": image_id})

    @app.route("/api/get-images", methods=["GET"])
    def api_list_images():
        """Return an array of JSON records for each image.
        Transform the s3key into a presigned GET url.

        Note: This interface returns *all* of the images. A
        production system would return just some of them.
        """

        app.logger.info("get-images")
        conn = db.get_db_conn()
        rows = list_images()

        # Validate all of the images (delete the ones that do not validate)
        rows = [validate_image_table_row(app, conn, row) for row in rows]

        # Filter out the images that are None or that validated
        rows = [row for row in rows if (row and row['validated'])]

        # Add a signed URL to the s3key and expand the JSON if present
        for row in rows:
            row['url'] = presign_get(row['s3key'])

            try:
                row['celeb'] = json.loads(row['celeb_json'])
            except (KeyError, TypeError, ValueError) as e:
                app.logger.error("celeb_json error: %s",e)
                pass
            del row['celeb_json']

            try:
                row['detected_text'] = json.loads(row['detected_text_json'])
            except (KeyError, TypeError, ValueError) as e:
                app.logger.error("detected_text_json error: %s",e)
                pass
            del row['detected_text_json']
        return rows

    # Finally, add the command to the CLI
    app.cli.add_command(create_bucket_and_apply_cors)
