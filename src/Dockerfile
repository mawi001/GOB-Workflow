FROM amsterdam/docker_python:latest
MAINTAINER datapunt@amsterdam.nl

# Copy .jenkins scripts to where jenkins / ansible expect them
COPY .jenkins /.jenkins

# Install gobworkflow in /app folder
WORKDIR /app

# Install required Python packages
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt
RUN rm requirements.txt

# Copy gobworkflow module
COPY gobworkflow gobworkflow

# Copy alembic config
COPY alembic alembic
COPY alembic.ini alembic.ini

# Set GOBOPTIONS=--migrate to run migrations and then exit
CMD python3 -m gobworkflow $GOBOPTIONS