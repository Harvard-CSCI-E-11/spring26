## Web application for Amazon rekognition demo.

To run this lab, log into your EC2 instance at Amazon and type:
```
cd /home/ec2-user
git clone https://github.com/Harvard-CSCI-E-11/spring25
```

Then do these steps:

1. Install and start up the lab4 service. (Note that we now run gunicorn on port 5004 to avoid conflicting with the gunicorn set up for lab2)
2. Add the -lab4 virtual host to your httpd configuration file (see the lab). Be sure to specify port 5004 for mod_proxy.
3. Tell the Let's Encrypt certbot to add a TLS certificate for the new virtual host.
