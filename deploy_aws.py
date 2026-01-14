#!/usr/bin/env python3
"""
AWS EC2 Deployment Script for OMI-Stitch
Creates security group, key pair, and EC2 instance with Ubuntu
"""

import boto3
import time
import os

# Configuration
REGION = "us-east-1"
INSTANCE_TYPE = "t2.micro"
KEY_NAME = "omi-stitch-key"
SECURITY_GROUP_NAME = "omi-stitch-sg"
INSTANCE_NAME = "omi-stitch-server"

# Ubuntu 22.04 LTS AMI for us-east-1
UBUNTU_AMI = "ami-0c7217cdde317cfec"

# User data script to set up the server
USER_DATA = """#!/bin/bash
set -e

# Update system
apt-get update -y
apt-get upgrade -y

# Install Python, pip, git, nginx
apt-get install -y python3 python3-pip python3-venv git nginx

# Clone the repository
cd /home/ubuntu
git clone https://github.com/vijay-sn15/omi-stitch.git
cd omi-stitch

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service for the application
cat > /etc/systemd/system/omistitch.service << 'EOF'
[Unit]
Description=OMI Stitch FastAPI Application
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/omi-stitch
Environment="PATH=/home/ubuntu/omi-stitch/venv/bin"
ExecStart=/home/ubuntu/omi-stitch/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx as reverse proxy
cat > /etc/nginx/sites-available/omistitch << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/ubuntu/omi-stitch/app/static;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/omistitch /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Set permissions
chown -R ubuntu:ubuntu /home/ubuntu/omi-stitch

# Start services
systemctl daemon-reload
systemctl enable omistitch
systemctl start omistitch
systemctl restart nginx

echo "Deployment complete!" > /home/ubuntu/deployment_status.txt
"""

def main():
    # Create boto3 session with ibexlabs profile
    session = boto3.Session(profile_name='ibexlabs', region_name=REGION)
    ec2 = session.resource('ec2')
    ec2_client = session.client('ec2')
    
    print(f"🔧 Using AWS Region: {REGION}")
    
    # Step 1: Create or get security group
    print("\n📦 Setting up Security Group...")
    try:
        # Check if security group exists
        response = ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [SECURITY_GROUP_NAME]}]
        )
        if response['SecurityGroups']:
            sg_id = response['SecurityGroups'][0]['GroupId']
            print(f"   Using existing security group: {sg_id}")
        else:
            raise Exception("Not found")
    except:
        # Create security group
        vpc_response = ec2_client.describe_vpcs(Filters=[{'Name': 'is-default', 'Values': ['true']}])
        vpc_id = vpc_response['Vpcs'][0]['VpcId']
        
        sg = ec2.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description='Security group for OMI Stitch web application',
            VpcId=vpc_id
        )
        sg_id = sg.id
        
        # Add inbound rules
        sg.authorize_ingress(
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SSH'}]},
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP'}]},
                {'IpProtocol': 'tcp', 'FromPort': 8000, 'ToPort': 8000, 'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'FastAPI'}]},
            ]
        )
        print(f"   Created security group: {sg_id}")
    
    # Step 2: Create or get key pair
    print("\n🔑 Setting up Key Pair...")
    key_path = os.path.expanduser(f"~/.ssh/{KEY_NAME}.pem")
    try:
        ec2_client.describe_key_pairs(KeyNames=[KEY_NAME])
        print(f"   Using existing key pair: {KEY_NAME}")
    except:
        # Create new key pair
        key_pair = ec2_client.create_key_pair(KeyName=KEY_NAME)
        # Save private key
        with open(key_path, 'w') as f:
            f.write(key_pair['KeyMaterial'])
        os.chmod(key_path, 0o400)
        print(f"   Created key pair: {KEY_NAME}")
        print(f"   Private key saved to: {key_path}")
    
    # Step 3: Check for existing instance
    print("\n🖥️  Checking for existing instances...")
    existing = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': [INSTANCE_NAME]},
            {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
        ]
    )
    
    if existing['Reservations']:
        instance_id = existing['Reservations'][0]['Instances'][0]['InstanceId']
        public_ip = existing['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'Pending...')
        print(f"   Found existing instance: {instance_id}")
        print(f"   Public IP: {public_ip}")
    else:
        # Launch new instance
        print("\n🚀 Launching EC2 Instance...")
        instances = ec2.create_instances(
            ImageId=UBUNTU_AMI,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_NAME,
            SecurityGroupIds=[sg_id],
            MinCount=1,
            MaxCount=1,
            UserData=USER_DATA,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': INSTANCE_NAME}]
                }
            ]
        )
        
        instance = instances[0]
        instance_id = instance.id
        print(f"   Instance ID: {instance_id}")
        
        # Wait for instance to be running
        print("   Waiting for instance to start...")
        instance.wait_until_running()
        instance.reload()
        
        public_ip = instance.public_ip_address
        print(f"   ✅ Instance is running!")
        print(f"   Public IP: {public_ip}")
    
    # Print access information
    print("\n" + "="*60)
    print("🎉 DEPLOYMENT INFO")
    print("="*60)
    print(f"\n🌐 Web Application URL: http://{public_ip}")
    print(f"🔧 Direct FastAPI URL:  http://{public_ip}:8000")
    print(f"\n🔐 SSH Access:")
    print(f"   ssh -i {key_path} ubuntu@{public_ip}")
    print(f"\n⏳ Note: The application takes 3-5 minutes to fully deploy.")
    print(f"   You can check deployment status with:")
    print(f"   ssh -i {key_path} ubuntu@{public_ip} 'cat /home/ubuntu/deployment_status.txt'")
    print("="*60)
    
    return public_ip

if __name__ == "__main__":
    main()
