#coding: utf-8
#端口: 角色1位, 集群号1位, 实例号2位, 主从端口一样
#proxy       9xxx
#redis      20xxx
#sentinel   21xxx


#we will gen:
#port
#pidfile
#logfile
#dir

#path in the deploy machine
binarys = {
    'redis_server' : '/home/ning/idning-github/redis/src/redis-server',
    'redis_cli' : '/home/ning/idning-github/redis/src/redis-cli',
    'redis_sentinel' : '/home/ning/idning-github/redis/src/redis-sentinel',
    'twemproxy' : 'xxx',
}

cluster0 = {
    'user': 'ning',
    'redis': [
        # host:port, install path
        ('127.0.0.5:20001', '/tmp/redis-20001'), ('127.0.0.5:30001', '/tmp/redis-30001'), #(示例配置, 主从端口分别用2xxxx/3xxxx)
        #('127.0.0.5:20002', '/tmp/redis-20002'), ('127.0.0.5:30002', '/tmp/redis-30002'),
        #('127.0.0.5:20003', '/tmp/redis-20003'), ('127.0.0.5:30003', '/tmp/redis-30003'),
        #('127.0.0.5:20004', '/tmp/redis-20004'), ('127.0.0.5:30004', '/tmp/redis-30004'),
    ],
    'twemproxy': [
        # host:port, install path
        ('127.0.0.5:9000', '/tmp/twemproxy-9000'),
        ('127.0.0.5:9001', '/tmp/twemproxy-9001'),
        ('127.0.0.5:9002', '/tmp/twemproxy-9002'),
        #...
    ],
    'sentinel':[
        ('127.0.0.5:21001', '/tmp/sentinel-21001'),
        ('127.0.0.5:21002', '/tmp/sentinel-21002'),
        ('127.0.0.5:21003', '/tmp/sentinel-21003'),
    ]
}
