Import a key paid:
```
KEYFILE=$HOME/.ssh/id_ed25519.pub
aws ec2 import-key-pair \
  --key-name mykey \
  --public-key-material fileb://$KEYFILE \
  --region us-east-2
```

List key pairs:
```
aws ec2 describe-key-pairs --region us-east-2 --output table
```

Describe LTS images:
```
aws ec2 describe-images \                                                                                                                                                                                          --region us-east-2 \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'reverse(sort_by(Images, &CreationDate))[:5].{ID:ImageId, Name:Name, CreationDate:CreationDate, Region:`us-east-2`}' \
  --output table
```


Launch an instance:
```
aws ec2 run-instances \
	  --instance-type t3a.nano \
	  --image-id $AMI \
	  --key-name $SSH_KEY_NAME \
	  --region us-east-2 \
	  --tag-specifications  'ResourceType=instance,Tags=[{Key=Name,Value=makefile-launch}]'
 ```


Delete unused security groups:
```
for sg in $(aws ec2 describe-security-groups --region us-east-2 --query 'SecurityGroups[].{GroupId:GroupId}' --output text)
  do
	echo $sg
    aws ec2 delete-security-group --region us-east-2 --group-id $sg
  done
```
