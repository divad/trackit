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

REPO_STATE = { 'REQUESTED': 0, 'ACTIVE': 1, 'SUSPEND_USER': 2, 'SUSPEND_ADMIN': 3, 'DELETE': 4 }
REPO_STATE_STR = { 0: 'Being created', 1: 'Active', 2: 'Suspended by repository admin', 3: 'Suspended by site administrator', 4: 'Scheduled for deletion' }

################################################################################

def get_all():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` ORDER BY `name`')
	return curd.fetchall()

################################################################################

def get_team_repos(team_id):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` WHERE `tid` = %s ORDER BY `name`',(team_id))
	repos = curd.fetchall()

	for repo in repos:
		repo['link'] = url_for('repo_view', name = repo['name'])
		repo['status'] = REPO_STATE_STR[repo['state']]

	return repos

################################################################################

@app.route('/repos')
@trackit.core.login_required
def repo_list():
	"""View handler to list all repositories"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` ORDER BY `name`')
	repos = curd.fetchall()

	for repo in repos:
		repo['link'] = url_for('repo_view', name = repo['name'])
		repo['status'] = REPO_STATE_STR[repo['state']]
		
	return render_template('repo_list.html',repos=repos,active='repos')

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


		## TEAM
		if 'repo_team' in request.form:
			repo_team = request.form['repo_team']

			if not re.search(r'[0-9]+$',repo_team):
				had_error = 1
				flash('Invalid team ID', 'alert-danger')

			if not int(repo_team) == -1:
				if not trackit.teams.exists(repo_team):
					had_error = 1
					flash('Sorry, but that team does not exist', 'alert-danger')

			## TODO check that they are allowed to create a repo in that team
		else:
			had_error = 1
			repo_team = -1
			flash("You must specify a team", 'alert-danger')

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

		## SECURITY MODE
		if 'repo_security' in request.form:
			repo_security = request.form['repo_security']

			if not str(repo_security) in ['0','1','2']:
				had_error = 1
				flash('Invalid repository security mode. Valid values are: 0 (private), 1 (domain) or 2 (public)', 'alert-danger')
		else:
			had_error = 1
			repo_security = 0
			flash("You must specify a repository security mode", 'alert-danger')

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
				repo_team=repo_team,
				repo_src_type=repo_src_type,
				repo_web_type=repo_web_type,
				repo_security=repo_security,
				teams=teams,
			)
			
		# CREATE THE REPOSITORY
		cur.execute('''INSERT INTO `repos` 
		(`name`, `desc`, `tid`, `src_type`, `web_type`, `security`, `state`) 
		VALUES (%s, %s, %s, %s, %s, %s, %s)''', (repo_name, repo_desc, repo_team, repo_src_type, repo_web_type, repo_security, REPO_STATE['REQUESTED']))

		# Commit changes to the database
		g.db.commit()

		# Notify that we've succeeded
		flash('Repository successfully created', 'alert-success')

		# redirect to server list
		return redirect(url_for('repo_view',name=repo_name))

################################################################################

def get(value,selector='id'):
	""" Return a repo from the DB. Returns None when the repo doesn't exist"""
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `repos` WHERE `' + selector + '` = %s', (value))
	repo = curd.fetchone()

	if repo is not None:
		repo['link'] = url_for('repo_view', name = repo['name'])
		repo['status'] = REPO_STATE_STR[repo['state']]

	return repo

################################################################################

def get_perms(repoid):
	""" Return all the permissions for a specific repo"""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `rules` WHERE `rid` = %s', (repoid))
	rules = curd.fetchall()

	return rules

################################################################################

@app.route('/repo/<name>/', methods=['GET','POST'])
@trackit.core.login_required
def repo_view(name):
	"""View handler to manage a repo"""

	## Get the repo
	repo    = get(name,selector='name')

	## No such team found!
	if repo == None:
		abort(404)

	## Get permissions list for the repo
	perms = trackit.repos.get_perms(repo['id'])
		
	## TODO Permissions checking
	#team_admin = trackit.teams.is_admin(team['id'])

	## get the team if any
	team = None
	if repo['tid'] != -1:
		team = trackit.teams.get(repo['tid'])
	
	## GET (view) requests
	if request.method == 'GET':
		return render_template('repo.html',repo=repo,team=team,repo_admin=True,perms=perms,active='repos')

	## POST (change settings or delete or add member or delete member)
	else:
		cur = g.db.cursor()	
		
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
						cur.execute('UPDATE `repos` SET `desc` = %s, `security` = %s, `src_notify_email` = %s, `autoversion` = %s WHERE `id` = %s', (repo_desc, repo_security, src_notify_email,repo_autoversion,repo['id']))
						g.db.commit()
						flash('Repository settings updated successfully', 'alert-success')
						
					return redirect(url_for('repo_view',name=repo['name']))

				else:
					abort(501)

			elif action == 'delete':
				cur.execute('UPDATE `repos` SET `state` = %s WHERE `id` = %s', (REPO_STATE['DELETE'], repo['id']))
				g.db.commit()
				flash('Repository marked for deletion', 'alert-success')
				return redirect(url_for('repo_view',name=repo['name']))
				
			elif action == 'addperm':
				pass
			elif action == 'setperm':
				pass
			elif action == 'rmperm':
				pass
			else:
				abort(400)
			
		else:
			abort(400)
