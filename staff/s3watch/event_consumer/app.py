"""
watch the S3 bucket and process uploaded records in the form:

account_id, my_ip, email, name
"""


import os
import json
import logging
import re
import boto3

# Initialize AWS clients
s3_client = boto3.client('s3')
route53_client = boto3.client('route53')
ses_client = boto3.client('ses',region_name='us-east-1') # SES is only in region us-east-1
logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'DEBUG').upper())
logger = logging.getLogger(__name__)
logger.info('message')


# Constants
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"        # from route53
DOMAIN = "csci-e-11.org"                        # Domain managed in Route53
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"      # Verified SES email address
DOMAIN_SUFFIXES = ['', '-lab1', '-lab2', '-lab3', '-lab4', '-lab5', '-lab6', '-lab7']

# Function to extract data from S3 object
def extract(content):
    """Given the content that the student uploaded to S3, extract the hostname, IP, and email"""
    (account_id, my_ip, email, name) = content.split(",")
    logging.info("account_id=%s my_ip=%s email=%s name=%s",account_id, my_ip, email, name)
    account_id = account_id.strip()
    my_ip = my_ip.strip()
    email   = re.sub(r'[^-a-zA-Z0-9_@.+]', '', email)
    hostname = "".join(email.replace("@",".").split(".")[0:2])
    hostname = re.sub(r'[^a-zA-Z0-9]', '', hostname)
    return hostname, my_ip, email, name

# Lambda handler
# pylint: disable=unused-argument
# pylint: disable=too-many-locals
def lambda_handler(event, context):
    """Process the lambda event"""
    logger.debug("Event received: %s",event)

    bucket_name = event['detail']['requestParameters']['bucketName']
    object_key = event['detail']['requestParameters']['key']

    # Get the content of the uploaded S3 object
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    content = response['Body'].read().decode('utf-8')

    logger.error("s3 object content=%s",content)

    # Extract data using the extract function
    hostname, ip_address, email, name = extract(content)

    # Create DNS records in Route53
    changes = []
    hostnames = [f"{hostname}{suffix}.{DOMAIN}" for suffix in DOMAIN_SUFFIXES]
    changes   = [{ "Action": "UPSERT",
                         "ResourceRecordSet": {
                             "Name": hostname,
                             "Type": "A",
                             "TTL": 300,
                             "ResourceRecords": [{"Value": ip_address}]
                             }}
                 for hostname in hostnames]

    route53_response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
            "Changes": changes
        }
    )
    logger.info("Route53 response: %s",route53_response)

    # Send email notification using SES
    email_subject = f"New DNS Record Created: {hostnames[0]}"
    email_body = f"""
    The following DNS record has been created:

    Hostname: {hostnames[0]}
    IP Address: {ip_address}

    Best regards,
    CSCIE-11 Team
    """
    ses_response = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={'ToAddresses': [email]},
        Message={
            'Subject': {'Data': email_subject},
            'Body': {'Text': {'Data': email_body}}
        }
    )
    logger.info("SES response: %s",ses_response)

    return {
        "statusCode": 200,
        "body": json.dumps("DNS record created and email sent successfully.")
    }
