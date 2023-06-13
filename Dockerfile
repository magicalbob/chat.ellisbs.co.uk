FROM almalinux:9

RUN dnf update -y && \
    dnf install -y python3-pip

RUN useradd -ms /bin/bash appuser

COPY testscript.sh /home/appuser/testscript.sh

RUN chown appuser:appuser /home/appuser/testscript.sh && \
    mkdir /opt/pwd && chown appuser:appuser /opt/pwd

USER appuser

WORKDIR /home/appuser

RUN pip install coverage

CMD sh -c ./testscript.sh

