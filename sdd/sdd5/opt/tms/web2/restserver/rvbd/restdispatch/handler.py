
from rvbd.extras import wsgiutils

class Request:

    def __init__(self, environ, start_response):
        self.__environ = environ
        self.__post_data = wsgiutils.get_post_data(environ)
        self.__query_params = wsgiutils.get_query_params(environ)
        self.__start_response = start_response

    def get_env(self, name):
        """!
        Get an environment variable.
        @param name the name of the variable.
        @return the value.
        """
        return self.__environ[name]

    def get_query_param(self, name):
        """!
        Get a query parameter.
        @param name the name of the parameter.
        @return the value.
        """
        return self.__query_params[name]

    def get_post_variable(self, name):
        """!
        Get a post variable.
        @param name the name of the variable.
        @return the value.
        """
        return self.__post_data[name]

    def get_query_params(self):
        """!
        Get the query params as a dict.
        @return a dict containing the query params.
        """
        return self.__query_params

    def get_post_data(self):
        """!
        Get the post data as a dict.
        @return a dict containing the post data.
        """
        return self.__post_data

    def respond(self, response):
        return response.send(self.__start_response)

class RequestHandler:

    def __init__(self, engine):
        self.__engine = engine

    def get_engine(self):
        """!
        Returns a reference to the engine.
        @return reference to the engine.
        """
        return self.__engine

    def register_paths(self, registry):
        """!
        Needs to be implemented by sub classes to register
        URL paths.
        """
        self.get_engine().log_error('register paths not implemented')

