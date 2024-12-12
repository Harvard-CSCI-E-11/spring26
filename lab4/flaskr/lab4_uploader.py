################################################################
##
# Image APIs. All of these need to only be POST to avoid an api_key from being written into the logfile
##

import logging
from flask import request, jsonify, current_app, Response

def register_routes(app):
    @app.route('/new-image', method=POST)
    def new_image():
        """Use the AWS S3 API to get a presigned post that the client can use to upload to S3
        :param api_key: the user's api_key
        :param api_secret_key: the user's api_secret_key
        :return: the post to use for uploading the image. Sends it directly to S3, or to the handler below.
        """

        api_key         = request.values.get('api_key', type=str, default="")
        api_secret_key  = request.values.get('api_secret_key', type=str, default="")
        # Verify api_key and api_secret_key
        if invalid:
            return Response("Invalid api_key", status=403)

        MIME_TYPE = 'image/jpeg'
        s3_client = boto3.session.Session().client( "s3" )

        presigned_post = s3_client.generate_presigned_post(
            Bucket=app.S3_BUCKET,
            Key="images/" + base64.b64encode(os.urandom(16)).decode('utf-8') + ".jpeg"
            Conditions=[
                {"Content-Type": 'image/jpeg'}, # Explicitly allow Content-Type header
                ["content-length-range", 1, current_app.config['MAX_IMAGE_SIZE']]
                 ],
            Fields= { 'Content-Type': 'image/jpeg' },
            ExpiresIn=120)      # in seconds

        return jsonify(presigned_post)


    @app.route('/get-signed-url', methods=['POST','GET'])
    def get_signed_url():
        api_key         = request.values.get('api_key', type=str, default="")
        api_secret_key  = request.values.get('api_secret_key', type=str, default="")
        image_id = request.values.get('image_id', type=int, default=0)

        # Verify api_key and api_secret_key
        if invalid:
            return Response("Invalid api_key", status=403)

        s3_client = boto3.session.Session().client( "s3" )

        presigned_url = s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': current_app.config['S3_BUCKET'],
                    'Key': o.path[1:]},
            ExpiresIn=3600)     # give an hour

        # Now redirect to it.
        # Code 302 is a temporary redirect, so the next time it will need to get a new presigned URL
        return redirect(presigned_url, code=302)
