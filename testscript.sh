cd /opt/pwd
pip install -r requirements.txt
./app_unittest.py
coverage run -m unittest app_unittest.py
coverage xml
rm -rf __pycache__
