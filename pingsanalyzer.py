import redis, logger, time, copy
from collections import defaultdict
from threading import Lock

def nodes_to_string( nodes ):
    return ", ".join( map( lambda node: "%s:%d" % ( node[ 0 ], node[ 1 ] ), nodes ) )

def build_memsorted_nodes( candidates, used_memory ):
    if not candidates:
        return []

    mem = sorted( [ ( used_memory[ server ], server ) for server in candidates ], reverse = True )
    candidate_list = [ ( 1, mem[ 0 ][ 1 ], mem[ 0 ][ 0 ] ) ]

    for i in xrange( len( mem ) - 1 ):
        if mem[ i ][ 0 ] == 0 or ( abs( mem[ i ][ 0 ] - mem[ i + 1 ][ 0 ] ) * 100 ) / mem[ i ][ 0 ] < 10:
            candidate_list.append( ( candidate_list[ -1 ][ 0 ], mem[ i + 1 ][ 1 ], candidate_list[ -1 ][ 2 ] ) )
        else:
            candidate_list.append( ( candidate_list[ -1 ][ 0 ] + 1, mem[ i + 1 ][ 1 ], mem[ i + 1 ][ 0 ] ) )

    return sorted( candidate_list )

def select_master( candidates, alive_nodes, used_memory, slave_links ):
    if slave_links:
        candidates = slave_links

    candidate_list = build_memsorted_nodes( candidates, used_memory )
    master = candidate_list[ 0 ][ 1 ]

    if slave_links:
        logger.action( "Electing master from slave_links with more used_memory: %s" % nodes_to_string( [ master ] ) )
    else:
        logger.action( "Electing master with more used_memory: %s" % nodes_to_string( [ master ] ) )

    try:
        r = redis.Redis( host = master[ 0 ], port = master[ 1 ] )
        r.slaveof()
    except Exception, e:
        if str( e ).find( "Redis is loading data into memory" ) < 0:
            logger.error( "Error while master slaveof(): %s" % str( e ) )

    configure_slaves( alive_nodes, master )        

def configure_slaves( alive_nodes, master ):
    for node in alive_nodes:
        if node != master:
            try:
                r = redis.Redis( host = node[ 0 ], port = node[ 1 ] )
                r.slaveof( host = master[ 0 ], port = master[ 1 ] )
            except Exception, e:
                if str( e ).find( "Redis is loading data into memory" ) < 0:
                    logger.error( "Error while node slaveof( master ): %s" % str( e ) )

def move_to_readonly( nodes ):
    for node in nodes:
        try:
            r = redis.Redis( host = node[ 0 ], port = node[ 1 ] )
            r.slaveof( host = "127.0.0.1", port = 0 )
        except Exception, e:
            if str( e ).find( "Redis is loading data into memory" ) < 0:
                logger.error( "Error while node slaveof( master ): %s" % str( e ) )

class PingsAnalyzer:
    def __init__( self, failtime, total_failovers ):
        self.data = {}
        self.lock = Lock()
        self.failtime = failtime
        self.total = total_failovers

    def push_info( self, failoverid, info ):
        info = copy.deepcopy( info )

        with self.lock:
            for redis_name, stat in info.iteritems():
                stat[ 0 ] = time.time() - stat[ 0 ]

            self.data[ failoverid ] = info
            self.__analyze_pings()

    def __process_quorum( self, alive_nodes, masters, slave_links, used_memory ):
        if not masters:
            logger.action( "No master nodes. Alive nodes: %s. Electing..." % nodes_to_string( alive_nodes ) )
            select_master( alive_nodes, alive_nodes, used_memory, [] )
        elif len( masters ) > 1:
            logger.action( "More than one master: %s. Electing one..." % nodes_to_string( masters ) )
            select_master( masters, alive_nodes, used_memory, slave_links )
        elif len( slave_links ) > 1 or ( slave_links and slave_links != set( masters ) ):
            logger.action( "Slaves are connected to different masters. Masters: %s. Slave links: %s. Selecting current master..." % ( nodes_to_string( masters ), nodes_to_string( slave_links ) )  )
            configure_slaves( alive_nodes, masters[ 0 ] )

    def __process_nonquorum( self, alive_nodes, masters ):
        if len( masters ) > 0 and alive_nodes == masters:
            logger.action( "Isolated master node: %s. Moving it to readonly slave..." % nodes_to_string( masters ) )
            move_to_readonly( masters ) 

    def __collect_nodes_info( self ):
        alive_nodes = defaultdict( int )
        masters = defaultdict( int )
        slave_links = set()
        used_memory_info = defaultdict( list )

        data_new = {}
        for failoverid, info in self.data.iteritems():
            something_actual = False
            for server in info:
                if time.time() - info[ server ][ 0 ] < self.failtime:
                    something_actual = True
                    alive_nodes[ server ] += 1
                    if info[ server ][ 4 ]:
                        used_memory_info[ server ].append( info[ server ][ 4 ] )
                    if info[ server ][ 1 ] == "master":
                        masters[ server ] += 1
                    elif info[ server ][ 1 ] == "slave":
                        slave_links.add( ( info[ server ][ 2 ], info[ server ][ 3 ] ) )
            if something_actual:
                data_new[ failoverid ] = info

        used_memory = defaultdict( int )                
        for server, sizes in used_memory_info.iteritems():
            used_memory[ server ] = sum( sizes ) / len( sizes )

        self.data = data_new
        return alive_nodes, masters, slave_links, used_memory

    def __analyze_pings( self ):
        alive_nodes, masters, slave_links, used_memory = self.__collect_nodes_info()

        nonquorum_alive_nodes = sorted( map( lambda( k, v ): k, filter( lambda ( k, v ): v <= 1 or v <= self.total / 2, alive_nodes.iteritems() ) ) )
        nonquorum_masters = sorted( map( lambda( k, v ): k, filter( lambda ( k, v ): v <= 1 or v <= self.total / 2, masters.iteritems() ) ) )

        quorum_alive_nodes = sorted( map( lambda( k, v ): k, filter( lambda ( k, v ): v > 1 and v > self.total / 2, alive_nodes.iteritems() ) ) )
        quorum_masters = sorted( map( lambda( k, v ): k, filter( lambda ( k, v ): v > 1 and v > self.total / 2, masters.iteritems() ) ) )

        logger.trace( "Total failovers = %d" % self.total )
        logger.trace( "NonQuorum Alive nodes = %s" % nodes_to_string( nonquorum_alive_nodes ) )
        logger.trace( "NonQuorum Masters     = %s" % nodes_to_string( nonquorum_masters ) )
        logger.trace( "Quorum Alive nodes    = %s" % nodes_to_string( quorum_alive_nodes ) )
        logger.trace( "Quorum Masters        = %s" % nodes_to_string( quorum_masters ) )

        if quorum_alive_nodes:
            self.__process_quorum( quorum_alive_nodes, quorum_masters, slave_links, used_memory )
        self.__process_nonquorum( nonquorum_alive_nodes, nonquorum_masters )

