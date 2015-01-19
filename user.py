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

from trackit import app
import trackit.core
import trackit.errors
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, jsonify
import kerberos
import pwd
import grp
import pwd
import os
import binascii
import MySQLdb as mysql

################################################################################
#### LOGIN

@app.route('/login', methods=['GET','POST'])
def login():

	if request.method == 'GET':
		return redirect(url_for('default'))
	else:

		try:
			## Check password with kerberos
			kerberos.checkPassword(request.form['username'], request.form['password'], app.config['KRB5_SERVICE'], app.config['KRB5_DOMAIN'])
		except kerberos.BasicAuthError as e:
			flash('Incorrect username and/or password','alert-danger')
			return redirect(url_for('default'))
		except kerberos.KrbError as e:
			flash('Kerberos Error: ' + e.__str__(),'alert-danger')
			return redirect(url_for('default'))
		except kerberos.GSSError as e:
			flash('GSS Error: ' + e.__str__(),'alert-danger')
			return redirect(url_for('default'))
		except Exception as e:
			trackit.errors.fatal(e)

		## Check this user is allowed to logon
		result = trackit.core.ldap_check_user_access(request.form['username'])

		## Check they can logon
		if result == None:
			flash("Sorry, I couldn't find your details in Active Directory! Please contact your system administrator.","alert-danger")
			return redirect(url_for('default'))
		elif result == False:
			flash("Sorry, you are not allowed to access this service. If you believe this is in error please contact ServiceLine.","alert-danger")
			return redirect(url_for('default'))

		## Set logged in (if we got this far)
		session['logged_in'] = True
		session['username'] = request.form['username']

		## Check if the user selected "Log me out when I close the browser"
		permanent = request.form.get('sec',default="")

		## Set session as permanent or not
		if permanent == 'sec':
			session.permanent = True
		else:
			session.permanent = False

		## Log a successful login
		app.logger.info('User "' + session['username'] + '" logged in from "' + request.remote_addr + '" using ' + request.user_agent.string)
		
		if is_global_admin():
			session['admin'] = True
			flash('You are logged in as a global administrator with full privileges over all repositories and teams.','alert-warning')
		else:
			session['admin'] = False

		## determine if "next" variable is set (the URL to be sent to)
		if 'next_url' in session:
			if session['next_url'] != None:
				return redirect(session['next_url'])

		return redirect(url_for('repo_list'))
		
################################################################################

def is_global_admin(username=None):
	if username == None:
		username = session['username']
		
	## mark the user as an admin if they are in the admins group
	group = grp.getgrnam(app.config['ADMIN_GROUP'])
	if username in group.gr_mem:
		return True
	else:
		return False

################################################################################

def get(username):

	try:
		passwd = pwd.getpwnam(username)
	except KeyError as e:
		return None
		
	return passwd

################################################################################


@app.route('/user/check', methods=['POST'])
def user_check():
	"""Returns a JSON response to user agents to check if a username is valid."""

	if 'username' in request.form:
		username = request.form['username']
	else:
		app.logger.info('invalid')
		return jsonify(result='invalid')

	user_object = trackit.user.get(username)
	
	if user_object == None:
		return jsonify(result='notfound')
	else:
		return jsonify(result='exists')

################################################################################
#### LOGOUT

@app.route('/logout')
@trackit.core.login_required
def logout():
	app.logger.info('User "' + session['username'] + '" logged out from "' + request.remote_addr + '" using ' + request.user_agent.string)

	session.pop('logged_in', None)
	session.pop('username', None)

	flash('You have been logged out. Goodbye.','alert-success')

	return redirect(url_for('default'))

################################################################################
#### ALTERNATIVE PASSWORD SYSTEM

@app.route('/passwd', methods=['GET','POST'])
@trackit.core.login_required
def passwd():
	## see if there is an existing password
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `alt_passwords` WHERE `username` = %s', (session['username']))
	result = curd.fetchone()

	if not result or request.method == 'POST':
		password = regenerate_alt_password()

		if request.method == 'POST':
			flash("Your password has been changed","alert-success")
			return redirect(url_for('passwd'))
	else:
		password = result['password']
	
	return render_template('passwd.html',password=password)

def regenerate_alt_password():
	cur = g.db.cursor()
	new_password = binascii.hexlify(os.urandom(16))

	cur.execute('DELETE FROM `alt_passwords` WHERE `username` = %s', (session['username']))
	cur.execute('INSERT INTO `alt_passwords` (username,password) VALUES (%s, %s)', (session['username'],new_password))
	g.db.commit()

	trackit.core.audit_event(session['username'],'user','alt_password.regenerate',0,'Alternative password (re)generated for ' + session['username'])

	return new_password

