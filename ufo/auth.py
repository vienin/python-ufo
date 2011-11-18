import new
import urlparse
import urllib
import Cookie
from httplib import HTTPSConnection

import ufo.errors as errors
from ufo.debugger import Debugger

class NullAuthenticator(Debugger):
    def __init__(self):
        self.authenticated = False

    def debug(self, msg):
        print msg

    def login(self):
        self.authenticated = True
        return True

    def ensure_login(self):
        if not self.authenticated:
            self.debug("Not authenticated yet, logging in")
            self.login()
            self.debug("Successfully authenticated")

    def bind(self, conn, service="HTTP", host=""):
        if not host:
            host = conn.host
        def endheaders(_self, body=None):
            self.ensure_login()

            for header, value in self.get_headers(service, host).items():
                _self.putheader(header, value)
                self.debug("Sending header %s=%s" % (header, value))

            try:
                return _self.__class__.endheaders(_self, body)
            except TypeError:
                return _self.__class__.endheaders(_self)

        conn._service = service
        conn._host = host
        conn.endheaders = new.instancemethod(endheaders, conn)


class SPNEGOAuthenticator(NullAuthenticator):
    def __init__(self):
        NullAuthenticator.__init__(self)

    def login(self):
        # TODO: get TGT ticket from credentials
        return NullAuthenticator.login(self)

    def get_headers(self, service, host):
        self.ensure_login()

        import kerberos as k

        result, context = k.authGSSClientInit("%s@%s" % (service, host))
        if result < 1:
            raise errors.AuthenticationError("authGSSClientInit returned result %d" % result)

        result = k.authGSSClientStep(context, "WWW-Authenticate")
        if result < 0:
            raise errors.AuthenticationError("authGSSClientStep returned result %d" % result)

        return { "Authorization" : "Negotiate %s" % k.authGSSClientResponse(context) }


class WebAuthAuthenticator(NullAuthenticator):
    LOGIN_HOST = "my.agorabox.org"

    def __init__(self, username="", password=""):
        NullAuthenticator.__init__(self)
        self.cookie = Cookie.SimpleCookie()
        self.username = username
        self.password = password

    def login(self):
        conn = HTTPSConnection(WebAuthAuthenticator.LOGIN_HOST, 443)

        if not self.username or not self.password:
            raise errors.AuthenticationError("You need to specify a login and a password to authenticate")

        conn.request("GET", "/")
        resp = conn.getresponse()
        location = resp.getheader("Location", "")
        if location:
            url = urlparse.urlparse(location)
            query = urlparse.parse_qs(url.query)
            RT = query['RT'][0]
            ST = query['ST'][0]
            LC = '>'
            login = "yes"
            params = urllib.urlencode({'RT': RT, 'ST': ST, 'LC': '>',
                                       'login': "yes", 'username' : self.username,
                                       'password' : self.password }) 
            conn.request('POST', '/login', params, { "Referer" : location })
            resp = conn.getresponse()

            while True:
                location = resp.getheader("Location", "")

                for header, value in resp.getheaders():
                    if header == "set-cookie":
                        cookie = Cookie.SimpleCookie(value)
                        self.cookie.update(cookie)

                if resp.status in (302, 303) and location:
                    conn = HTTPSConnection(WebAuthAuthenticator.LOGIN_HOST, 443)
                    conn.request('GET', location)
                    resp = conn.getresponse()
                    continue

                break

            resp.read()

            self.authenticated = True
            self.clear_credentials()

        else:
            raise errors.InvalidAuthenticationMethod(method=self.method)

    def logout(self):
        self.cookie = Cookie.SimpleCookie()
        NullAuthenticator.logout(self)

    def clear_credentials(self):
        self.username = ""
        self.password = ""

    def set_credentials(self, username, password):
        self.username = username
        self.password = password

    def get_cookie(self):
        self.ensure_login()

        items = self.cookie.items()
        items.sort()
        result = []
        for K,V in items:
            result.append( V.OutputString() )
        cookie = "; ".join(result)
        return cookie

    def get_headers(self, service, host):
        self.ensure_login()

        items = self.cookie.items()
        items.sort()
        result = []
        for K,V in items:
            result.append( V.OutputString() )
        cookie = "; ".join(result)
                                                            
        return { "Cookie" : cookie }

    def get_connection(self, url):
        parts = urlparse.urlparse(url)
        conn = HTTPSConnection(parts.hostname, parts.port)
        self.bind(conn)
        return conn

def get_authenticator(method):
    if method not in _authenticators:
        if method == "webauth":
            authenticator = WebAuthAuthenticator()
        elif method == "spnego":
            authenticator = SPNEGOAuthenticator()
        else:
            raise Exception('Invalid authentication method %s' % method)
        _authenticators[method] = authenticator
    else:
        authenticator = _authenticators[method]
    return authenticator

def set_credentials(username, password):
    authenticator.set_credentials(username, password)

"""
def dispatch_auth(func):
    def default_auth(*args, **kw):
        method = kw.get("method", "webauth")
        return func(get_authenticator(method), *args, **kw)

    return default_auth

@dispatch_auth
def get_connection(authenticator, url):
    return authenticator.get_connection(url)

def bind(conn, service, host):
    authenticator = get_authenticator(method)
    return authenticator.bind(conn, service, host)

def get_cookie():
    return authenticator.get_cookie()

def get_headers(service, host):
    return authenticator.get_headers(service, host)
"""

