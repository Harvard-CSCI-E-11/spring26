"""
image_validate: Validate the image in S3

STUDENTS - You need to make minor changes to this file to complete labs 5 and 6
For lab 5 - you will add validation of the image uploading and downloading
For lab 6 - you will add the AI routines

"""

import io
import socket
import json

import boto3
from botocore.exceptions import BotoCoreError
from PIL import Image,UnidentifiedImageError

from . import db

S3_BUCKET_PREFIX = socket.gethostname().replace(".", "-")
S3_BUCKET_SUFFIX = "-images-bucket"
S3_BUCKET = S3_BUCKET_PREFIX + db.get_lab_name() + S3_BUCKET_SUFFIX
MAX_IMAGE_SIZE_BYTES = 4 * 1024 * 1024
JPEG_MIME_TYPE = "image/jpeg"

s3_client   = boto3.client("s3")
rekognition_client = boto3.client("rekognition", region_name=s3_client.meta.region_name)

def safe_get_object(bucket, s3key):
    """Get an object's bytes for S3 or return None"""
    try:
        r = s3_client.get_object(Bucket=bucket, Key=s3key)
    except s3_client.exceptions.NoSuchKey:
        return None
    return r['Body'].read()

def is_valid_jpeg(buf: bytes) -> bool:
    """Simple program to use Pillow to validate a JPEG image"""
    try:
        img = Image.open(io.BytesIO(buf))
        return img.format == "JPEG"
    except (IOError,UnidentifiedImageError):
        return False

def delete_row(app, conn, row):
    """If the image does not validate, you can use this to delete it in the database"""
    app.logger.info("Deleting image: %s",row)

    # If the s3key exists, delete it
    if row['s3key']:
        s3_client.delete_object(Bucket=S3_BUCKET,  Key=row['s3key'])
    c = conn.cursor()
    c.execute("DELETE FROM images where image_id=?",(row['image_id'],))
    c.execute("DELETE FROM messages where message_id=?",(row['message_id'],))
    conn.commit()

def validate_image_data_length(app, image_data_length):
    """Return True if the image_data_length is acceptable"""

    # STUDENTS --- fix this:
    app.logger.info("validate_image_data_length(%s)",image_data_length)
    return image_data_length <= MAX_IMAGE_SIZE_BYTES

def validate_image_table_row(app, conn, row):
    """Given a row of images from the database query above,
    delete rows that do not have valid images."""
    if row['validated']:
        return row

    # Image is not validated. Get information that may be useful
    message_id = row['message_id']
    image_id = row['image_id']
    s3key = row['s3key']
    image = safe_get_object(S3_BUCKET, s3key)
    if image is None:
        app.logger.info("validate_images: message_id=%s image_id=%s "
                        "has no corresponding s3 object at s3key=%s",
                        message_id, image_id, s3key)
        delete_row(app, conn, row)
        return None

    app.logger.info("validate message_id=%s image_id=%s s3key=%s len(image)=%s",
                    message_id, image_id, s3key, len(image))

    #
    # Right now this just validates everything that is in S3.
    # Change this so that the JPEGs are on validated if they are valid JPEGs.
    #
    # You can check to see if it is valid with is_valid_jpeg():
    # validated = is_valid_jpeg(data)
    #
    # For now, we will assume everything is validated

    #
    # == STUDENTS - START LAB5 MODIFICATIONS ==
    #

    validated = is_valid_jpeg(image)

    #
    # == STUDENTS - END LAB5 MODIFICATIONS ==
    #

    # For Lab6, Do the AI on the image after it is validated.
    # Store the results in 'notes'
    # == STUDENTS - START LAB6 MODIFICATIONS ==

    if validated:
        try:
            response = rekognition_client.recognize_celebrities( Image={"Bytes": image} )
            celeb = response.get("CelebrityFaces", [])
            app.logger.info("celeb=%s",celeb)
        except BotoCoreError as e:
            celeb = []
            app.logger.error("rekognition error: %s",e)

        # Update the database and the row
        celeb_json = json.dumps(celeb,default=str)
        c = conn.cursor()
        c.execute("UPDATE images set celeb_json=? where image_id=?",
                  (celeb_json,image_id))
        conn.commit()
        row['celeb_json'] = celeb

    # == STUDENTS - END LAB6 MODIFICATIONS ==

    #
    # If the row did not validate, delete it in the database
    if not validated:
        delete_row(app, conn, row)
        return None

    # Validation is successful. Save this fact in the database and update the row object
    app.logger.info("message_id=%s image_id=%s validated",row['message_id'],row['image_id'])
    row['validated'] = 1
    c = conn.cursor()
    c.execute("UPDATE images set validated=1 where image_id=?",(row['image_id'],))
    conn.commit()
    return row

def make_presigned_post(s3_bucket,s3key):
    """Return the S3 presigned_post fields"""
    return s3_client.generate_presigned_post(
        Bucket = s3_bucket,
        Key = s3key,
        Conditions = [
            # Only enforce the Content-Type restriction...
            { "Content-Type": JPEG_MIME_TYPE },
            # STUDENTS --- impose the MAX_IMAGE_SIZE_BYTES
            # restriction by uncommenting the next line:
            [ "content-length-range", 1, MAX_IMAGE_SIZE_BYTES],
        ],
        Fields = { "Content-Type": JPEG_MIME_TYPE},
        ExpiresIn = 120, # in seconds
    )
