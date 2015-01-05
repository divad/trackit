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
import re
import MySQLdb as mysql
import math
import Pyro4

REPO_STATE       = { 'REQUESTED': 0, 'ACTIVE': 1, 'SUSPEND': 2, 'DELETE': 3 }
REPO_STATE_STR   = { 0: 'Being created', 1: 'Active', 2: 'Suspended', 3: 'Scheduled for deletion' }
REPO_SEC         = { 'PRIVATE': 0, 'INTERNAL': 1, 'PUBLIC': 2 }
REPO_SEC_STR     = { 0: 'Private', 1: 'University only', 2: 'Public' }
REPO_WEB_SEC     = { 'PRIVATE': 0, 'PUBLIC': 1 }
REPO_WEB_SEC_STR = { 0: 'Private', 1: 'Public' }

################################################################################

def get_all():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` ORDER BY `name`')
	return curd.fetchall()

################################################################################

def get_user_repos():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("""
	SELECT * FROM `repos` WHERE `id` IN 
		(SELECT `rid` FROM `rules` WHERE `name` = %s AND `source` = 'internal') 
	OR `id` IN
		(SELECT `rid` FROM `rules` WHERE `source` = 'team' AND `name` IN
			(SELECT `name` FROM `teams` WHERE `id` IN 
				(SELECT `tid` FROM `team_members` WHERE `domain` = 'internal' AND `username` = %s)
			)
		)
	""",(session['username'],session['username']))
	return curd.fetchall()
	
################################################################################

def get_team_repos(team_name):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute("SELECT * FROM `repos` WHERE `state` = %s AND `id` IN (SELECT `rid` FROM `rules` WHERE `source` = 'team' AND `name` = %s)",(REPO_STATE['ACTIVE'],team_name))
	repos = curd.fetchall()

	for repo in repos:
		repo['link'] = url_for('repo_view', name = repo['name'])
		repo['status'] = REPO_STATE_STR[repo['state']]
		repo['visibility'] = REPO_SEC_STR[repo['security']]

	return repos

################################################################################
	
def repo_list_handler(repos,title,page,function):

	## Add links / status text
	for repo in repos:
		repo['link'] = url_for('repo_view', name = repo['name'])
		repo['status'] = REPO_STATE_STR[repo['state']]
		repo['visibility'] = REPO_SEC_STR[repo['security']]
		
	## Pagination
	itemsPerPage = 12
		
	repos_length = len(repos)
	number_of_pages = int(math.ceil(float(repos_length) / float(itemsPerPage)))
	
	pages = False
	if number_of_pages > 1:
		pages = True
		
		if page == None:
			page = 1
		else:
			try:
				page = int(page)
			except ValueError as e:
				flash('Invalid page ID','alert-danger')
				page = 1
			
		if page > number_of_pages:
			flash('That page does not exist','alert-danger')
			page = 1
			
		## slice the repos!
		start = (page -1) * itemsPerPage
		end = start + itemsPerPage
		repos = repos[start:end]
		
	return render_template('repo_list.html',repos=repos,active='repos',title=title,pages=pages,number_of_pages=number_of_pages,page=page,function=function)	

################################################################################

@app.route('/repos')
@app.route('/repos/<page>')
@trackit.core.login_required
def repo_list(page=None):
	"""View handler to list all repositories"""

	return repo_list_handler(get_user_repos(),"My Repositories",page,'repo_list')

################################################################################

@app.route('/public')
@app.route('/public/<page>')
def repo_list_all(page=None):
	"""View handler to list all repositories"""
	
	if session.get('logged_in',False) is False:
		curd = g.db.cursor(mysql.cursors.DictCursor)
		curd.execute('SELECT * FROM `repos` WHERE `security` = %s AND `state` = %s ORDER BY `name`',(REPO_SEC['PUBLIC'],REPO_STATE['ACTIVE']))
		repos = curd.fetchall()

		return repo_list_handler(repos,"Public Projects",page,'repo_list_all')
	else:
		curd = g.db.cursor(mysql.cursors.DictCursor)
		curd.execute('SELECT * FROM `repos` WHERE `security` >= %s AND `state` = %s ORDER BY `name`',(REPO_SEC['INTERNAL'],REPO_STATE['ACTIVE']))
		repos = curd.fetchall()

		return repo_list_handler(repos,"All Repositories",page,'repo_list_all')
		
################################################################################

@app.route('/god/repos')
@trackit.core.login_required
@trackit.core.admin_required
def repo_list_admin():
	"""View handler to list all repositories"""
	
	repos = get_all()
	
	## Add links / status text
	for repo in repos:
		repo['link']       = url_for('repo_view', name = repo['name'])
		repo['status']     = REPO_STATE_STR[repo['state']]
		repo['visibility'] = REPO_SEC_STR[repo['security']]

	return render_template('god_repo_list.html',repos=repos,active='god')	

################################################################################
	
def repo_is_valid_name(repo_name):
	if re.search(r'^[a-zA-Z0-9_\-]{3,50}$', repo_name):
		return True
	else:
		return False

################################################################################

@app.route('/repos/check', methods=['POST'])
def repo_check_exists():
	"""Returns a JSON response to user agents to check if a repository already exists. Used for AJAX client-side checking before form submit"""

	if 'repo_name' in request.form:
		repo_name = request.form['repo_name']
	else:
		return jsonify(success=0)

	if not repo_is_valid_name(repo_name):
		return jsonify(success=1, result='invalid')

	# Check whether the repo exists
	cur = g.db.cursor()
	cur.execute('SELECT 1 FROM `repos` WHERE `name` = %s;', (repo_name))
	if cur.fetchone() is not None:
		# Repo exists
		return jsonify(success=1, result='exists')

	return jsonify(success=1, result='valid')

################################################################################

def get(value,selector='id'):
	""" Return a repo from the DB. Returns None when the repo doesn't exist"""
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` WHERE `' + selector + '` = %s', (value))
	repo = curd.fetchone()

	if repo is not None:
		repo['link']             = url_for('repo_view', name = repo['name'])
		repo['status']           = REPO_STATE_STR[repo['state']]
		repo['visibility']       = REPO_SEC_STR[repo['security']]
		repo['web_security_str'] = REPO_WEB_SEC_STR[repo['web_security']]

	return repo

