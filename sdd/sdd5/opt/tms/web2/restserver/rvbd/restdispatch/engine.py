
from routes import Mapper
from rvbd.restdispatch import constants
from rvbd.restdispatch.claims import Claims
from rvbd.restdispatch.handler import Request
from rvbd.restdispatch.handler import RequestHandler
from rvbd.extras import wsgiutils
from logging.handlers import SysLogHandler
import base64
import inspect
import json
import rvbd_restdispatch_config
import logging
import os
import sys
import time

class Engine:
    """!
    Class that wraps up global state information for the
    REST Engine itself.
    """

    def log_debug(self, msg):
        self.__logger.debug('%s%s' % (self.__get_prefix(), msg))

    def log_info(self, msg):
        self.__logger.info('%s%s' % (self.__get_prefix(), msg))

    def log_error(self, msg):
        self.__logger.error('%s%s' % (self.__get_prefix(), msg))

    def log_warning(self, msg):
        self.__logger.warning('%s%s' % (self.__get_prefix(), msg))

    def log_critical(self, msg):
        self.__logger.critical('%s%s' % (self.__get_prefix(), msg))

    def get_namespaces(self):
        """!
        Return all the namespaces supported.
        Includes those supported by the REST Engine as well
        as those supported by product handlers.
        @return list of supported namespaces
        """
        return self.__namespaces

    def get_auth_info(self):
        """!
        Returns information that may be necessary to properly authenticate to the device.
        @return dict of supported namespaces
        """
        engine_info = {
            'supported_methods': ['OAUTH_2_0'],
            'specify_purpose': False,
            'login_banner': ''
        }

        try:
            info = rvbd_restdispatch_config.get_auth_info(engine_info)
        except AttributeError:
            # Method doesn't exist inside the config so just use our info.
            info = engine_info
        return info

    def handle_token_request(self, environ, start_response):
        """!
        Handles token requests.
        This is normally only called by the implementation of
        the 'token' api within the GL7 common module implementation.
        @param environ the WSGI environment variables
        @param start_response WSGI response callback
        @return response body iterable
        """
        return self.__handle_token_request(environ, start_response)

    def handle_request(self, environ, start_response):
        """!
        This method is called by the WSGI container when a request for
        the REST Engine comes in.

        The REST Engine pulls out the URL path from the PATH_INFO
        environment variable and then uses it with the Routes package
        to dispatch it to the proper request handler module.

        There are two mappers, one is public which does not require any
        authentication. The other is secure which requires a valid access
        token.

        The presence of the HTTP_AUTHORIZATION header determines which
        mappers are tried. If a HTTP_AUTHORIZATION header exists, we will
        try both beginning with the secure mapper. If the header does not
        exist, we skip the secure one and jump directly to the public.

        @param environ WSGI environment variables
        @param start_response WSGI response callback
        @return response body iterable
        """

        path = environ['PATH_INFO']

        # Make sure that the namespace and the version provided in the path
        # are one of the allowed services on this appliance.
        pathlist = path.split('/')
        if len(pathlist) < 3:
            return self.ResourceNotFoundErrorResponse().send(start_response)

        path_namespace = pathlist[1]
        path_version = pathlist[2]
        found = False
        for ns in self.__namespaces:
            if path_namespace == ns['id']:
                if path_version in ns['versions']:
                    found = True
                    break
            else:
                continue

        if found == False:
            return self.ResourceNotFoundErrorResponse().send(start_response)

        result = None
        if 'HTTP_AUTHORIZATION' in environ:
            result = self.__route_map_secure.match(path)
            if result != None:
                if not self.__is_authorized(environ):
                    return self.InvalidTokenErrorResponse().send(start_response)

        if result == None:
            result = self.__route_map_public.match(path)
            if result == None:
                return self.ResourceNotFoundErrorResponse().send(start_response)

        # Determine which controller is responsible for the requested API
        # and forward the request to the controller. At this point, the
        # request is authenticated already if it required authentication.

        try:
            controller_name = result['controller']
            action_name = result['action']

            # Figure out which type of request handler this was,
            # either a class derived from RequestHandler or
            # a WSGI application.

            if controller_name in self.__simple_handlers:
                return self.__handle_simple_request(result,
                                                    controller_name,
                                                    action_name,
                                                    environ,
                                                    start_response)
            else:
                return self.__handle_wsgi_request(result,
                                                  controller_name,
                                                  action_name,
                                                  environ,
                                                  start_response)

        except wsgiutils.WebError, e:
            return e.send(start_response)
        except Exception, e:
            self.log_error('Internal error servicing request \'%s\': %s' % (path, e))
            return self.InternalError().send(start_response)

    def __init__(self):
        self.__namespaces = []
        self.__route_map_public = None
        self.__route_map_secure = None
        self.__logger = None
        self.__auth_module = None
        self.__simple_handlers = {}

        self.__initialize_logger()
        self.__logger.info('REST subsystem initializing')
        self.__initialize_auth_module()
        self.__initialize_namespaces()
        self.__initialize_mappers()
        self.__initialize_handlers()
        self.__logger.info('REST subsystem ready')

    def __get_prefix(self):
        # SysLogHandler dumps raw lines to the /var/log/messages
        # file and we really want it properly formatted with
        # process name and pid. Unfortunately, getting the process
        # name is platform specific and there's no common way to
        # to do this currently in stock python. Leaving this open
        # for the future to pull in various open source libs that
        # do it in a platform specific way. For now, hardcode to
        # 'restd'.
        return 'restd[%u]: ' % (os.getpid())

    def __initialize_logger(self):
        self.__logger = logging.getLogger('REST Engine Logger')
        self.__logger.setLevel(logging.INFO)
        self.__logger.addHandler(SysLogHandler(address = '/dev/log'))

    def __initialize_auth_module(self):
        try:
            # Find the product specific authorization module and grab
            # function pointers to the various methods we will need access to.
            # If the auth module name is blank, then we assume no auth
            # module exists.

            auth_module_name = rvbd_restdispatch_config.AUTH_MODULE
            if len(auth_module_name) > 0:
                parts = auth_module_name.rpartition('.')
                module_name = parts[0]
                class_name = parts[2]

                __import__(module_name)
                auth_module = sys.modules[module_name]
                class_ref = getattr(auth_module, class_name)

                self.__auth_module = class_ref(self)

        except ImportError, e:
            self.log_error('Could not find authorization module.')
            raise e

    def __initialize_namespaces(self):
        # Load in the namespaces/versions supported by the product.
        # We're going to hold this until our GL7 common implementation
        # needs it to service the 'versions' API call.

        self.__namespaces += constants.NAMESPACES
        self.__namespaces += rvbd_restdispatch_config.NAMESPACES

    def __initialize_mappers(self):
        # Need to initialize the Routes mapper - the mapper is used to map incoming
        # URLs to the request handler module that services the URL.
        #
        # The public mapper contains calls that do not require any authentication.
        # The secure mapper contains calls that require a valid access token to call.

        self.__route_map_public = Mapper()
        self.__route_map_secure = Mapper()

    class InvalidRequestErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'Invalid request input provided.'):
            wsgiutils.ErrorResponse.__init__(self, 400, 'REQUEST_INVALID_INPUT', text)

    class InvalidTokenErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'Invalid auth token.'):
            wsgiutils.ErrorResponse.__init__(self, 401, 'AUTH_INVALID_TOKEN', text)

    class InvalidCodeErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'Invalid auth code.'):
            wsgiutils.ErrorResponse.__init__(self, 401, 'AUTH_INVALID_CODE', text)

    class ExpiredCodeErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'Expired auth code.'):
            wsgiutils.ErrorResponse.__init__(self, 401, 'AUTH_EXPIRED_CODE', text)

    class ResourceNotFoundErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'Resource not found.'):
            wsgiutils.ErrorResponse.__init__(self, 404, 'RESOURCE_NOT_FOUND', text)

    class InternalErrorResponse(wsgiutils.ErrorResponse):
        def __init__(self, text = 'An internal error has occurred.'):
            wsgiutils.ErrorResponse.__init__(self, 500, 'INTERNAL_ERROR', text)

    class Registry():

        def register(self, namespace, controller, paths):
            """!
            Register paths.
            Each path in the paths list is a tuple of
            path_snippet/secure_request/action_name.

            Example:
            [
               ('/my/insecure/api/call', False, 'my_insecure_call'),
               ('/my/secure/api/call', True, 'my_secure_call')
            ]

            @param namespace the namespace for this registration
            @param controller the controller module's full name
            @param paths list of paths
            """
            for path in paths:
                path_snippet = path[0]
                secure_request = path[1]
                action_name = path[2]

                if secure_request == True:
                    mapper = self.__secure_mapper
                else:
                    mapper = self.__public_mapper

                mapper.connect(None,
                               '/%s/{version}%s' % (namespace, path_snippet),
                               controller=controller,
                               action=action_name)

        def __init__(self, engine, public_mapper, secure_mapper):
            self.__engine = engine
            self.__public_mapper = public_mapper
            self.__secure_mapper = secure_mapper

    def load_handler_directory(self, directory, base_module_name = "rvbd.restdispatch.handlers."):
        """!
        Load any handlers found in the given directory.
        By default the rvbd.restdispatch.handlers directory is checked but
        this method allows additional directories to be loaded as well.
        """
        if not os.path.exists(directory):
            return

        files = os.listdir(directory)
        loaded_files = {}
        registry = self.Registry(self, self.__route_map_public, self.__route_map_secure)
        for f in files:
            try:
                name, extension = os.path.splitext(f)

                # Skip files that don't have a py or pyc extension.
                if not extension in ['.py', '.pyc']:
                    continue

                # Python will take care of loading the newer of the
                # py and pyc files. But we want to make sure we're not
                # loading it twice unnecessarily so keep an indicator
                # that we have already loaded the name prefix.

                if name in loaded_files:
                    continue
                else:
                    loaded_files[name] = name

                # Now see if it loads.
                module_name = base_module_name + name
                __import__(module_name)
                module = sys.modules[module_name]

            except ImportError, e:
                self.log_error('Error loading handler %s: %s' % (module_name, e))
                continue

            # Next iterate through any RequestHandlers we have inside
            # the module.

            for name, obj in inspect.getmembers(module):
                if hasattr(obj, '__bases__') and RequestHandler in obj.__bases__:
                    class_ref = getattr(module, name)
                    handler = class_ref(self)
                    handler.register_paths(registry)
                    self.__simple_handlers[str(obj)] = handler

            # Lastly, see if the module is using the WSGI-style
            # request handler and let it register using that method
            # if so.

            if hasattr(module, 'register_paths'):
                method_ref = getattr(module, 'register_paths')
                try:
                    method_ref(registry)
                except Exception, e:
                    # Catching all exceptions here because we don't want a
                    # single misbehaving handler to kill everyone.
                    self.log_error('Error loading handler %s: %s' % (module, e))

    def __initialize_handlers(self):
        # Load in the request handlers.
        # Request handlers are all found inside the rvbd.restdispatch.handlers module.
        # We're going to assume that all handlers are in the same directory
        # tree instead of found anywhere within the PYTHONPATH. Try loading
        # any files we find in that directory.
        handlers_path = os.path.join(os.path.dirname(constants.__file__), 'handlers')
        self.load_handler_directory(handlers_path)

        # Load component specific handlers. 
        # Here we assume that the handlers are the module's subdirectory "handlers"
        handlers_path = os.path.join(os.getcwd(), "handlers")
        self.load_handler_directory(handlers_path, "handlers.")
        
        # Also check any directories mentioned inside the config file.
        try:
            for directory in rvbd_restdispatch_config.HANDLER_DIRECTORIES:
                self.load_handler_directory(directory)
        except AttributeError:
            pass

    def __is_authorized(self, environ):
        # Check if an authorization module is configured and
        # fail this request if one is not.
        if self.__auth_module == None:
            return False

        try:
            auth_data = environ['HTTP_AUTHORIZATION']
        except KeyError, e:
            # missing the Authorization header so fail authorization.
            return False

        # The Authorization header sent by the client looks like this:
        #
        #     Authorization: Bearer <ACCESS_TOKEN>
        #
        # What we get via the HTTP_AUTHORIZATION environment variable
        # however has the label stripped out and thus we will get:
        #
        #     Bearer <ACCESS_TOKEN>
        #
        # We need to parse the auth_data into these two parts and
        # then validate the type and the access token.

        parts = auth_data.split()
        if len(parts) != 2:
            return False

        auth_type = parts[0]
        if auth_type != 'Bearer':
            return False

        # Decode the access token that we received and grab the
        # JTI out of it. We'll then ask the auth module to return
        # To us what the auth database has for that JTI and see
        # if what we got from the client matches what we have
        # in the database.

        try:
            bearer_token = parts[1]
            bearer_token_claims = Claims(bearer_token)
            bearer_jti = bearer_token_claims.get_field('jti')
        except Exception, e:
            return False

        token = self.__auth_module.get_access_token(bearer_jti)
        if token == None:
            return False

        if token != bearer_token:
            return False

        # Ensure that the token is not expired.
    
        exp_time = int(bearer_token_claims.get_field('exp'))
        current_time = int(time.time())
        
        if exp_time > 0 and exp_time < current_time:
            return False

        return True

    def __handle_token_request(self, environ, start_response):
        # Check if an authorization module is configured and
        # fail this request if one is not.
        if self.__auth_module == None:
            return wsgiutils.ErrorResponse(501, 'NOT_IMPLEMENTED', 'Not implemented.').send(start_response)

        # The POST data for a token request should contain three
        # parameters: grant_type, assertion, and state.

        post_data = wsgiutils.get_post_data(environ)

        if not 'grant_type' in post_data or not 'assertion' in post_data or not 'state' in post_data:
            return self.InvalidRequestErrorResponse().send(start_response)
        
        grant_type = post_data.get('grant_type', [''])[0]
        assertion = post_data.get('assertion', [''])[0]
        state = post_data.get('state', [''])[0]

        # Only support 'access_code' grant_type in this release.

        if grant_type != 'access_code':
            return self.InvalidRequestErrorResponse().send(start_response)

        # The assertion looks like this according to GL3:
        #
        #     <header>.<access_code>.<signature>
        #
        # We will error out if the assertion is malformed.

        jwt = assertion.split('.')
        if len(jwt) != 3:
            return self.InvalidRequestErrorResponse().send(start_response)

        jwt_header_encoded = jwt[0]
        jwt_access_code = jwt[1]
        jwt_signature_encoded = jwt[2]

        # The JWT Header is a base64url encoded JSON string that
        # once decoded should look like this:
        #
        #    { "alg": "none" }
        #
        # Verify that the algorithm is indeed "none" because we
        # don't support anything else in the first release.

        try:
            jwt_header = json.loads(base64.urlsafe_b64decode(jwt_header_encoded))
            jwt_algorithm = jwt_header['alg']
        except Exception, e:
            return self.InvalidRequestErrorResponse().send(start_response)

        if jwt_algorithm != 'none':
            return self.InvalidRequestErrorResponse().send(start_response)

        # Pull out the jti from the access code we received inside
        # the JWT. Then use that to lookup the access code we
        # have inside the database. If we get nothing back,
        # obviously we fail. If we do get something back, we still
        # need to make sure the access code we got matches exactly
        # the access code we have inside the database.

        try:
            code_claims = Claims(jwt_access_code)
            access_code_jti = code_claims.get_field('jti')
            access_code = self.__auth_module.get_access_code(access_code_jti)
        except Exception, e:
            return self.InvalidRequestErrorResponse().send(start_response)

        if access_code == None:
            return self.InvalidCodeErrorResponse().send(start_response)

        if jwt_access_code != access_code:
            return self.InvalidCodeErrorResponse().send(start_response)

        # Now check to make sure the access code has not
        # expired yet. Times are stored in UTC/GMT.

        exp_time = int(code_claims.get_field('exp'))
        current_time = int(time.time())

        if exp_time > 0 and exp_time < current_time:
            return self.ExpiredCodeErrorResponse().send(start_response)

        # Ok at thie point everything looks good so generate
        # a new token, store it in the auth database, and return
        # to the caller.
        #
        # Note for the lifetime, we need to check the remaining
        # time on the access code and take that into account.

        lifetime = rvbd_restdispatch_config.TOKEN_LIFETIME
        if exp_time > 0 and (exp_time - current_time) < lifetime:
            lifetime = (exp_time - current_time)
        
        token_claims = Claims(principle=code_claims.get_field('prn'),
                              lifetime=lifetime)
        token = token_claims.get_encoded()

        if not self.__auth_module.store_access_token(code_claims,
                                                     token_claims,
                                                     token):
            raise wsgiutils.WebError(500, 'Error storing access token')

        data = {
            'access_token': token,
            'token_type': 'bearer',
            'expires_in': rvbd_restdispatch_config.TOKEN_LIFETIME,
            'state': state,
            'allowed_signature_types': ['none'],
        }

        return wsgiutils.JsonResponse(data).send(start_response)

    def __handle_simple_request(self,
                                params,
                                controller_name,
                                action_name,
                                environ,
                                start_response):

        # This is a request handled by a RequestHandler child class.
        # Find the action method and call it.

        handler = self.__simple_handlers[controller_name]
        method = getattr(handler, action_name)

        # The argument list should contain variables matched in
        # the route. Since we're copying the route match params,
        # we need to remove the entries for controller and action.

        parameters = params.copy()
        parameters['request'] = Request(environ, start_response)
        del parameters['controller']
        del parameters['action']

        # Call the method and return the results.

        return method(**parameters)

    def __handle_wsgi_request(self,
                              params,
                              controller_name,
                              action_name,
                              environ,
                              start_response):

        # This is a request handled by a WSGI application.
        # Find the action method and call it.

        if not controller_name in sys.modules:
            try:
                __import__(controller_name)
            except ImportError, e:
                self.log_error('Could not load controller module %s: %s' % (controller_name, e))
                raise e

        controller = sys.modules[controller_name]
        method = getattr(controller, action_name)

        # The environ dict is updated to include some helper
        # variables from the REST Engine, primarily variables
        # returned by the Routes package so that the controller
        # does not have to parse the URL again.

        for name, value in params.items():
            if not name in ['controller', 'action']:
                environ['parameter_%s' % name] = value

        # The argument list should contain the WSGI parameters that
        # were passed into this method.

        parameters = {}
        parameters['environ'] = environ
        parameters['start_response'] = start_response

        # Call the method with the arguments that were in the mapper.
        # The method should be one that implements the WSGI
        # application interface.

        return method(**parameters)
