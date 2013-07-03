#!/usr/bin/env python

import sys, os, uuid, string, time, redis, logger, socket, ConfigParser
from pingsanalyzer import PingsAnalyzer
from httpserver import HttpServer, multicast_pings
from daemonize import become_daemon

def read_serverlist( servers_str ):
    servers = []

    for server_str in map( string.strip, servers_str.split( "," ) ):
        if server_str:
            parts = server_str.split( ":" )
            if len( parts ) == 2:
                servers.append( ( unicode( parts[ 0 ] ), int( parts[ 1 ] ) ) )

    return servers        

def write_pid( pidfile ):
    print >> open( pidfile, "wt" ), os.getpid()

if len( sys.argv ) != 2:
    print >> sys.stderr, "Usage: ./redis-replica.py <config>"
    exit( 1 )


try:
    config = ConfigParser.SafeConfigParser( { "port": "16379", "redises": "", "failovers": "", "checkdelay": "1", "failtime": "5", "logs": "/var/log" } )
    config.read( sys.argv[ 1 ] )
    port = config.getint( "common", "port" )
    redises = read_serverlist( config.get( "common", "redises" ) )
    failovers = read_serverlist( config.get( "common", "failovers" ) )
    check_delay = config.getfloat( "common", "checkdelay" )
    failtime = config.getfloat( "common", "failtime" )
    logpath = config.get( "common", "logs" )
    pidfile = config.get( "common", "pidfile" )
except ConfigParser.Error, e:
    print >> sys.stderr, "Error: cannot parse config file"
    exit( 1 )

if not redises:
    print >> sys.stderr, "No redis instances are set in config."
    exit( 1 )

if len( redises ) != len( failovers ):
    print >> sys.stderr, "Incorrect config. Number of redises != number of failovers."
    exit( 1 )

try:    
    logger.configure( logpath )
except Exception, e:
    print >> sys.stderr, "Error while configuring logger:", e
    exit( 1 )

failover_id = str( uuid.uuid1() )
process_start = time.time()

analyzer = PingsAnalyzer( failtime, len( failovers ) )

try:    
    httpserver = HttpServer( port, analyzer )
except socket.error, e:
    print >> sys.stderr, "Error while starting http server:", e
    exit( 1 )

print "Replica process started. ReplicaProcessId = %s, Port = %d" % ( failover_id, port )
logger.trace( "Replica process started. ReplicaProcessId = %s, Port = %d" % ( failover_id, port ) )

become_daemon()
write_pid( pidfile )

httpserver.start()    

lasttime = {}
info = {}

while True:
    for hostport in redises:
        r = redis.Redis( hostport[ 0 ], port = int( hostport[ 1 ] ), socket_timeout = check_delay / 2 )
        role, master_host, master_port, used_memory = "", "", "", ""
        try:
            redis_info = r.info()
            if redis_info[ "loading" ] == 0:
                role = redis_info[ "role" ]
                used_memory = redis_info[ "used_memory" ]
                master_host = unicode( redis_info[ "master_host" ] )
                master_port = redis_info[ "master_port" ]
        except Exception, e:
            pass

        if role:
            lasttime[ hostport ] = time.time()
            info[ hostport ] = [ 0, role, master_host, master_port, used_memory ]
        else:
            if hostport not in lasttime:
                lasttime[ hostport ] = process_start
            if hostport not in info:
                info[ hostport ] = [ time.time() - lasttime[ hostport ], role, master_host, master_port, used_memory ]
            else:
                info[ hostport ][ 0 ] = time.time() - lasttime[ hostport ]

    multicast_pings( failover_id, failovers, info, check_delay / 2 )
    analyzer.push_info( failover_id, info )

    time.sleep( check_delay )

