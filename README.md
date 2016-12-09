# proj8-freetimes, Wyatt Reed for CIS 322, University of Oregon
Select multiple Google calendars and get the complement free times.


## How to Run the Code
You may start configuring the code by doing the following.

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
