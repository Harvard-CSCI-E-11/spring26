Master list of things to do
===========================
- e11admin cli
  - Runs on staff laptop
  - Gives staff commands
  - create a course key for a student and a auto-login URL

- e11admin lab1 - gets list of students & attacks
- e11admin status lab1 - reports how many people have started, completed
- e11admin status reg - reports all registrations
- e11admin download reg - downloads registration
- e11admin download lab1 - downloads grade reports


many labs:
 - check niinx
 - check dns

- labs 5-8:
  - makefile target to set up gunicorn & nginx.
  - e11 command 'e11 hostname lab3' - creates hostname for the lab.
  - use envsubst to do the environment variable substitutions
     `envsubst '$SHASHEDEMAIL $LAB' < config.txt > output2.txt` to limit substitutions
  - have certbot add the TLS certificate
# 1. Set your new hostname variable
export NEW_HOSTNAME="store.example.com"

# 2. Use envsubst to create the new config file
envsubst < /path/to/template.conf > /etc/nginx/sites-available/$NEW_HOSTNAME.conf

# 3. CRITICAL: Enable the new site by creating a symlink
sudo ln -s /etc/nginx/sites-available/$NEW_HOSTNAME.conf /etc/nginx/sites-enabled/

# 1. Test your Nginx configuration for any errors
sudo nginx -t

# 2. If the test is successful, reload Nginx
sudo systemctl reload nginx

# Example: expanding a cert that already has 'example.com' and 'www.example.com'
sudo certbot --nginx --expand -d example.com -d www.example.com -d store.example.com

- lab1
  - answer - the attack we used
  - modify ssh attacker to attack systems that have been registered but do not have a perfect score.


- lab3
  - check access key

- lab4
  - we will set up the gunicorn and nginx

- lab5 tester
  - web app
  - dns
  - api version
  - api key in db
  - api key match
  - upload image works
  - fetch image works

- lab6:
 - analyze image works

- lab7:
 - Something got posted to the dynamodb


- batch grader - do not grade winners
