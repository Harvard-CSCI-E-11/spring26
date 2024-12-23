import boto3
import json

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
    except Exception as e:
        print(f"Error: {e}")
        return None

def celebrities_to_html(celebs):
    html = ''
    for celeb in celebs:
        html += f"Name: {celeb.get('Name')} Confidence: {celeb.get('MatchConfidence'):2.4}% "
        for url in celeb.get('Urls', []):
            html += f"<a target='_' href='https://{url}'>[link]</a>"
        html += "<br/>\n"
    return html
