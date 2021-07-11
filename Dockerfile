FROM python
COPY ./requirements.txt .
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r requirements.txt
COPY ./autoradarr/autoradarr.py .
ENV AUTORADARR_DB_HOST=$AUTORADARR_DB_HOST
ENV AUTORADARR_DB_USERNAME=$AUTORADARR_DB_USERNAME
ENV AUTORADARR_DB_PASSWORD=$AUTORADARR_DB_PASSWORD
ENV IMDB_APIKEY=$IMDB_APIKEY
ENV RADARR_APIKEY=$RADARR_APIKEY
ENV RADARR_DEFAULT_QUALITY=$RADARR_DEFAULT_QUALITY
ENV RADARR_ROOT_ANIMATIONS=$RADARR_ROOT_ANIMATIONS
ENV RADARR_ROOT_OTHER=$RADARR_ROOT_OTHER
ENV RADARR_URL=$RADARR_URL
ENV TMDB_APIKEY=$TMDB_APIKEY
CMD python /autoradarr.py
