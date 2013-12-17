#端口: 角色1位, 集群号1位, 实例号2位
#proxy       9xxx
#redis      20xxx
#sentinel   21xxx

cluster0 = {
    'redis': [
        # host:port, install path
        ['127.0.0.1:20001', '/tmp/redis-9001'],
        ['127.0.0.1:20002', '/tmp/redis-9001'],
        ['127.0.0.1:20003', '/tmp/redis-9001'],
        ['127.0.0.1:20004', '/tmp/redis-9001'],
    ],
    'twemproxy': [
        # host:port, install path
        ['127.0.0.1:9000', '/tmp/twemproxy-9000'],
        ['127.0.0.1:9001', '/tmp/twemproxy-9001'],
        ['127.0.0.1:9002', '/tmp/twemproxy-9002'],
        #...
    ],
    'sentinel':[
        ['127.0.0.1:21001', '/tmp/sentinel-21001'],
        ['127.0.0.1:21002', '/tmp/sentinel-21002'],
        ['127.0.0.1:21003', '/tmp/sentinel-21003'],
    ]
}



