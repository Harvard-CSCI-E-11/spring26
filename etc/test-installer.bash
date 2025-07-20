#!/bin/bash

set -euo pipefail

CANONICAL_OWNER_ID=099720109477
SSH_KEY_NAME=Seasons
AMI=ami-05eb56e0befdb025f
REGION=us-east-2
INSTANCE_TYPE=t3a.nano
TAG_NAME="makefile-launch"

# Step 1: Get first available subnet in a VPC with IPv6 support
read -r SUBNET_ID VPC_ID AZ <<< $(aws ec2 describe-subnets \
  --region "$REGION" \
  --filters "Name=default-for-az,Values=true" \
  --query "Subnets[0].[SubnetId,VpcId,AvailabilityZone]" \
  --output text)

echo "Using Subnet: $SUBNET_ID in AZ: $AZ"

# Step 2: Create Security Group (or find existing one)
SEC_GROUP_NAME="allow-ssh-http-https"
SEC_GROUP_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters Name=group-name,Values="$SEC_GROUP_NAME" Name=vpc-id,Values="$VPC_ID" \
  --query "SecurityGroups[0].GroupId" \
  --output text  || true)

if [[ "$SEC_GROUP_ID" == "None" || -z "$SEC_GROUP_ID" ]]; then
  echo "Creating security group..."
  SEC_GROUP_ID=$(aws ec2 create-security-group \
    --group-name "$SEC_GROUP_NAME" \
    --description "Allow SSH, HTTP, HTTPS" \
    --vpc-id "$VPC_ID" \
    --region "$REGION" \
    --query 'GroupId' \
    --output text)

  for PORT in 22 80 443; do
    echo adding ingress on port $PORT
    aws ec2 authorize-security-group-ingress \
      --group-id "$SEC_GROUP_ID" \
      --region "$REGION" \
      --protocol tcp --port "$PORT" --cidr 0.0.0.0/0
  done
fi

# Step 3: Launch EC2 Instance
echo "Launching instance..."
InstanceId=$(aws ec2 run-instances \
  --image-id "$AMI" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$SSH_KEY_NAME" \
  --region "$REGION" \
  --subnet-id "$SUBNET_ID" \
  --associate-public-ip-address \
  --security-group-ids "$SEC_GROUP_ID" \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME}]" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance ID: $InstanceId"

# Step 4: Wait for instance and fetch IPs
aws ec2 wait instance-running --instance-ids "$InstanceId" --region "$REGION"

aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$InstanceId" \
  --query 'Reservations[].Instances[].{ID:InstanceId, AZ:Placement.AvailabilityZone, IPv4:PublicIpAddress, IPv6:NetworkInterfaces[0].Ipv6Addresses[0].Ipv6Address}' \
  --output table

# Get the IP address
IPADDR=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$InstanceId" \
	     --query 'Reservations[].Instances[].{IPv4:PublicIpAddress}' --output text)


MAX_RETRIES=50
DELAY=0.2
for ((i=1; i<=MAX_RETRIES; i++)); do
    if ssh -o ConnectTimeout=1 -o StrictHostKeyChecking=no -o LogLevel=ERROR "ubuntu@$IPADDR" 'hostname && uptime'  2>/dev/null; then
        echo "Successfully logged in to $IPADDR"
        SUCCESS=1
        break
    fi
    sleep "$DELAY"
done

if [ "$SUCCESS" -eq 0 ]; then
    echo "❌ SSH failed after $((MAX_RETRIES * DELAY)) seconds" >&2
    exit 1
fi

echo Installing...
ssh ubuntu@$IPADDR 'sudo apt install git && git clone https://github.com/Harvard-CSCI-E-11/spring26.git && spring26/etc/install-e11'

echo Testing...
ssh ubuntu@IPADDR poetry about

echo Terminating instance $InstanceId
aws ec2 terminate-instances --instance-ids $InstanceId --region $REGION
