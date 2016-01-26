
from rvbd.restdispatch.service import get_engine
from rvbd.extras import wsgiutils
import rvbd_restdispatch_config

def register_paths(registry):
    registry.register('common',
                      'rvbd.restdispatch.handlers.common',
                      [
                          ('/info', False, 'info'),
                          ('/ping', False, 'ping'),
                          ('/auth_info', False, 'auth_info'),
                          ('/oauth/token', False, 'token'),
                          ('/services', False, 'services')
                      ])

def info(environ, start_response):
    """!
    Send back some device/server information.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    """

    # The REST Engine doesn't have any of this information.
    # This must all be provided by the product that is using
    # the REST Engine.
    #
    # We have to call the product code dynamically here because the
    # contents of the info structure may dynamically update.

    version = environ['parameter_version']
    info = rvbd_restdispatch_config.get_info(version)
    return wsgiutils.JsonResponse(info).send(start_response)

def ping(environ, start_response):
    """!
    Ping is supposed to return a status 204 with no content body.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    """
    return wsgiutils.StatusCodeResponse(204).send(start_response)

def auth_info(environ, start_response):
    """!
    Returns information that may be necessary to properly authenticate to the device.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    """
    return wsgiutils.JsonResponse(get_engine().get_auth_info()).send(start_response)

def token(environ, start_response):
    """!
    Generate an access token and return it to the client after
    validating the provided access code.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    """
    return get_engine().handle_token_request(environ, start_response)

def services(environ, start_response):
    """!
    Return all the namespaces and versions supported by this device.
    @param environ the WSGI environment variables
    @param start_response the WSGI response callback
    """
    return wsgiutils.JsonResponse(get_engine().get_namespaces()).send(start_response)
