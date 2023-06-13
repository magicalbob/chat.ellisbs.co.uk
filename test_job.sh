rm -rf __pycache__
docker build -t local:testchat .
docker run -v ${PWD}:/opt/pwd local:testchat
