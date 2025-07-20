#
# Admin Makefile. Used by CSCI E-11 course administrators.
#
# This file is provided for students to see, but not to use.
#

CANONICAL_OWNER_ID=099720109477
SSH_KEY_NAME=seasons
REGION=us-east-2
AMI=ami-05eb56e0befdb025f

test-installer:
	@echo starting instance with key
	aws ec2 run-instances \
	  --instance-type t3a.nano \
	  --image-id $(AMI) \
	  --key-name $(SSH_KEY_NAME) \
	  --region us-east-2 \
	  --tag-specifications  'ResourceType=instance,Tags=[{Key=Name,Value=makefile-launch}]'

list-running-instances:
	aws ec2 describe-instances \
	  --filters "Name=instance-state-name,Values=running" \
	  --region us-east-2 \
	  --query 'Reservations[].Instances[].{ID:InstanceId,Type:InstanceType,PublicIP:PublicIpAddress,LaunchTime:LaunchTime,AZ:Placement.AvailabilityZone}' \
	  --output table

list-security-groups:
	aws ec2 describe-security-groups --region $(REGION) --query 'SecurityGroups[].{Description:Description,GroupId:GroupId,GroupName:GroupName}' --output table

list-lts-images:
	aws ec2 describe-images \                                                                                                                                                                                                                 (main)csci_e-11
	  --region us-east-2 \
	  --owners 099720109477 \
	  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
	            "Name=state,Values=available" \
	  --query 'reverse(sort_by(Images, &CreationDate))[:5].{ID:ImageId, Name:Name, CreationDate:CreationDate, Region:"us-east-2"}' \
	  --output table
