#!/usr/bin/bash
sudo yum install cronie -y
sudo systemctl enable crond.service
sudo systemctl start crond.service
sudo systemctl status crond | grep Active
sudo systemctl status crond.service
echo "0 0,12 * * * root /opt/certbot/bin/python -c 'import random; import time; time.sleep(random.random() * 3600)' && sudo certbot renew -q" | sudo tee -a /etc/crontab  > /dev/null
