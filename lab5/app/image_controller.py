"""
image_controller: Controlls all aspects of uploading, downloading, listing, and processing JPEG images.
"""

################################################################
##
# Image APIs. All of these need to only be POST to avoid an api_key
# from being written into the logfile
##

import os
import json
import socket

import boto3
from flask import request, jsonify, current_app, abort, redirect
from . import apikey
from .db import get_db
from . import rekognizer


S3_BUCKET = socket.gethostname().replace('.','-') + '-cscie-11-s3-bucket'
MAX_IMAGE_SIZE=10_000_000,
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

def list_images():
    """Return an array of dicts for all the images"""
    db = get_db()
    rows = db.execute('SELECT * FROM images').fetchall()

def get_image_info(image_id):
    """Return a dict for a specific image"""
    db = get_db()
    return db.execute('SELECT * FROM images WHERE image_id=?',(image_id,)).fetchone()

def new_image(api_key_id,s3key):
    """Create a new image in the database"""
    db = get_db()
    cur  = db.cursor()
    cur.execute("""
        INSERT into images (s3key,created_by)
        VALUES (?, ?)
        """,(s3key,api_key_id))
    db.commit()
    return cur.lastrowid        # return the row inserted into images

def init_app(app):
    """Initialize the app and register the paths."""
    def presigned_url_for_s3key(s3key):
        s3_client = boto3.session.Session().client( "s3" )
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': current_app.config['S3_BUCKET'],
                    'Key': s3key},
            ExpiresIn=3600)     # give an hour
        return presigned_url

    @app.route('/api/new-image', methods=['POST'])
    def api_new_image():
        """Use the AWS S3 API to get a presigned post that the client can use to upload to S3
        :param api_key: the user's api_key
        :param api_secret_key: the user's api_secret_key
        :return: the post to use for uploading the image.
                 Sends it directly to S3, or to the handler below.
        """

        api_key_id = apikey.validate_api_key_request()
        s3_client = boto3.session.Session().client( "s3" )
        s3key = "images/" + os.urandom(8).hex() + ".jpeg"
        presigned_post = s3_client.generate_presigned_post(
            Bucket=app.config['S3_BUCKET'],
            Key=s3key,
            Conditions=[
                {"Content-Type": JPEG_MIME_TYPE}, # Explicitly allow Content-Type header
                ["content-length-range", 1, current_app.config['MAX_IMAGE_SIZE']]
            ],
            Fields= { 'Content-Type': JPEG_MIME_TYPE },
            ExpiresIn=120)      # in seconds

        # Finally, record the image in the database
        image_id = new_image(api_key_id, s3key)

        app.logger.info("delivered presigned api_key_id=%s s3_key=%s image_id=%s",
                        api_key_id,presigned_post,image_id)
        return jsonify({'presigned_post':presigned_post,'image_id':image_id})


    @app.route('/api/get-image', methods=['POST','GET'])
    def api_get_image():
        """No authenticaiton"""
        # Get the URN for the image_id
        image_id = request.values.get('image_id', type=int, default=0)
        s3key    = get_image_info(image_id)['s3key']
        presigned_url = presigned_url_for_s3key(s3key)
        app.logger.info("image_id=%d s3key=%s presigned_url=%s",image_id,s3key,presigned_url)

        # Now redirect to it.
        # Code 302 is a temporary redirect, so the next time it will need to get a new presigned URL
        return redirect(presigned_url, code=302)

    @app.route('/api/list-images', methods=['GET'])
    def api_list_images():
        """List the imsages. Note that the function list_images() returns a list of SQLIte3 Row
        objects. They need to be turned into an array of dict() objects, and each s3key needs to be turned into a url.
        """
        # Get all of the images and convert each SQLite3 Row object to a dictionary (so we can modify it)
        rows = [dict(row) for row in list_images()]

        # Now, for each row, add a url for the s3key
        # If we don't celeb info for it, generate the JSON and HTML
        # (note: it would probably be better to generate the HTML on the client from the JSON)
        db = get_db()
        for row in rows:
            s3key = row['s3key']
            row['url'] = presigned_url_for_s3key(s3key)
            if row['celeb']:
                celeb = json.loads(row['celeb'])
            else:
                celeb = rekognizer.recognize_celebrities(app.config['S3_BUCKET'], s3key)
                row['celeb'] = json.dumps(celeb,default=str)
                db.execute("UPDATE images set celeb=? where s3key=?",(celeb_json,s3key))
                db.commit()
            row['celeb_html'] = rekognizer.celebrities_to_html(celeb)
            print(row['celeb_html'])
        return rows

    # Add new variable to the configuration
    app.config['S3_BUCKET'] = S3_BUCKET
    app.config['MAX_IMAGE_SIZE'] = MAX_IMAGE_SIZE

    # Register CLI command
    @click.command('apply-cors')
    def apply_cors():
        # Check to see if the bucket exists and creat it if it does not
        s3 = boto3.client('s3')

        try:
            s3.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # Bucket does not exist; create it
                s3.create_bucket(Bucket=bucket_name)
                click.echo(f'Created bucket {app.config["S3_BUCKET"]}')
        else:
            print(f"Error checking bucket: {e}")
            raise


        # Apply the CORS policy to the S3 bucket
        s3.put_bucket_cors(
            Bucket=app.config['S3_BUCKET'],
            CORSConfiguration=CORS_CONFIGURATION
        )
        click.echo(f'Applied CORS policy to bucket {app.config["S3_BUCKET"]}')

    app.cli.add_command(apply_cors)
