FROM gitpod/workspace-mysql:latest

# install python3-dev to make sure the pip package "mysqlclient" works fine.
USER root
RUN apt-get update && apt-get install -y pkg-config python3-dev
RUN pyenv install 3.6.15
RUN pyenv local 3.6.15
RUN pip install pipenv