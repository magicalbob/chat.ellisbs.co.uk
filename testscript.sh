cd /opt/pwd
pip install -r requirements.txt
./app_unittest.py
/home/appuser/.local/bin/coverage run -m unittest app_unittest.py
/home/appuser/.local/bin/coverage xml
rm -rf __pycache__
