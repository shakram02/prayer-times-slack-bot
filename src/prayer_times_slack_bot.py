#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020 shakram02
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import requests
import sched
import sys
import pytz
import time
import random
# Used for translating times across timezones.
from pytz import timezone
from iso3166 import countries
from datetime import datetime, timedelta

# https://aladhan.com/prayer-times-api
API_URL = "https://api.aladhan.com/v1/timingsByCity"

SLACK_BOT_EMOJI = ":mosque:"  # Emoji of the bot (replaces the user icon)
SLACK_BOT_USER_NAME = "Prayer Times"  # Display name of the bot.
scheduler = sched.scheduler()


def to_target_timezone(time_object: datetime):
    """
    Localizes a time object to the target timezone. 
    Handles both naive and localized datetime objects.
    """
    if not time_object.tzinfo:
        time_object = pytz.utc.localize(time_object)

    return time_object.astimezone(country_locale)


def target_timezone_now():
    return to_target_timezone(datetime.now())


def to_formatted_date_str(datetime_object: datetime):
    return datetime_object.strftime("%d-%m-%Y")


def to_formatted_time_str(datetime_object: datetime):
    return datetime_object.strftime("%I:%M %p")


def en_to_ar_num(number_string: str):
    """Translates an English language number to an Arabic language number."""
    dic = {
        '0': '۰',
        '1': '١',
        '2': '٢',
        '3': '۳',
        '4': '٤',
        '5': '۵',
        '6': '٦',
        '7': '۷',
        '8': '۸',
        '9': '۹',
    }

    return "".join([dic[char] for char in number_string])


def seconds_to_hours_minutes(seconds: int):
    return time.strftime("%H:%M", time.gmtime(seconds))


class PrayerInfo:
    def __init__(self, ar_name: str, en_name: str, target_datetime: datetime):
        self._en_name = en_name
        self._ar_name = ar_name
        self.target_datetime: datetime = target_datetime

    def en_time(self):
        return to_formatted_time_str(self._prayer_time_in_local_timezone().time())

    def en_date(self):
        return to_formatted_date_str(self._prayer_time_in_local_timezone().date())

    def ar_name(self):
        return self._ar_name

    def en_name(self):
        return self._en_name

    def ar_time(self):
        """
        Converts an AM/PM time in English to its
        Arabic equivalent.
        e.g. 01:23 PM -> ٠١:٢٣ م
        """
        time, time_of_day = self.en_time().split(" ")
        h, m = time.split(":")
        h, m = en_to_ar_num(h), en_to_ar_num(m)
        tod_dict = {
            "AM": "ص",
            "PM": "م"
        }
        return f"{h}:{m} {tod_dict[time_of_day]}"

    def _prayer_time_in_local_timezone(self):
        return self.target_datetime.astimezone(country_locale)

    def __repr__(self):
        return self._en_name

    def __str__(self):
        return self.__repr__()


def seconds_until_midnight(minute_offset):
    """
    Get the number of seconds until midnight.
    The API is called each midnight to get next
    day's prayer times.
    """
    # source: http://jacobbridges.github.io/post/how-many-seconds-until-midnight/
    tomorrow = target_timezone_now() + timedelta(days=1)
    midnight = datetime(year=tomorrow.year, month=tomorrow.month,
                        day=tomorrow.day, hour=0, minute=minute_offset, second=0)
    midnight = to_target_timezone(midnight)
    return (midnight - target_timezone_now()).total_seconds()


def next_prayer_offset(next_paryer_time: datetime):
    """Computes the time to the next prayer in seconds."""
    today = target_timezone_now()
    return (next_paryer_time - today).total_seconds()


def parse_date(api_response):
    """Extracts Hijri date from API response in Arabic."""
    hijri = api_response["date"]["hijri"]
    month = hijri["month"]["ar"]
    day = hijri["day"]
    year = hijri["year"]

    return f"{en_to_ar_num(day)} من {month} {en_to_ar_num(year)}"


def pretty_now():
    """Return the date now in a pretty format for logging."""
    # Converts the date to a string because this function
    # is always used in call site.
    target_now = target_timezone_now().replace(microsecond=0)
    return target_now.strftime("%d-%m-%Y %I:%M %p")


