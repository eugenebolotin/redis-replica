import BaseHTTPServer, httplib2, socket, json, base64, logger
from urlparse import parse_qs, urlparse
from threading import Thread

def load_info( data ):
    json_dump = base64.urlsafe_b64decode( data )
    prepared_info = json.loads( json_dump )

    info = {}
    for k, v in prepared_info:
        info[ tuple( json.loads( k ) ) ] = v
    return info

def dump_info( info ):
    prepared_info = map( lambda ( k, v ): ( json.dumps( k ), v ), info.iteritems() )
    json_dump = json.dumps( prepared_info )
    return base64.urlsafe_b64encode( json_dump )                                           

def multicast_pings( failover_id, failovers, last_info, timeout ):
    http = httplib2.Http( timeout = timeout )
    for failover in failovers:
        try:
            http.request( "http://" + ":".join( map( str, failover ) ) + "/info?id=" + failover_id + "&data=" + dump_info( last_info ) )
        except Exception, e:
            logger.error( "Multicast pings problem: %s" % str( e ) )

class HttpHandler( BaseHTTPServer.BaseHTTPRequestHandler ):
    def do_GET( self ):
        params = parse_qs( urlparse( self.path ).query )
        if ( "data" not in params ) or ( "id" not in params ):
            self.send_response( 200 )
            self.end_headers()
            return

        info = load_info( params[ "data" ][ 0 ] )            
        self.server.analyzer.push_info( params[ "id" ][ 0 ], info )
    
        self.send_response( 200 )
        self.end_headers()

    def log_request( self, code = "-", size = "-" ):
        logger.access( "%s %s" % ( str( code ), self.requestline ) )

class HttpServer( Thread ):
    def __init__( self, port, analyzer ):
        Thread.__init__( self )
        self.daemon = True

        self.port = port
        server_address = ( '', self.port )
        self.httpd = BaseHTTPServer.HTTPServer( server_address, HttpHandler )
        self.httpd.analyzer = analyzer

    def run( self ):
        while True:
            self.httpd.handle_request()

