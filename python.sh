#!/bin/sh

#!/bin/bash

if [ -d venv ]; then
    . venv/bin/activate
else
    python3 -m venv venv
    if [ $? -ne 0 ]; then
      exit 1
    fi
    . venv/bin/activate
    pip install -r requirements.txt
fi

python $@