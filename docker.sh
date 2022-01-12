#!/bin/bash

DIR_PATH="$(cd "$(dirname "$0")" && pwd -P)"

docker build -t ubuntu:stdeb .

docker run -ti  \
-u 1000:1000    \
--rm   \
--network=host  \
-v /mnt:/mnt    \
-w ${DIR_PATH}   \
ubuntu:stdeb /bin/bash
