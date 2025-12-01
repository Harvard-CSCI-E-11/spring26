"""
image_controller: Controlls all aspects of uploading, downloading,
listing, and processing JPEG images.

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

import os
import io
import socket
import logging

import click
import boto3
import PIL                      # Pillow

from botocore.exceptions import BotoCoreError, ClientError

from flask import request, jsonify, current_app, redirect

from . import db
from . import message_controller

S3_BUCKET = socket.gethostname().replace(".", "-") + "-lab5-bucket"
S3_REGION = "us-east-1"
MAX_IMAGE_SIZE_BYTES = 4 * 1024 * 1024
JPEG_MIME_TYPE = "image/jpeg"

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


def is_valid_jpeg(byte_array: buf) -> bool:
    """Simple program to use Pillow to validate a JPEG image"""
    try:
        img = PIL.Image.open(io.BytesIO(buf))
        return img.format == "JPEG"
    except (IOError,PIL.UnidentifiedImageError):
        return False


@click.command("init-s3")
def create_bucket_and_apply_cors():
    """Check to see if the bucket exists and create it if it does not."""
    s3 = boto3.client("s3")

    # Check for S3_BUCKET.
    # Create the bucket if it does not exist.
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            # Bucket does not exist; create it
            s3.create_bucket(Bucket=S3_BUCKET)
            click.echo(f"Created bucket {S3_BUCKET}")
        else:
            print(f"Error checking bucket: {e}")
            raise

    # Apply the CORS policy to the S3 bucket.
    # If there is an existing CORS policy, this will replace it.
    s3.put_bucket_cors(Bucket=S3_BUCKET, CORSConfiguration=CORS_CONFIGURATION)
    click.echo(f"CORS policy applied to {S3_BUCKET}")

def list_images():
    """Return an array of dicts for all the images.
    NOTE: For a production system, we would want to include OFFSET and
    LIMIT to restrict to ~100 responses.
    """
    conn = db.get_db_conn()
    rows = conn.execute(
        """
        SELECT message_id,messages.created as created,message, image_id,s3key, validated
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
        s3 = boto3.session.Session().client("s3")
        try:
            s3.head_bucket(Bucket=S3_BUCKET)
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                error_message = "S3 bucket does not exist"
            else:
                # Log the detailed error server-side, return generic error to user.
                logging.error("S3 error occurred: %s", e, exc_info=True)
                error_message = "An internal S3 error has occurred"
            return {"error": error_message}

        # Validate the API key and post the message
        api_key_id = message_controller.validate_api_key_request()
        message = request.values.get("message")
        message_id = message_controller.post_message(api_key_id, message)
        logging.info("Message %s posted. message_id=%s", message, message_id)

        # Now get params for the signed S3 POST
        s3key = "images/" + os.urandom(8).hex() + ".jpeg"
        presigned_post = s3.generate_presigned_post(
            Bucket = S3_BUCKET,
            Key = s3key,
            Conditions = [
                # Only enforce the Content-Type restriction...
                { "Content-Type": JPEG_MIME_TYPE },
                # [ "content-length-range", 1, MAX_IMAGE_SIZE_BYTES],
            ],
            Fields = { "Content-Type": JPEG_MIME_TYPE},
            ExpiresIn = 120, # in seconds
        )

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

    @app.route("/api/get-image", methods=["POST", "GET"])
    def api_get_image():
        """Given a request for an image_id, return a presigned URL that will let the client
        directly GET the image from S3. NOTE: No authenticaiton.
        """
        # Get the URN for the image_id
        image_id = request.values.get("image_id", type=int, default=0)
        s3key = get_image_info(image_id)["s3key"]
        presigned_url = presigned_url_for_s3key(s3key)
        client_ip = (
            request.headers.getlist("X-Forwarded-For")[0]
            if request.headers.getlist("X-Forwarded-For")
            else request.remote_addr
        )
        app.logger.info("%s image_id=%d s3key=%s", client_ip, image_id, s3key)
        app.logger.debug(
            "image_id=%d s3key=%s presigned_url=%s", image_id, s3key, presigned_url
        )

        # Now redirect to it.
        # Code 302 is a temporary redirect, so the next time it will need to get a new presigned URL
        return redirect(presigned_url, code=302)

    @app.route("/api/get-images", methods=["GET"])
    def api_list_images():
        """Return an array of JSON records for each image.
        Transform the s3key into a presigned GET url.

        Note: This interface returns *all* of the images. A
        production system would return just some of them.
        """

        s3 = boto3.session.Session().client("s3")
        app.logger.info("get-images")
        conn = db.get_db_conn()
        rows = list_images()
        validated_rows = []
        for row in rows:
            # for each row, add a URL to the s3key
            row['url'] = s3.generate_presigned_url( "get_object", # the S3 command
                                                    Params={"Bucket": S3_BUCKET, "Key": row['s3key'}},
                                                    ExpiresIn=3600 )  # give an hour

            # If row has not been validated yet, we need to validate it.
            if not row['validated']:

                """
                STUDENTS: PERFORM ADDITIONAL VALIDATION HERE...

                you can fetch the data with:
                r = requests.get(row['url']0
                r.content             would now be a byte array of byte image.

                You can use the is_valid_jpeg() function above to validate if it is a JPEG or not:
                validated = is_valid_jpeg(r.content)

                For now, we will assume everything is validated
                """
                validated = True

                if not validated:
                    # validation was not successful.
                    # Delete the s3 object
                    s3.delete_object(Bucket=S3_BUCKET,  Key=row['s3key'])
                    # Delete the database record
                    c = conn.cursor()
                    c.execute("DELETE FROM messages where message_id=?",(row['message_id'],))
                    conn.commit()
                    continue

                # Validation is successful. Save this fact in the database and update the row object
                c = conn.cursor()
                c.execute("UPDATE messages set validated=1 where message_id=?",
                          (row['message_id'],))
                conn.commit()
                row['validated'] = 1

            # If we get here, the row is validated. Add it to the list
            validated_rows.append(row)

        # Now just return the validated rows
        return validated_rows

    app.cli.add_command(create_bucket_and_apply_cors)
