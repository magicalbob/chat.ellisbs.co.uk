#!/usr/bin/env bash

cd /home/vagrant/projects/chat.ellisbs.co.uk

. /home/vagrant/chat/bin/activate

export OPENAI_API_KEY="$OPENAI_API_KEY"
export USE_DEBUG=True

python3 app.py
