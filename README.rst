README
######

this script will deploy a redis cluster with:

- redis
- redis-sentinel
- twemproxy

config
======

::

    cluster0 = {
        'cluster_name': 'cluster0',
        'user': 'ning',
        'redis': [
            # master host:port, install path         # slave
            ('127.0.0.5:20000', '/tmp/redis-20000'), ('127.0.0.5:30000', '/tmp/redis-30000'), 
            ('127.0.0.5:20001', '/tmp/redis-20001'), ('127.0.0.5:30001', '/tmp/redis-30001'),
        ],
        'sentinel':[
            ('127.0.0.5:21001', '/tmp/sentinel-21001'),
            ('127.0.0.5:21002', '/tmp/sentinel-21002'),
            ('127.0.0.5:21003', '/tmp/sentinel-21003'),
        ],
        'nutcracker': [
            ('127.0.0.5:22000', '/tmp/nutcracker-22000'),
            ('127.0.0.5:22001', '/tmp/nutcracker-22001'),
            ('127.0.0.5:22002', '/tmp/nutcracker-22002'),
        ],
    }

this will gen ``sentinel``  config::

    sentinel monitor cluster0-20000 127.0.0.5 20000 2
    sentinel down-after-milliseconds  cluster0-20000 60000
    sentinel failover-timeout cluster0-20000 180000
    sentinel parallel-syncs cluster0-20000 1
            
    sentinel monitor cluster0-20001 127.0.0.5 20001 2
    sentinel down-after-milliseconds  cluster0-20001 60000
    sentinel failover-timeout cluster0-20001 180000
    sentinel parallel-syncs cluster0-20001 1

and ``twemproxy`` config::

    cluster0:
      listen: 127.0.0.5:22000
      hash: fnv1a_64
      distribution: modula
      preconnect: true
      auto_eject_hosts: false
      redis: true
      backlog: 512
      client_connections: 0
      server_connections: 1
      server_retry_timeout: 2000
      server_failure_limit: 2
      servers:
        - 127.0.0.5:20000:1 cluster0-20000
        - 127.0.0.5:20001:1 cluster0-20001

usage
=====

::

    $ ./bin/deploy.py -h
    usage: deploy.py [-h] [-v] [-o LOGFILE]
                     {deploy,log,start,status,stop} {cluster0}

    $ ./bin/deploy.py deploy cluster0
    $ ./bin/deploy.py start cluster0
    $ ./bin/deploy.py status cluster0
    $ ./bin/deploy.py log cluster0
    $ ./bin/deploy.py stop cluster0

example::

    $ ./bin/deploy.py start cluster0
    2013-12-18 14:34:15,934 [MainThread] [INFO] start running: ./bin/deploy.py -v start cluster0
    2013-12-18 14:34:15,934 [MainThread] [INFO] Namespace(logfile='log/deploy.log', op='start', target='cluster0', verbose=1)
    2013-12-18 14:34:15,936 [MainThread] [NOTICE] start redis
    2013-12-18 14:34:15,936 [MainThread] [INFO] start [RedisServer:127.0.0.5:20000]
    2013-12-18 14:34:16,122 [MainThread] [INFO] start [RedisServer:127.0.0.5:30000]
    2013-12-18 14:34:16,301 [MainThread] [INFO] start [RedisServer:127.0.0.5:20001]
    2013-12-18 14:34:16,489 [MainThread] [INFO] start [RedisServer:127.0.0.5:30001]
    2013-12-18 14:34:16,691 [MainThread] [INFO] start [RedisServer:127.0.0.5:20002]
    2013-12-18 14:34:16,905 [MainThread] [INFO] start [RedisServer:127.0.0.5:30002]
    2013-12-18 14:34:17,102 [MainThread] [INFO] start [RedisServer:127.0.0.5:20003]
    2013-12-18 14:34:17,310 [MainThread] [INFO] start [RedisServer:127.0.0.5:30003]

    2013-12-18 14:34:17,513 [MainThread] [NOTICE] start sentinel
    2013-12-18 14:34:17,513 [MainThread] [INFO] start [Sentinel:127.0.0.5:21001]
    2013-12-18 14:34:17,706 [MainThread] [INFO] start [Sentinel:127.0.0.5:21002]
    2013-12-18 14:34:17,913 [MainThread] [INFO] start [Sentinel:127.0.0.5:21003]

    2013-12-18 14:34:18,102 [MainThread] [NOTICE] start nutcracker
    2013-12-18 14:34:18,102 [MainThread] [INFO] start [NutCracker:127.0.0.5:22000]
    2013-12-18 14:34:18,325 [MainThread] [INFO] start [NutCracker:127.0.0.5:22001]
    2013-12-18 14:34:18,516 [MainThread] [INFO] start [NutCracker:127.0.0.5:22002]

Dependency
==========

- pcl: https://github.com/idning/pcl


