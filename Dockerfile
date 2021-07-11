FROM python
COPY ./requirements.txt .
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN pip install -r requirements.txt
COPY ./autoradarr/autoradarr.py .
CMD python /autoradarr.py
