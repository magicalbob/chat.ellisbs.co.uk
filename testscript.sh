pip install -r requirements.txt
./app_unittest.py
~/.local/bin/coverage run -m unittest app_unittest.py
~/.local/bin/coverage xml
rm -rf __pycache__
