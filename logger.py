import logging, os

TRACE_ID= "trace"
ACCESS_ID = "access"
ACTION_ID = "action"
ERROR_ID = "error"

def configure( path ):
    formatter = logging.Formatter( "[%(asctime)s] %(message)s", datefmt = "%Y.%m.%d %H:%M:%S" )

    for logid in [ TRACE_ID, ACCESS_ID, ACTION_ID, ERROR_ID ]:
        logger = logging.getLogger( logid )
        handler = logging.FileHandler( os.path.join( path, logid + ".log" ) )
        handler.setFormatter( formatter )
        logger.addHandler( handler )
        logger.setLevel( logging.INFO )

def log( logid, s ):
    logging.getLogger( logid ).info( s )

def trace( s ):
    log( TRACE_ID, s )

def access( s ):
    log( ACCESS_ID, s )

def action( s ):
    log( ACTION_ID, s )

def error( s ):
    log( ERROR_ID, s )
