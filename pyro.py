# saved as client.py
import Pyro4

svr=Pyro4.Proxy('PYRO:trackit-daemon@localhost:1888')  
svr._pyroHmacKey = "changeme"
print svr.trac_auth_config('tux2')

