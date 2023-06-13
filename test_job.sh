rm -rf __pycache__
touch coverage.xml
chmod 777 coverage.xml
docker build -t local:testchat .
docker run -v ${PWD}:/opt/pwd local:testchat
