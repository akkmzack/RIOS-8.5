
from rvbd.restdispatch.engine import Engine

_engine = None

def get_engine():
    return _engine

def application(environ, start_response):
    """!
    Main WSGI entry point for the REST Engine.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    @return response iterable
    """
    return get_engine().handle_request(environ, start_response)

# Initialize the REST Engine.
# Global singleton.

_engine = Engine()
