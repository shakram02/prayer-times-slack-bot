FROM python:3.7.5-alpine
RUN python -m pip install -r requirements.txt
ENV PRAYER_TIMES_SLACK_CITY=Alexandria
ENV PRAYER_TIMES_SLACK_COUNTRY=Egypt
COPY prayer_times_slack_bot.py .
CMD ["python","-u", "prayer_times_slack_bot.py"]