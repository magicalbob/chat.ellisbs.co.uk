FROM almalinux:9

RUN dnf update -y
RUN dnf install -y python3-pip
COPY testscript.sh /root/testscript.sh
CMD sh -c /root/testscript.sh
