#!/bin/bash
#file   : run.sh
#author : ning
#date   : 2014-01-06 16:30:21


./bin/deploy.py cluster0 deploy
./bin/deploy.py cluster0 start
./bin/deploy.py cluster0 printcmd
./bin/deploy.py cluster0 status
./bin/deploy.py cluster0 log
./bin/deploy.py cluster0 mastercmd 'PING'
./bin/deploy.py cluster0 rdb

./bin/deploy.py cluster0 failover &
./bin/deploy.py cluster0 randomkill 
pkill -f './bin/deploy.py'

./bin/deploy.py cluster0 mq &
./bin/deploy.py cluster0 bench
pkill -f './bin/deploy.py'

./bin/deploy.py cluster0 stop



