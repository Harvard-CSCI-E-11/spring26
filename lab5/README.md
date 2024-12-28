## Web application for Lab5: Adding AWS Rekognition

To run this lab, log into your EC2 instance at Amazon and type:
```
cd /home/ec2-user
git clone https://github.com/Harvard-CSCI-E-11/spring25
```

Then do these steps:

1. Install and start up the lab4 service.
   (Note that we now run gunicorn on port 8005 to avoid conflicting with the gunicorn set up for lab2)

   command to type:
   ```
   cp lab4/lab4.service /etc/systemd/system/
   ```

2. Add the -lab4 virtual host to your httpd configuration file (see the lab).
   Be sure to specify port 8005 for `mod_proxy`!

3. Tell the Let's Encrypt certbot to add a TLS certificate for the new virtual host.
