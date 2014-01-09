#coding: utf-8
#the port: role: x, cluster_id: x, instance:xx
#       2        0              x           xx

#redis-master   20xxx
#redis-slave    21xxx
#proxy          22xxx 23xxx(status-port)
#sentinel       29xxx

#we will generate:
#port
#pidfile
#logfile
#dir

#path in the deploy machine
BINARYS = {
    'REDIS_SERVER_BINS' : '/home/ning/idning-github/redis/src/redis-*',
    'REDIS_CLI' : '/home/ning/idning-github/redis/src/redis-cli',
    'REDIS_SENTINEL_BINS' : '/home/ning/idning-github/redis/src/redis-sentinel',
    'NUTCRACKER_BINS' : '/home/ning/Desktop/t/nutcracker-0.2.4/output/bin/nutcracker',
}

RDB_SLEEP_TIME = 1

#optional
REDIS_MONITOR_EXTRA = {
    'used_cpu_user':              (0, 50),
}

#optional
NUTCRACKER_MONITOR_EXTRA = {
    'client_connections':  (0, 10),
    "forward_error_INC":   (0, 1000),  # in every minute
    "client_err_INC":      (0, 1000),  # in every minute
    'in_queue':            (0, 10),
    'out_queue':           (0, 10),
}

cluster0 = {
    'cluster_name': 'cluster0',
    'user': 'ning',
    'sentinel':[
        ('127.0.0.5:29001', '/tmp/r/sentinel-29001'),
        ('127.0.0.5:29002', '/tmp/r/sentinel-29002'),
        ('127.0.0.5:29003', '/tmp/r/sentinel-29003'),
    ],
    'redis': [
        # master(host:port, install path)       ,  slave(host:port, install path)
        ('127.0.0.5:20000', '/tmp/r/redis-20000'), ('127.0.0.5:21000', '/tmp/r/redis-21000'),
        ('127.0.0.5:20001', '/tmp/r/redis-20001'), ('127.0.0.5:21001', '/tmp/r/redis-21001'),
        ('127.0.0.5:20002', '/tmp/r/redis-20002'), ('127.0.0.5:21002', '/tmp/r/redis-21002'),
        ('127.0.0.5:20003', '/tmp/r/redis-20003'), ('127.0.0.5:21003', '/tmp/r/redis-21003'),
    ],
    'nutcracker': [
        ('127.0.0.5:22000', '/tmp/r/nutcracker-22000'),
        ('127.0.0.5:22001', '/tmp/r/nutcracker-22001'),
        ('127.0.0.5:22002', '/tmp/r/nutcracker-22002'),
    ],
}


