#!/usr/bin/python
#
# This file is part of trackit.
#
# trackit is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# trackit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with trackit.  If not, see <http://www.gnu.org/licenses/>.

import imp
import syslog
import redis
import bcrypt #libffi-devel needed, pip install bcrypt
import ldap

TRACKIT_CONFIG_FILE = '/data/forgemgr/trackit.conf'
PASSWORD_CACHE_TTL  = 900

################################################################################

def load_config():
	d = imp.new_module('config')
	d.__file__ = TRACKIT_CONFIG_FILE
	try:
		with open(TRACKIT_CONFIG_FILE) as config_file:
			exec(compile(config_file.read(), TRACKIT_CONFIG_FILE, 'exec'), d.__dict__)
	except IOError as e:
		print 'Unable to load configuration file (%s)' % e.strerror
		sys.exit(1)
	config = {}
	for key in dir(d):
		if key.isupper():
			config[key] = getattr(d, key)
			
	return config

################################################################################

def cache_password(red, username, password):
	try:
		encrypted_password = bcrypt.hashpw(password, bcrypt.gensalt())
		red.setex('user' + ':' + username + ':cached_password', PASSWORD_CACHE_TTL, encrypted_password)
	except Exception as ex:
		syslog.openlog("trackit-auth",syslog.LOG_PID)
		syslog.syslog('check_password redis set call failed! - ' + str(ex))

################################################################################

def ldap_auth_user(config,username,password):
	syslog.openlog("trackit-auth",syslog.LOG_PID)

	## connect to LDAP and turn off referals
	l = ldap.initialize(config['LDAP_URI'])
	l.set_option(ldap.OPT_REFERRALS, 0)

	## and bind to the server with a username/password if needed in order to search for the full DN for the user who is logging in.
	try:
		if config['LDAP_ANON_BIND']:
			l.simple_bind_s()
		else:
			l.simple_bind_s( (config['LDAP_BIND_USER']), (config['LDAP_BIND_PW']) )
	except ldap.LDAPError as e:
		syslog.syslog('Failed to bind to LDAP - ' + str(ex))
		return False

	## Now search for the user object to bind as
	try:
		results = l.search_s(config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE,(config['LDAP_USER_ATTRIBUTE']) + "=" + username)
	except ldap.LDAPError as e:
		return False

	## handle the search results
	for result in results:
		dn	= result[0]
		attrs	= result[1]

		if dn == None:
			## No dn returned. Return false.
			return False

		else:
			## Found the DN. Yay! Now bind with that DN and the password the user supplied
			try:
				lauth = ldap.initialize(config['LDAP_URI'])
				lauth.set_option(ldap.OPT_REFERRALS, 0)
				lauth.simple_bind_s( (dn), (password) )
				return True
			except ldap.LDAPError as e:
				return False

			syslog.syslog('auth ldap OK for ' + str(dn))

	## Catch all return false for LDAP auth
	return False

def check_password(environ, username, password):
	syslog.openlog("trackit-auth",syslog.LOG_PID)
	syslog.syslog('auth ldap call started')

	## We use REDIS password caching for both to reduce having to hit
	## LDAP (AD) (dog slow!) or MySQL (which is slower than REDIS)

	if username == '':
		return False
	if password == '':
		return False

	syslog.syslog('auth ldap call started2')

	## Connect to REDIS
	try:
		r = redis.StrictRedis(host='localhost', port=6379, db=0)
		use_redis = True
	except Exception as ex:
		syslog.openlog("trackit-auth",syslog.LOG_PID)
		syslog.syslog('ERROR could not connect to REDIS: ' + str(ex))	
		use_redis = False

	syslog.syslog('auth ldap call started3')

	## If we can use redis
	if use_redis:
		try:		
			cached_password = r.get('user' + ':' + username + ':cached_password')
			cached_alt_password  = r.get('user' + ':' + username + ':cached_alt_password')

			## Check the cache for the main password
			if not cached_password == None:
				## redis cache exists, check password.
				if bcrypt.hashpw(password, cached_password) == cached_password:
					return True

			## Try the alt password cache instead
			if not cached_alt_password == None:
				if bcrypt.hashpw(password, cached_altpassword) == cached_alt_password:
					return True
				else:
					return False

		except Exception as ex:
			syslog.openlog("trackit-auth",syslog.LOG_PID)
			syslog.syslog('check_password redis get call failed! - ' + str(ex))

	syslog.syslog('auth ldap call started4')

	## If we got here then redis didnt' have a password cache for this user
	config = load_config()

	try:
		ldap_auth_result = ldap_auth_user(config,username,password)

		if ldap_auth_result:
			syslog.syslog('success')
			return True
		syslog.syslog('fail')
		
	except Exception as ex:
		syslog.syslog('ldap auth call resulted in an exception: ' + str(ex))
		result = False

	if result:
		if use_redis:
			cache_password(r,username,password)

		return True
	else:
		## try the alt password instead
		try:
			import MySQLdb as mysql
			db = mysql.connect(config['DB_SERV'],config['DB_USER'],config['DB_PASS'],config['DB_NAME'])
			curd = db.cursor(mysql.cursors.DictCursor)
	
			curd.execute('SELECT * FROM `alt_passwords` WHERE `username` = %s',(username))
			user = curd.fetchone()

			if user == None:
				return False
			else:
				if password == user['password']:

					if use_redis:
						cache_password(r,username,password)

					return True

		except Exception as ex:
			## something went wrong during MySQL alt password auth. the server was probably down.
			syslog.openlog("trackit-auth",syslog.LOG_PID)
			syslog.syslog('check_password mysql call failed! - ' + str(ex))
			return False			

	return False
