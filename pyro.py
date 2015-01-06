# saved as client.py
import Pyro4

svr=Pyro4.Proxy('PYRO:trackit-daemon@localhost:1888')  
svr._pyroHmacKey = "askgjio32904234kjsdflkjsfd09210jlkasd"
print svr.repo_create('git1','git','none','db2z07')
#print svr.trac_auth_config('apache')
#print svr.regenerate_authz_file()


svr.server_graceful()

