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

    def login(self):
        self.authenticated = True
        return True

    def logout(self):
        pass

    def ensure_login(self):
        if not self.authenticated:
            self.login()

    def bind(self, conn, service="HTTP", host=""):
        if not host:
            host = conn.host
        def endheaders(_self, body=None):
            self.ensure_login()

            for header, value in self.get_headers(service, host).items():
                _self.putheader(header, value)

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

        result, context = k.authGSSClientInit("%s@%s" % (service, host),
                                              k.GSS_C_DELEG_FLAG)
        if result < 1:
            raise errors.AuthenticationError("authGSSClientInit returned result %d" % result)

        result = k.authGSSClientStep(context, "WWW-Authenticate")
        if result < 0:
            raise errors.AuthenticationError("authGSSClientStep returned result %d" % result)

        return { "Authorization" : "Negotiate %s" % k.authGSSClientResponse(context) }


class WebAuthAuthenticator(NullAuthenticator):
    LOGIN_HOST = "my.agorabox.org"

    def __init__(self, username="", password="", cookie=""):
        NullAuthenticator.__init__(self)
        self.username = username
        self.password = password
        self.cookie = Cookie.SimpleCookie(cookie)
        self.authenticated = cookie != ""

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

            if 'webauth_at' in self.cookie:
                return True

        else:
            raise errors.InvalidAuthenticationMethod(method=self.__class__.__name__)

        return False

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

def get_authenticator(method, *args, **kw):
    if method == "webauth":
        authenticator = WebAuthAuthenticator(cookie=kw.get('cookie'))
    elif method == "spnego":
        authenticator = SPNEGOAuthenticator()
    else:
        raise Exception('Invalid authentication method %s' % method)
    return authenticator

def set_credentials(username, password):
    authenticator.set_credentials(username, password)
