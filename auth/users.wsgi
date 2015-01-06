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
import kerberos

TRACKIT_CONFIG_FILE = '/data/trackit/trackit.conf'

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

def check_password(environ, username, password):
	config = load_config()

	## Try kerberos auth first of all
	syslog.openlog("trackit-auth",syslog.LOG_PID)
	syslog.syslog('check_password called')

	try:
		kerberos.checkPassword(username, password, config['KRB5_SERVICE'], config['KRB5_DOMAIN'])
		result = True
	except Exception:
		result = False

	if result:
		return True
	else:
		import MySQLdb as mysql
		db = mysql.connect(config['DB_SERV'],config['DB_USER'],config['DB_PASS'],config['DB_NAME'])
		curd = db.cursor(mysql.cursors.DictCursor)
	
		curd.execute('SELECT * FROM `alt_passwords` WHERE `username` = %s',(username))
		user = curd.fetchone()

		if user == None:
			return False
		else:
			if password == user['password']:
				return True

	return False
