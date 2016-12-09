# proj9-MeetMe, Wyatt Reed for CIS 322, University of Oregon
Select multiple Google calendars and get the complement free times, then send them to a friend to hash out a meeting.


## How to Run the Code
You may start configuring the code by doing the following.

Make sure that you've started your mongodb database and created a admin user using

```
	mongo --port xxxx
	use admin
```
Then adding your user credentials. Afterward you are ready to connect ot the application after creating your admin_credentials file.

```
	bash ./configure
	make test    # All tests should pass
	make service # Then I test from browser on another machine
```
Open up a browser on localhost:5000. Once loaded, the page should allow you to choose a date and time range.

Once submitted, you'll be prompted to login with your google account. The page will then display all calendars for your account which you can choose to display free times you are not busy.

If you have issues with the service you can stop the service by typing the following:
```
	ps -e | grep gunicorn #Find the PID for gunicorn
	kill -9 pid #where pid is the process id returned by the last command
	make service
```

If you are getting issues starting the mongodb server, make sure your current user has access to /data/db/

If you do not, attempt the following as root. 

```
sudo chown -R youruser /data/db/
```
