FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update
#RUN apt-get install -y make python3 python3-pip python3-stdeb libglib2.0-dev libgirepository1.0-dev libcairo2-dev python3-dev dh-python python-all
RUN apt-get install -y sudo make python3 python3-pip python3-stdeb fakeroot dh-python python-all
# RUN pip3 install stem stdeb
RUN groupadd -r -g 1000 docker && useradd -m -u 1000 -g 1000 docker && adduser docker sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER docker
CMD /bin/bash

# volumes and ports
# EXPOSE 4711/tcp 4712/tcp 4672/udp 4665/udp 4662/tcp 4661/tcp 

#ENTRYPOINT /usr/bin/amuled
#CMD -c /config 
#CMD -c /mnt/data/Downloads/.aMule
