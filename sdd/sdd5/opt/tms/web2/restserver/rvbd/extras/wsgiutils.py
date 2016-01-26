
from cgi import parse_qs
import urllib
import json
import httplib

class Response:
    def __init__(self, status_code, ctype, body, other_headers = {}):
        self.status = '%u %s' % (status_code, httplib.responses[status_code])
        self.body = body
        self.headers = other_headers
        self.headers['Content-type'] = ctype
        self.cacheable = False

    def set_cacheable(self, cacheable):
        self.cacheable = cacheable

    def send(self, start_response):
        response_headers = self.headers.copy()

        if self.cacheable:
            response_headers['Cache-control'] = 'no-store'
            response_headers['Pragma'] = 'no-cache'
        
        start_response(self.status, response_headers.items())
        return self.body

class StatusCodeResponse(Response):
    def __init__(self, status_code):
        Response.__init__(self, status_code, 'text/plain', '', {})

class SimpleResponse(Response):
    def __init__(self, status_code):
        Response.__init__(self, status_code, 'text/plain',
                          [httplib.responses[status_code]],
                          {})

class ErrorResponse(Response):
    def __init__(self, status_code, error_id, error_text, error_info = None):
        payload = {}
        payload['error_id'] = error_id
        payload['error_text'] = error_text

        if error_info != None:
            payload['error_info'] = error_info

        Response.__init__(self, status_code, 'application/json',
                          [json.dumps(payload, sort_keys=True, indent=4)],
                          {})

class StringResponse(Response):
    def __init__(self, body):
        Response.__init__(self, 200, 'text/plain', [body], {})

class IterableResponse(Response):
    def __init__(self, ctype, iterable, other_headers = {}):
        Response.__init__(self, 200, ctype, iterable, other_headers)

class JsonResponse(Response):
    def __init__(self, obj, other_headers = {}):
        Response.__init__(self, 200, 'application/json',
                          [json.dumps(obj, sort_keys=True, indent=4)], other_headers)

class WebError(Exception, Response):
    def __init__(self, status_code, body):
        Response.__init__(self, status_code, 'text/plain', [body])

def get_post_data(environ):
    """!
    Helper function to get the post data into a dict.
    @param environ the WSGI environment variables
    @return dict of post data
    """
    data = {}

    try:
        length = int(environ.get('CONTENT_LENGTH', '0'))
    except ValueError:
        length = 0

    if length > 0:
        content = environ['wsgi.input'].read(length)
        data = parse_qs(content)

    return data

def get_query_params(environ):
    """!
    Helper function to get query parameters into a dict.
    @param environ the WSGI environment variables
    @return dict of query parameters
    """
    return parse_qs(environ['QUERY_STRING'])

def parse_params(s, expected = ()):
    D = {}
    if len(s) > 0:
        for a in s.split('&'):
            name, value = a.split('=', 1)
            value = urllib.unquote_plus(value)
            D[name] = value
        
    for e in expected:
        if e not in D:
            raise WebError(400, 'missing %s parameter' % e)
    return D
    
