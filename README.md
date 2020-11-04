# Prayer times notifier Slack bot :robot:

This worker fetches prayer times :mosque: from a remote API and posts a message to Slack when it's prayer time and when the prayer time is about to end so you're almost sure in sha Allah that you're not missing any prayers :v:.

You can run this script either locally or using `docker` .

### Setup locally :computer:

* Install `requests` dependency by running `pip install requests pytz iso3166` 
* Setup an Incoming Webhooks in Slack's Integration: [https://my.slack.com/services/new/incoming-webhook](https://my.slack.com/services/new/incoming-webhook).
* Get the Webhook URL e.g.[https://hooks.slack.com/services/some-cryptic-secrets](https://hooks.slack.com/services/some-cryptic-secrets).
* Put the Webhook URL into the `prayer_times_slack_bot.py` .
* Modify the location variables `DEFAULT_CITY` and `DEFAULT_COUNTRY` in the python script to match your city.
* The script will use the location specific API e.g. URL = [http://api.aladhan.com/v1/timingsByCity?city=mecca&country=Saudi Arabia&method=5](http://api.aladhan.com/v1/timingsByCity?city=mecca&country=Saudi%20Arabia&method=5) for Mecca, Saudi Arabia based on the variables you set above.
* OPTIONAL: Modify the Slack username (can be any name, you don't have to create the user beforehand) in `prayer_times_slack_bot.py` .
* OPTIONAL: Modify the Slack channel name `SLACK_CHANNEL_NAME` in `prayer_times_slack_bot.py` to post to a certain channel.
* OPTIONAL: Modify the emoji name to be used as user's icon

Idea and setup steps credits go to [Sholat-Prayer-Times-Slack](https://github.com/ainunnajib/Sholat-Prayer-Times-Slack/)

### Setup using docker :whale:

The extra thing for setup is that you can set the location from the `Dockerfile` instead of changing it from the python code.
Using `PRAYER_TIMES_SLACK_CITY` and `PRAYER_TIMES_SLACK_COUNTRY` environment variables.

To run the container (make sure your user is in the `docker` group)

``` bash
chmod u+x deploy.sh # Make the script runnable
./deploy.sh
```
