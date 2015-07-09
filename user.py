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
import ldap

################################################################################
#### LOGIN

@app.route('/login', methods=['GET','POST'])
def login():

	if request.method == 'GET':
		return redirect(url_for('default'))
	else:
		result = trackit.user.auth_user(request.form['username'],request.form['password'])

		if not result:
			flash('Incorrect username and/or password','alert-danger')
			return redirect(url_for('default'))

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

def auth_user(username,password):
	app.logger.debug("trackit.user.auth_user for " + username)

	if username == '':
		return False
	if password == '':
		return False

	## connect to LDAP and turn off referals
	l = ldap.initialize(app.config['LDAP_URI'])
	l.set_option(ldap.OPT_REFERRALS, 0)

	## and bind to the server with a username/password if needed in order to search for the full DN for the user who is logging in.
	try:
		if app.config['LDAP_ANON_BIND']:
			l.simple_bind_s()
		else:
			l.simple_bind_s( (app.config['LDAP_BIND_USER']), (app.config['LDAP_BIND_PW']) )
	except ldap.LDAPError as e:
		flash('Internal Error - Could not connect to LDAP directory: ' + str(e),'alert-danger')
		app.logger.error("Could not bind to LDAP: " + str(e))
		trackit.errors.fatal(e)

	app.logger.debug("trackit.user.auth_user ldap bind succeeded ")

	## Now search for the user object to bind as
	try:
		results = l.search_s(app.config['LDAP_SEARCH_BASE'], ldap.SCOPE_SUBTREE,(app.config['LDAP_USER_ATTRIBUTE']) + "=" + username)
	except ldap.LDAPError as e:
		app.logger.debug("trackit.user.auth_user no object found in ldap")
		return False

	app.logger.debug("trackit.user.auth_user ldap results found ")

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
				app.logger.debug("trackit.user.auth_user ldap attempting ldap simple bind as " + str(dn))
				lauth = ldap.initialize(app.config['LDAP_URI'])
				lauth.set_option(ldap.OPT_REFERRALS, 0)
				lauth.simple_bind_s( (dn), (password) )
				return True
			except ldap.LDAPError as e:
				## password was wrong
				app.logger.debug("trackit.core.auth_user ldap bind failed as " + str(dn))
				return False

			app.logger.debug("trackit.core.auth_user ldap bind succeeded as " + str(dn))

	## Catch all return false for LDAP auth
	return False

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
@trackit.core.db_required
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

