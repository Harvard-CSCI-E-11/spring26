#!/bin/bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo $AWS_ACCOUNT_ID, $MY_IP | aws s3 cp - s3://cscie-11/students/$AWS_ACCOUNT_ID  --acl bucket-owner-full-control
