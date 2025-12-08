## Web application for Lab6 Adding AWS Rekognition

To run this lab, log into your EC2 instance and cd to the lab directory:

```
cd /home/ec2-user/spring26/lab6
```

Then do these steps:

1. Tell the Let's Encrypt certbot to add a TLS certificate for the new virtual host.

2. Add the -lab6 virtual host to your httpd configuration file (see the lab).
   Be sure to specify port 8006 for the proxy!

3. Install and start up the lab4 service.
   (Note that we now run gunicorn on port 8006 to avoid conflicting with the gunicorn set up for the other labs)

   command to type:
   ```
   sudo cp lab6.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl start lab6.service
   ```

4. Modify image_controller.py so that 
