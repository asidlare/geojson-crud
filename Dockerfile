# syntax=docker/dockerfile:1
FROM python:3.12.7-slim-bullseye
ENV PYTHONUNBUFFERED=1
WORKDIR /code

# Install Packages
RUN apt-get -y update && apt-get -y install vim curl

# install requirements
COPY requirements.txt /code/
RUN pip install -r requirements.txt
# COPY . /code/