################################################################################

def get_perms(repoid):
	""" Return all the permissions for a specific repo"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `rules` WHERE `rid` = %s', (repoid))
	rules = curd.fetchall()

	return rules

	
################################################################################

def is_admin(repo_id,username=None):
	if username == None:
		username = session['username']
		
	if trackit.user.is_global_admin():
		return True
		
	cur = g.db.cursor()
	cur.execute("""SELECT 1 FROM `rules` WHERE `source` = 'internal' AND `name` = %s AND `admin` = 1 AND `rid` = %s""", (username,repo_id))
	result = cur.fetchone()
	
	if not result == None:
		return True
		
	cur.execute("""
		SELECT 1 FROM `rules` WHERE `source` = 'team' AND `admin` = 1 AND `rid` = %s AND `name` IN
			(
				SELECT `name` FROM `teams` WHERE `id` IN 
				(
					SELECT `tid` FROM `team_members` WHERE `domain` = 'internal' AND `username` = %s
				)
			)	
	""",(repo_id,session['username']))
	result = cur.fetchone()
	
	if not result == None:
		return True

	return False
	
################################################################################

def has_access(repo_id,username=None):
	if username == None:
		username = session['username']
		
	if trackit.user.is_global_admin():
		return True
		
	cur = g.db.cursor()
	cur.execute("""SELECT 1 FROM `rules` WHERE `source` = 'internal' AND `name` = %s AND `rid` = %s""", (username,repo_id))
	result = cur.fetchone()
	
	if not result == None:
		return True
		
	cur.execute("""
		SELECT 1 FROM `rules` WHERE `source` = 'team' AND `rid` = %s AND `name` IN
			(
				SELECT `name` FROM `teams` WHERE `id` IN 
				(
					SELECT `tid` FROM `team_members` WHERE `domain` = 'internal' AND `username` = %s
				)
			)	
	""",(repo_id,session['username']))
	result = cur.fetchone()
	
	if not result == None:
		return True

	return False
		
################################################################################

@app.route('/repos/create', methods=['GET','POST'])
@trackit.core.login_required
def repo_create():
	"""View function to create a new repository"""	
	
	if request.method == 'GET':
		teams = trackit.teams.get_user_teams(session['username'])
		return render_template('repo_create.html', active='repos', teams=teams)

	elif request.method == 'POST':
		# Set a flag to determine if we'd had an error
		had_error = 0

		# NAME
		if 'repo_name' in request.form:
			repo_name = request.form['repo_name']

			if not re.search(r'^[a-zA-Z0-9_\-]{3,50}$',repo_name):
				had_error = 1
				flash('Invalid repository name. Allowed characters are a-z, 0-9, underscore and hyphen', 'alert-danger')
		else:
			had_error = 1
			repo_name = ''
			flash("You must specify a repository name", 'alert-danger')

		## DESCRIPTION
		if 'repo_desc' in request.form:
			repo_desc = request.form['repo_desc']

			if not re.search(r'^[a-zA-Z0-9_\-\,\.\(\)\s\+]{3,255}$',repo_desc):
				had_error = 1
				flash('Invalid repository description. Allowed characters are a-z, 0-9, comma, full stop, backslash, whitespace, plus, underscore and hyphen', 'alert-danger')
		else:
			had_error = 1
			repo_desc = ''
			flash("You must specify a repository description", 'alert-danger')		

		## SOURCE TYPE
		if 'repo_src_type' in request.form:
			repo_src_type = request.form['repo_src_type']

			if not repo_src_type in ['git','svn','hg','none']:
				had_error = 1
				flash('Invalid repository source type. Valid values are: git, svn, hg or none.', 'alert-danger')
		else:
			had_error = 1
			repo_src_type = 'git'
			flash("You must specify a repository source type", 'alert-danger')

		## WEB TYPE
		if 'repo_web_type' in request.form:
			repo_web_type = request.form['repo_web_type']

			if not repo_web_type in ['trac','redmine','none']:
				had_error = 1
				flash('Invalid repository web tool type. Valid values are: trac, redmine or none.', 'alert-danger')
		else:
			had_error = 1
			repo_src_type = 'trac'
			flash("You must specify a repository web tool type", 'alert-danger')

		# Ensure that the repo name doesn't already exist
		cur = g.db.cursor()
		cur.execute('SELECT 1 FROM `repos` WHERE `name` = %s;', (repo_name))
		if cur.fetchone() is not None:
			had_error = 1
			flash('Error: I\'m sorry, but a repository with that name already exists. Please choose another name.', 'alert-danger')

		# If we had an error, just render the form again with details already there so they can be changed
		if had_error == 1:
			teams = trackit.teams.get_user_teams(session['username'])
			return render_template('repo_create.html',
				active='servers',
				repo_name=repo_name,
				repo_desc=repo_desc,
				repo_src_type=repo_src_type,
				repo_web_type=repo_web_type,
				teams=teams,
			)
		
		# CREATE THE REPOSITORY
		cur.execute('''INSERT INTO `repos` 
		(`name`, `desc`, `tid`, `src_type`, `web_type`, `security`, `state`) 
		VALUES (%s, %s, %s, %s, %s, %s, %s)''', (repo_name, repo_desc, '-1', repo_src_type, repo_web_type, REPO_SEC['PRIVATE'], REPO_STATE['REQUESTED']))
		
		# Commit changes to the database
		g.db.commit()
		
		# Get the new ID
		rid = cur.lastrowid

		# CREATE THE DEFAULT ADMIN RULE
		cur.execute('''INSERT INTO `rules` 
		(`rid`, `source`, `name`, `src`, `web`, `admin`) 
		VALUES (%s, %s, %s, %s, %s, %s)''', (rid, 'internal', session['username'], 2, 1, 1))

		g.db.commit()

		# Ask trackitd to create the repository 
		trackitd = trackit.core.trackitd_connect()
		result, error_string = trackitd.repo_create(repo_name,repo_src_type,repo_web_type,session['username'])
		
		if result == False:
			flash('Repository creation failed: ' + str(error_string), 'alert-danger')
			return redirect(url_for('repo_view',name=repo_name))
		
		## Mark repo as activated 
		cur.execute("UPDATE `repos` SET `state` = %s WHERE `id` = %s",(REPO_STATE['ACTIVE'],rid))
		g.db.commit()	
		
		# Notify that we've succeeded
		flash('Repository successfully created', 'alert-success')

		# redirect to server list
		return redirect(url_for('repo_view',name=repo_name))

################################################################################

@app.route('/repo/<name>/', methods=['GET','POST'])
def repo_view(name):
	"""View handler to manage a repo"""

	## Get the repo
	repo    = get(name,selector='name')

	## No such repo found!
	if repo == None:
		abort(404)
		
	## If the user is not logged in show a public page, IF its public 
	if session.get('logged_in',False) is False:
		if repo['security'] == REPO_SEC['PUBLIC']:
			return render_template('public_repo.html',repo=repo,active='repos')
		else:
			abort(403)

	## Get permissions list for the repo
	perms = trackit.repos.get_perms(repo['id'])
		
	## Permissions checking
	repo_admin = trackit.repos.is_admin(repo['id'])
	repo_member = trackit.repos.has_access(repo['id'])
		
	## Check visibility
	if repo['security'] == 0:
		if not repo_member:
			flash('You do not have permission to view that repository','alert-danger')
			return(redirect(url_for('repo_list')))
	
	## GET (view) requests
	if request.method == 'GET':
	
		## Get all teams :/ fix this later via AJAX call!
		teams = trackit.teams.get_all_teams()
	
		return render_template('repo.html',teams=teams,repo=repo,repo_admin=repo_admin,repo_member=repo_member,perms=perms,active='repos',global_admin=trackit.user.is_global_admin())

	## POST (change settings or delete or add member or delete member)
	else:
		cur = g.db.cursor()
		trackitd = trackit.core.trackitd_connect()
		
		if 'action' in request.form:
			action = request.form['action']
			
			if action == 'settings':
			
				had_error = 0
			
				if 'repo_desc' in request.form:
					repo_desc = request.form['repo_desc']

					if not re.search(r'^[a-zA-Z0-9_\-\,\.\(\)\s\+]{3,255}$',repo_desc):
						had_error = 1
						flash('Invalid repository description. Allowed characters are a-z, 0-9, comma, full stop, backslash, whitespace, plus, underscore and hyphen', 'alert-danger')
				else:
					had_error = 1
					flash("You must specify a repository description", 'alert-danger')
					
				if 'repo_security' in request.form:
					repo_security = request.form['repo_security']

					if not str(repo_security) in ['0','1','2']:
						had_error = 1
						flash('Invalid repository security mode. Valid values are: 0 (private), 1 (domain) or 2 (public)', 'alert-danger')
				else:
					had_error = 1
					flash("You must specify a repository security mode", 'alert-danger')
				
				
				if repo['web_type'] == 'trac':
				
					if 'repo_web_security' in request.form:
						repo_web_security = request.form['repo_web_security']

						if not str(repo_web_security) in ['0','1']:
							had_error = 1
							flash('Invalid repository web security mode. Valid values are: 0 (private), 1 (public)', 'alert-danger')
					else:
						had_error = 1
						flash("You must specify a repository web security mode", 'alert-danger')
				else:
					repo_web_security = repo['web_security']
					
				if repo['src_type'] == 'svn':
				
					if 'src_notify_email' in request.form:
						src_notify_email = request.form['src_notify_email']
						
						if len(src_notify_email) > 0:
						
							if not re.search(r'[-0-9a-zA-Z.+_]+@[-0-9a-zA-Z.+_]+\.[a-zA-Z]{2,10}',src_notify_email):
								had_error = 1
								flash('Invalid notification e-mail address', 'alert-danger')

					else:
						had_error = 1
						flash("You must specify a repository security mode", 'alert-danger')
						
					if 'repo_autoversion' in request.form:
						repo_autoversion = request.form['repo_autoversion']

						if not str(repo_autoversion) in ['0','1']:
							had_error = 1
							flash('Invalid autoversion flag. Valid values are: 0 (off) and 1 (on)', 'alert-danger')
							
							
				if not had_error:
					## First update non-trackitd-fields
					cur.execute('UPDATE `repos` SET `desc` = %s, `security` = %s WHERE `id` = %s', (repo_desc, repo_security, repo['id']))
					g.db.commit()
					
					if repo['web_type'] == 'trac':
					
						if not str(repo_web_security) == str(repo['web_security']):
							cur.execute('UPDATE `repos` SET `web_security` = %s WHERE `id` = %s', (repo_web_security, repo['id']))
							g.db.commit()
						
							result, error_string = trackitd.repo_update_web_security(repo['name'])
		
							if result == False:
								flash('Could not alter the web security mode: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))
							
					if repo['src_type'] == 'svn':
					
						if not src_notify_email == repo['src_notify_email']:
							cur.execute('UPDATE `repos` SET `src_notify_email` = %s WHERE `id` = %s', (src_notify_email, repo['id']))
							g.db.commit()
						
							result, error_string = trackitd.repo_update_src_notify_email(repo['name'],src_notify_email)
		
							if result == False:
								flash('Could not alter the svn notification e-mail: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))
					
						if not str(repo_autoversion) == str(repo['autoversion']):
							cur.execute('UPDATE `repos` SET `autoversion` = %s WHERE `id` = %s', (repo_autoversion, repo['id']))
							g.db.commit()
								
							result, error_string = trackitd.update_autoversion()
		
							if result == False:
								flash('Could not alter the svn auto versioning flag: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))

					flash('Repository settings updated successfully', 'alert-success')
					
				return redirect(url_for('repo_view',name=repo['name']))

			elif action == 'addweb':
			
				if repo['web_type'] == 'none':
				
					cur.execute('UPDATE `repos` SET `web_type` = %s WHERE `id` = %s', ("trac", repo['id']))
					g.db.commit()
					
					result, error_string = trackitd.repo_add_web(repo['name'],"trac")
		
					if result == False:
						flash('Could not not add Trac: ' + str(error_string), 'alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))
					else:
						flash('Trac has been added to this repository', 'alert-success')
						return redirect(url_for('repo_view',name=repo['name']))
						
				else:
					abort(400)

				
			elif action == 'suspend':
				if trackit.user.is_global_admin():
				
					cur.execute('UPDATE `repos` SET `state` = %s WHERE `id` = %s', (REPO_STATE['SUSPEND'], repo['id']))
					g.db.commit()
					
					result, error_string = trackitd.repo_suspend(repo['name'])
		
					if result == False:
						flash('Could not not suspend repository: ' + str(error_string), 'alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))
					else:
						flash('Repository suspended', 'alert-success')
						return redirect(url_for('repo_view',name=repo['name']))
				else:
					abort(403)
					
			elif action == 'enable':
				if trackit.user.is_global_admin():
				
					result, error_string = trackitd.repo_enable(repo['name'])
		
					if result == False:
						flash('Could not not enable repository: ' + str(error_string), 'alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))
					else:
						cur.execute('UPDATE `repos` SET `state` = %s WHERE `id` = %s', (REPO_STATE['ACTIVE'], repo['id']))
						g.db.commit()
						flash('Repository enabled', 'alert-success')
						return redirect(url_for('repo_view',name=repo['name']))
				else:
					abort(403)

			elif action == 'delete':
				cur.execute('UPDATE `repos` SET `state` = %s WHERE `id` = %s', (REPO_STATE['DELETE'], repo['id']))
				g.db.commit()
				
				result, error_string = trackitd.repo_delete(repo['name'])
	
				if result == False:
					flash('Could not not delete repository: ' + str(error_string), 'alert-danger')
					return redirect(url_for('repo_view',name=repo['name']))
				else:
					## TODO delete sql maybe
					flash('Repository deleted', 'alert-success')
					return redirect(url_for('repo_list'))
				
			elif action == 'addperm':
				had_error = 0
			
				if 'src' in request.form:
					src = request.form['src']

					if not int(src) >= 0 and int(src) <= 2:
						had_error = 1
						flash('Invalid revision control access flag', 'alert-danger')
				else:
					had_error = 1
					flash("You must specify a revision control access flag", 'alert-danger')
						
				if 'web' in request.form:
					web = request.form['web']

					if not str(web) == '1':
						had_error = 1
						flash('Invalid web project management tool access flag', 'alert-danger')	
				else:
					web = 0
					
				if 'admin' in request.form:
					admin = request.form['admin']

					if not str(admin) == '1':
						had_error = 1
						flash('Invalid admin flag', 'alert-danger')	
				else:
					admin = 0
		
				if 'source' in request.form:
					source = request.form['source']
				else:
					flash("You must specify a source type", 'alert-danger')
					had_error = 1

				if 'name' in request.form:
					name = request.form['name']
					
					if not len(name) > 0:
						had_error = 1
						flash("You must specify a name", 'alert-danger')
				else:
					flash("You must specify a name", 'alert-danger')
					had_error = 1
					
				if had_error:
					return redirect(url_for('repo_view',name=repo['name']))
				else:

					if source == 'internal':
						## university internal account
						## check its a valid username
						user_object = trackit.user.get(name)
					
						if user_object == None:
							flash('That username was not found','alert-danger')
							return redirect(url_for('repo_view',name=repo['name']))
						
					elif source == 'team':
						## trackit team
						## check its a valid team
						team_object = trackit.teams.get(name,'name')
						
						if team_object == None:
							flash('That team was not found','alert-danger')
							return redirect(url_for('repo_view',name=repo['name']))					
						
					elif source == 'adgroup':
						if not trackit.core.ldap_check_group(name):
							flash('I looked in Active Directory but could not find that group :(','alert-danger')
							return redirect(url_for('repo_view',name=repo['name']))	
						else:
							admin = 0
							src = 0
						
					else:
						flash('Invalid source','alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))	
												
					cur.execute('SELECT * FROM `rules` WHERE `source` = %s AND `name` = %s AND `rid` = %s', (source,name,repo['id']))
					result = cur.fetchone()
					if not result == None: 
						flash('A permission rule already exists for that name','alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))	
						
					## now add to sql
					cur.execute('''INSERT INTO `rules` 
					(`rid`, `source`, `name`, `src`, `web`, `admin`) 
					VALUES (%s, %s, %s, %s, %s, %s)''', (repo['id'], source, name, src, web, admin))

					# Commit changes to the database
					g.db.commit()
					
					## Now get the rules to rebuilt in trackitd
					
					result, error_string = trackitd.repo_update_rules(repo['name'])
		
					if result == False:
						flash('An internal error occured when rebuilding permission rules: ' + str(error_string), 'alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))
					
					if str(admin) == '1':
						if source == 'internal':
							result, error_string = trackitd.repo_add_admin(repo['name'],name)
							
							if result == False:
								flash('An internal error occured when setting permission rules: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))

					# Notify that we've succeeded
					flash('Permission rule added', 'alert-success')

					# redirect to server list
					return redirect(url_for('repo_view',name=repo['name']))
				
			elif action == 'editperm':

				## Load the rule ID from the form
				rid = request.form['rid']
				if not re.search(r'^[0-9]+$',rid):
					flash('Invalid rule ID', 'alert-danger')
					return(redirect(url_for('repo_view',name=repo['name'])))
					
				## Check that rule exists
				curd = g.db.cursor(mysql.cursors.DictCursor)
				curd.execute('SELECT * FROM `rules` WHERE `id` = %s;', (rid))
				existing_rule = curd.fetchone()
				if existing_rule is None:
					flash('That rule has was not found', 'alert-danger')
					return(redirect(url_for('repo_view',name=repo['name'])))			
			
				## Check if this is an edit or a delete of the rule
				submit = request.form['submit']
				if submit == 'Remove':
				
					## Remove web/trac admin rights if needed
					if str(existing_rule['admin']) == '1':
						if existing_rule['source'] == 'internal':
							result, error_string = trackitd.repo_remove_admin(repo['name'],existing_rule['name'])
							
							if result == False:
								flash('An internal error occured when deleting permission rules: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))
								
					## Update SQL
					cur.execute('DELETE FROM `rules` WHERE id = %s', (rid))
					g.db.commit()
					
					## Rebuild rules
					result, error_string = trackitd.repo_update_rules(repo['name'])
		
					if result == False:
						flash('An internal error occured when rebuilding permission rules: ' + str(error_string), 'alert-danger')
						return redirect(url_for('repo_view',name=repo['name']))
					
					flash('Removed permission rule', 'alert-success')
					return(redirect(url_for('repo_view',name=repo['name'])))	
					
				elif submit == 'Save':
			
					had_error = 0
				
					if 'src' in request.form:
						src = request.form['src']

						if not int(src) >= 0 and int(src) <= 2:
							had_error = 1
							flash('Invalid revision control access flag', 'alert-danger')
					else:
						had_error = 1
						flash("You must specify a revision control access flag", 'alert-danger')
							
					if 'web' in request.form:
						web = request.form['web']

						if not str(web) == '1':
							had_error = 1
							flash('Invalid web project management tool access flag', 'alert-danger')	
					else:
						web = 0
						
					if 'admin' in request.form:
						admin = request.form['admin']

						if not str(admin) == '1':
							had_error = 1
							flash('Invalid admin flag', 'alert-danger')	
					else:
						admin = 0
						
					if existing_rule['source'] == 'adgroup':
						admin = 0
						src = 0
					
					if not had_error:
					
						## Change web/trac admin rights if needed
						if str(existing_rule['admin']) == '1' and str(admin) == '0' and existing_rule['source'] == 'internal':
							result, error_string = trackitd.repo_remove_admin(repo['name'],existing_rule['name'])
							
							if result == False:
								flash('An internal error occured when deleting permission rules: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))
								
						elif str(existing_rule['admin']) == '0' and str(admin) == '1' and existing_rule['source'] == 'internal':
							result, error_string = trackitd.repo_add_admin(repo['name'],existing_rule['name'])
							
							if result == False:
								flash('An internal error occured when adding permission rules: ' + str(error_string), 'alert-danger')
								return redirect(url_for('repo_view',name=repo['name']))	
					
						## Now update SQL
						cur.execute('UPDATE `rules` SET `src` = %s, `web` = %s, `admin` = %s WHERE id = %s', (src, web, admin, rid))
						g.db.commit()
						
						## Now call trackitd to rebuild rules
						result, error_string = trackitd.repo_update_rules(repo['name'])
			
						if result == False:
							flash('An internal error occured when rebuilding permission rules: ' + str(error_string), 'alert-danger')
							return redirect(url_for('repo_view',name=repo['name']))
						
						flash('Permission rule updated', 'alert-success')
						
					return(redirect(url_for('repo_view',name=repo['name'])))

			else:
				abort(400)
			
		else:
			abort(400)
