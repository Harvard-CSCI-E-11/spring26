"""
upload and download to s3.
"""

################################################################
##
# Image APIs. All of these need to only be POST to avoid an api_key
# from being written into the logfile
##

import base64
import os
import boto3
from flask import request, jsonify, current_app, abort, redirect
from . import lab4_apikey
from . import db

JPEG_MIME_TYPE = 'image/jpeg'

def init_app(app):
    """Initialize the app and register the paths."""
    def validate_api_key_request():
        """Validate the API key for the current request and throw an exception if invalid"""
        api_key         = request.values.get('api_key', type=str, default="")
        api_secret_key  = request.values.get('api_secret_key', type=str, default="")
        # Verify api_key and api_secret_key
        if not lab4_apikey.validate_api_key(api_key, api_secret_key):
            app.logger.info("api_key %s does not validate",api_key)
            abort(403)

    @app.route('/new-image', methods=['POST'])
    def new_image():
        """Use the AWS S3 API to get a presigned post that the client can use to upload to S3
        :param api_key: the user's api_key
        :param api_secret_key: the user's api_secret_key
        :return: the post to use for uploading the image.
                 Sends it directly to S3, or to the handler below.
        """

        validate_api_key_request()

        s3_client = boto3.session.Session().client( "s3" )

        presigned_post = s3_client.generate_presigned_post(
            Bucket=app.S3_BUCKET,
            Key="images/" + base64.b64encode(os.urandom(16)).decode('utf-8') + ".jpeg",
            Conditions=[
                {"Content-Type": JPEG_MIME_TYPE}, # Explicitly allow Content-Type header
                ["content-length-range", 1, current_app.config['MAX_IMAGE_SIZE']]
                 ],
            Fields= { 'Content-Type': JPEG_MIME_TYPE },
            ExpiresIn=120)      # in seconds

        return jsonify(presigned_post)


    @app.route('/get-image', methods=['POST','GET'])
    def get_image():
        validate_api_key_request()

        # Get the URN for the image_id
        image_id = request.values.get('image_id', type=int, default=0)
        s3key    = db.get_image_info(image_id)['s3key']

        s3_client = boto3.session.Session().client( "s3" )
        presigned_url = s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': current_app.config['S3_BUCKET'],
                    'Key': s3key},
            ExpiresIn=3600)     # give an hour

        # Now redirect to it.
        # Code 302 is a temporary redirect, so the next time it will need to get a new presigned URL
        return redirect(presigned_url, code=302)

    @app.route('/list-images', methods=['GET'])
    def list_images():
        # Does not verify api_key
        return db.list_images()