def compose_prayer_time_notification_message(date, prayer_info: PrayerInfo):
    """Format the prayer time notification message to be posted to slack."""
    s = "اللهم صلي و سلم على نبينا محمد"
    tag_for_ppl_online = "<!here>"
    p = f"صلاة {prayer_info.ar_name()} ({prayer_info.ar_time()})"
    return f"{p} {s}\n\n{date}\n{tag_for_ppl_online}"


def compose_prayer_time_out_message():
    """Format the prayer time warning message to be posted to slack."""
    s = "اللهم صلي و سلم على نبينا محمد"
    tag_for_ppl_online = "<!here>"
    p = "وقت هذه الصلاة قارب على الانتهاء"
    return f":warning: {p} {s}\n\n{tag_for_ppl_online}"


def move_to_next_prayer(day_prayers):
    """
    Removes the next prayer from the list
    and returns its information and
    seconds remaining till its time.
    """

    next_prayer_info = day_prayers.pop(0)
    next_offset = next_prayer_offset(next_prayer_info.target_datetime)
    return next_prayer_info, next_offset


def parse_prayer_times(api_response):
    """
    Extracts prayer times from raw API response
    as a list of tuples (<prayer_name_en>,<time_en>),

    returns PrayerInfo objects.
    """
    def get_naive_datetime_for_time(time: datetime):
        return target_timezone_now().replace(
            hour=time.hour, minute=time.minute)

    def to_target_timezone_datetime(api_time_string):
        naive_time = datetime.strptime(api_time_string, "%H:%M")
        naive_datetime = get_naive_datetime_for_time(naive_time)
        return to_target_timezone(naive_datetime)

    timings = api_response["timings"]
    prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]  # Sorted prayers
    # Transalate prayer names to Arabic.
    arabic_prayer_names = {"Fajr": "الفجر", "Dhuhr": "الظهر",
                           "Asr": "العصر", "Maghrib": "المغرب", "Isha": "العشاء"}

    prayer_times = []
    for prayer_name in prayers:
        prayer_time_target = to_target_timezone_datetime(timings[prayer_name])
        arabic_name = arabic_prayer_names[prayer_name]
        info = PrayerInfo(arabic_name, prayer_name, prayer_time_target)
        prayer_times.append(info)

    return prayer_times


def call_prayer_api(method=5):
    """Retrieves prayer time information from the API using the given method."""
    # 3 - Muslim World League
    # 4 - Umm Al-Qura University, Makkah
    # 5 - Egyptian General Authority of Survey
    # 9 - Kuwait
    # 10 - Qatar
    # 11 - Majlis Ugama Islam Singapura, Singapore
    # 12 - Union Organization islamic de France
    # 13 - Diyanet İşleri Başkanlığı, Turkey
    # 14 - Spiritual Administration of Muslims of Russia

    # Example request (the space will be encoded by Python)
    # http://api.aladhan.com/v1/timingsByCity?city=mecca&country=Saudi Arabia&method=5
    params = {"city": CITY, "country": COUNTRY, "method": method}
    r = requests.get(url=API_URL, params=params)
    assert r.status_code == 200, f"Request failed, got:\n\n{r.text}"

    data = r.json()
    return data["data"]


def post_to_slack(message=None):
    """Posts a given message to slack, if the message is empty a "test" message is posted."""
    print(f"[post_to_slack] ({pretty_now()})")

    if not message:
        message = "test"

    payload = {
        # "channel": SLACK_CHANNEL_NAME,
        "username": SLACK_BOT_USER_NAME,
        "text": message,
        "icon_emoji": SLACK_BOT_EMOJI
    }

    payload_json = json.dumps(payload)

    r = requests.post(url=SLACK_WEBHOOK_URL, data=payload_json)
    if r.status_code != 200:
        print(f"Request failed, got:\n\n{r.text}", file=sys.stderr)


def schedule_next_prayer(next_prayer_info, date, next_offset):
    """Post a message announcing the next prayer's time."""
    print(f"[schedule_next_prayer] ({pretty_now()})")

    print(
        f"Next prayer: {next_prayer_info}" +
        f" {next_prayer_info.en_time()} " +
        f" in [{seconds_to_hours_minutes(next_offset)} hours]")

    message = compose_prayer_time_notification_message(date, next_prayer_info)

    # Notify at the next prayer's time.
    scheduler.enter(next_offset, 1, post_to_slack, argument=(message,))


