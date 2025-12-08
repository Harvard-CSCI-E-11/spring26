## Web application for Lab5: Image Board

To run this lab, log into your EC2 instance at Amazon and type:
```
cd /home/ec2-user/spring26/lab5
```

Then do these steps:

1. Tell the Let's Encrypt certbot to add a TLS certificate for the new virtual host.

2. Add the -lab5 virtual host to your nginx configuration file (see the lab instructions).
   Be sure to specify port 8005 for the proxy!

3. Install and start up the lab5 service.
   (Note that we now run gunicorn on port 8005 to avoid conflicting with the gunicorn set up for the other labs)

   command to type:
   ```
   sudo cp lab5.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl start lab5.service
   ```

