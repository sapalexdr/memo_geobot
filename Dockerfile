FROM python:3.9-alpine

# Metadata
LABEL MAINTAINERS="@sapalexdr (https://t.me/sapalexdr)"

# Installing apps
RUN apk add build-base libffi-dev

# Creating virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
# Some magic: next line also activates venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY geobot/utils/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip -r /tmp/requirements.txt

# Switching to an unprivileged user
RUN adduser --gecos memo_geobot --home /home/memo_geobot/ --disabled-password memo_geobot
COPY ./geobot /home/memo_geobot/geobot
RUN chown -R root.memo_geobot /home/memo_geobot
# RUN chmod g+w /home/memo_geobot/geobot/bot.log
USER memo_geobot
WORKDIR /home/memo_geobot/geobot

# Running a bot
CMD python -u app.py