def schedule_prayer_time_out_warning(next_offset):
    """Post a message before the next prayer's time."""
    message = compose_prayer_time_out_message()

    seconds_before_timeout = random.randint(18, 29) * 60
    alert_after = next_offset - seconds_before_timeout
    print(f"[schedule_prayer_time_out_warning] ({pretty_now()})" +
          f" in [{seconds_to_hours_minutes(alert_after)} hours]")

    scheduler.enter(alert_after,
                    1, post_to_slack, argument=(message,))


def schedule_next_update(next_offset, date, day_prayers):
    """Schedule the next update task."""
    print(f"[schedule_next_update] ({pretty_now()})")

    thresh = 60  # 60 Seconds.
    scheduler.enter(next_offset + thresh, 1, run_scheduler,
                    argument=(date, day_prayers,))


def run_scheduler(date, day_prayers):
    """
    Handles prayer notification scheduling by checking the next prayer and
    scheduling a function to run at that time.

    If no prayers are remaining in this day, a call to the API is sechdueled
    to retrieve prayer information for the next day.
    """
    print(f"[run_scheduler] ({pretty_now()})")

    if not day_prayers:
        # Compute the time till midnight + 1 minute.
        seconds_to_tomorrow = seconds_until_midnight(minute_offset=1)
        print("[run_scheduler] done for today, scheduling next day in",
              seconds_to_hours_minutes(seconds_to_tomorrow), "hours...")
        scheduler.enter(seconds_to_tomorrow, 1, schedule_daily_task)
        return

    next_prayer_info, next_offset = move_to_next_prayer(day_prayers)

    # Skip to next prayer if we passed it already.
    if next_offset < 0:
        print("[run_scheduler] skipping...",
              next_prayer_info)

        scheduler.enter(0, 1, run_scheduler,
                        argument=(date, day_prayers,))
    else:
        # The next prayer's time hasn't yet come.
        print("[run_scheduler] cont...", day_prayers)
        schedule_next_prayer(next_prayer_info, date, next_offset)
        schedule_prayer_time_out_warning(next_offset)

        # Fetch the prayer after the next prayer time has come.
        schedule_next_update(next_offset, date, day_prayers)


def schedule_daily_task():
    """
    Calls the API to fetch prayer times of this day,
    then starts the prayer notification schedule.
    """

    print("\n\n[schedule_daily_task]",
          f"({pretty_now()}) Loading new day...\n", file=sys.stderr)

    api_response = call_prayer_api()
    prayer_times = parse_prayer_times(api_response)
    date = parse_date(api_response)

    run_scheduler(date, prayer_times)


def main():
    # If you want to send a test message
    # uncomment the following line
    # post_to_slack()

    # Start the scheduler now ⏲
    location = f"[{COUNTRY}].[{CITY}]"
    print(f"RUNNING [{__file__}] for {location}...", file=sys.stderr)
    scheduler.enter(0, 1, schedule_daily_task)
    scheduler.run()
    exit(0)


if __name__ == "__main__":
    if sys.version_info[0] < 3 or sys.version_info[1] < 3:
        print("This script requires at least Python version 3", file=sys.stderr)
        sys.exit(1)

    CONFIG = json.load(
        open(os.path.join(os.path.dirname(__file__), "config.json"))
    )

    CITY = CONFIG["CITY"]
    COUNTRY = CONFIG["COUNTRY"]
    SLACK_WEBHOOK_URL = CONFIG["SLACK_WEBHOOK_URL"]
    assert CITY and COUNTRY and SLACK_WEBHOOK_URL, "A required variable is missing, please fix your .env file"

    # Get the iso3166 country code.
    COUNTRY_CODE = countries.get(COUNTRY).alpha2

    # If this doesn't work for your country (your country has multiple timezones)
    # use countries.get(YOUR_REGION_ISO3166_CODE), be default the code uses the first
    # available timezone name
    COUNTRY_TIMEZONE_NAME = pytz.country_timezones[COUNTRY_CODE][0]
    country_locale = timezone(COUNTRY_TIMEZONE_NAME)

    # Run 🚀
    main()
