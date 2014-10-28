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

################################################################################

def get_all_teams():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `teams` ORDER BY `name`')
	return curd.fetchall()

################################################################################

def get_user_teams(username):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `teams` WHERE `id` IN (SELECT `tid` FROM `team_members` WHERE `username` = %s ) ORDER BY `name`',(username))
	return curd.fetchall()

################################################################################

def get_team_member(tid,username):
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `team_members` WHERE `tid` = %s AND `username` = %s', (tid,username))
	return curd.fetchone()

################################################################################

def exists(team_id):
	"""checks if a team ID corresponds to a valid team. Returns true or false"""
	cur = g.db.cursor()
	cur.execute('SELECT 1 FROM `teams` WHERE `id` = %s', (team_id))
	if cur.fetchone() is not None:
		return True
	return False

################################################################################

def get(value,selector='id'):
	""" Return a team from the DB. Returns None when the team doesn't exist"""
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `teams` WHERE `' + selector + '` = %s', (value))
	team = curd.fetchone()
	team['link'] = url_for('team_view', name = team['name'])
	return team

################################################################################

def team_is_valid_name(team_name):
	if re.search(r'^[a-zA-Z0-9_\-]{3,50}$', team_name):
		return True
	else:
		return False

################################################################################

def members(team_id):
	""" Return a list of members of a team."""

	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `team_members` WHERE `tid` = %s', (team_id))
	members = curd.fetchall()

	for member in members:
		if member['domain'] == 'internal':
		
			user_object = trackit.user.get(member['username'])
			
			if user_object == None:
				app.logger.warn('Username ' + member['username'] + 'found on team but not found on internal domain')
				member['fullname'] = 'User not found'
			else:
				member['fullname'] = user_object.pw_gecos			

		else:
			## TODO other domain support (v3.0)
			member['fullname'] = 'N/A'

	return members
	
################################################################################

def is_admin(team_id,username=None):
	if username == None:
		username = session['username']
		
	if trackit.user.is_global_admin():
		return True
		
	cur = g.db.cursor()
	cur.execute('SELECT 1 FROM `team_members` WHERE `tid` = %s AND `username` = %s AND `admin` = 1', (team_id,username))
	result = cur.fetchone()
	
	if result == None:
		return False
	else:
		return True

################################################################################

@app.route('/team/<name>/', methods=['GET','POST'])
@trackit.core.login_required
def team_view(name):
	"""View handler to show a team and the repositories in the team"""

	## Get the team
	team    = trackit.teams.get(name,selector='name')

	## No such team found!
	if team == None:
		abort(404)
		
	## Permissions checking
	team_admin = trackit.teams.is_admin(team['id'])
	
	## GET (view) requests
	if request.method == 'GET':

		repos   = trackit.repos.get_team_repos(team['id'])
		members = trackit.teams.members(team['id'])

		return render_template('team.html',team=team,repos=repos,members=members,team_admin=team_admin,active='teams')

	## POST (change settings or delete or add member or delete member)
	else:
		cur = g.db.cursor()
		
		if not team_admin:
			flash('You must be a team administrator to alter this team','alert-danger')
			abort(403)

		if 'action' in request.form:
			action = request.form['action']
			
			## Delete the team
			if action == 'delete':
			
				## TODO why isn't this on delete cascade in MySQL???
				cur.execute('DELETE FROM `team_members` WHERE `tid` = %s', (team['id']))
				cur.execute('DELETE FROM `teams` WHERE `id` = %s', (team['id']))
				g.db.commit()
				flash('Team successfully deleted', 'alert-success')
				return(redirect(url_for('team_list_mine')))
			
			## Add a member to the team	
			if action == 'add':
				if 'username' in request.form and 'admin' in request.form:
					username = request.form['username']
					admin    = request.form['admin']
					
					## 'validate' the admin flag
					if int(admin) != 1:
						admin = 0
					
					user_object = trackit.user.get(username)
					
					if user_object == None:
						flash('That username was not found','alert-danger')
					else:	
						member = get_team_member(team['id'],username)
						if member == None:
							cur.execute('INSERT INTO `team_members` (tid,username,admin) VALUES (%s, %s,%s)', (team['id'],username,admin))
							g.db.commit()
							flash('Team member added', 'alert-success')
						else:
							flash('That person is already a team member','alert-danger')
					
					return(redirect(url_for('team_view',name=team['name'])))	
				else:
					flash('You must supply a username and an admin flag to add a new team member')
					return(redirect(url_for('team_view',name=team['name'])))	
					
			## Save settings
			elif action == 'save':
				if 'team_desc' in request.form:
					team_desc = request.form['team_desc']

					if not re.search(r'^[a-zA-Z0-9_\-\,\.\(\)\s\+]{3,255}$',team_desc):
						flash('Invalid team description. Allowed characters are a-z, 0-9, comma, full stop, backslash, whitespace, plus, underscore and hyphen', 'alert-danger')
						return(redirect(url_for('team_view',name=team['name'])))

					cur.execute('UPDATE `teams` SET `desc` = %s WHERE `id` = %s', (team_desc,team['id']))
					g.db.commit()
					flash('Team settings updated successfully', 'alert-success')
					return(redirect(url_for('team_view',name=team['name'])))
					
				else:
					flash("You must specify a team description", 'alert-danger')	
					return(redirect(url_for('team_view',name=team['name'])))

			elif action == 'member':
				if 'username' in request.form and 'admin' in request.form:
					username = request.form['username']
					admin    = request.form['admin']
					submit   = request.form['submit']
					
					## 'validate' the admin flag
					if int(admin) != 1:
						admin = 0
					
					user_object = trackit.user.get(username)
					
					if user_object == None:
						flash('That username was not found','alert-danger')
					else:
						member = get_team_member(team['id'],username)
						if member == None:
							flash('That person is not a member of the team','alert-danger')
						else:
							if submit == 'Remove':
								cur.execute('DELETE FROM `team_members` WHERE tid = %s AND username = %s', (team['id'],username))
								g.db.commit()
								flash('Removed team member', 'alert-success')
							elif submit == 'Save':
								cur.execute('UPDATE `team_members` SET `admin` = %s WHERE tid = %s AND username = %s', (admin, team['id'],username))
								g.db.commit()
								flash('Team member details saved', 'alert-success')
							else:
								flash('Unknown action','alert-danger')
					
					return(redirect(url_for('team_view',name=team['name'])))	
				else:
					flash('You must supply a username and an admin flag to add a new team member')
					return(redirect(url_for('team_view',name=team['name'])))
					
			else:
				abort(400)
			
		else:
			flash("You must specify an action!", 'alert-danger')	
			return(redirect(url_for('team_view',name=team['name'])))
			
################################################################################

def team_list_handler(teams,template,page,function):

	for team in teams:
		team['link'] = url_for('team_view', name = team['name'])

	## Pagination
	itemsPerPage = 8
		
	teams_length = len(teams)
	number_of_pages = int(math.ceil(float(teams_length) / float(itemsPerPage)))
	
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
		teams = teams[start:end]
		
	return render_template(template,teams=teams,active='teams',pages=pages,number_of_pages=number_of_pages,page=page,function=function)
		
################################################################################

@app.route('/teams')
@app.route('/teams/<page>')
@trackit.core.login_required
def team_list_all(page=None):
	"""View handler to list all teams"""
	return team_list_handler(get_all_teams(),'team_list_all.html',page,'team_list_all')

################################################################################

@app.route('/myteams')
@app.route('/myteams/<page>')
@trackit.core.login_required
def team_list_mine(page=None):
	"""View handler to list all my teams"""
	return team_list_handler(get_user_teams(session['username']),'team_list_mine.html',page,'team_list_mine')
		

################################################################################

@app.route('/teams/check', methods=['POST'])
def team_check():
	"""Returns a JSON response to user agents to check if a team already exists. Used for AJAX client-side checking before form submit"""

	if 'team_name' in request.form:
		team_name = request.form['team_name']
	else:
		return jsonify(success=0)

	if not team_is_valid_name(team_name):
		return jsonify(success=1, result='invalid')

	# Check whether the team exists
	cur = g.db.cursor()
	cur.execute('SELECT 1 FROM `teams` WHERE `name` = %s;', (team_name))
	if cur.fetchone() is not None:
		# team exists
		return jsonify(success=1, result='exists')

	return jsonify(success=1, result='valid')

################################################################################
	
@app.route('/teams/create', methods=['GET','POST'])
@trackit.core.login_required
def team_create():
	"""View function to create a new team"""	
	
	if request.method == 'GET':
		return render_template('team_create.html', active='teams')

	elif request.method == 'POST':
		# Set a flag to determine if we'd had an error
		had_error = 0

		# NAME
		if 'team_name' in request.form:
			team_name = request.form['team_name']

			if not re.search(r'^[a-zA-Z0-9_\-]{3,50}$',team_name):
				had_error = 1
				flash('Invalid team name. Allowed characters are a-z, 0-9, underscore and hyphen', 'alert-danger')
		else:
			had_error = 1
			team_name = ''
			flash("You must specify a team name", 'alert-danger')

		## DESCRIPTION
		if 'team_desc' in request.form:
			team_desc = request.form['team_desc']

			if not re.search(r'^[a-zA-Z0-9_\-\,\.\(\)\s\+]{3,255}$',team_desc):
				had_error = 1
				flash('Invalid team description. Allowed characters are a-z, 0-9, comma, full stop, backslash, whitespace, plus, underscore and hyphen', 'alert-danger')
		else:
			had_error = 1
			team_desc = ''
			flash("You must specify a team description", 'alert-danger')		

		# Ensure that the team name doesn't already exist
		cur = g.db.cursor()
		cur.execute('SELECT 1 FROM `teams` WHERE `name` = %s;', (team_name))
		if cur.fetchone() is not None:
			had_error = 1
			flash('Error: I\'m sorry, but a team with that name already exists. Please choose another name.', 'alert-danger')

		# If we had an error, just render the form again with details already there so they can be changed
		if had_error == 1:
			return render_template('team_create.html',
				active='servers',
				team_name=team_name,
				team_desc=team_desc,
			)
			
		# CREATE THE team
		cur.execute('''INSERT INTO `teams` 
		(`name`, `desc`) 
		VALUES (%s, %s)''', (team_name, team_desc))

		# Commit changes to the database
		g.db.commit()

		## Last insert ID
		team_id = cur.lastrowid

		## add a team member to manage the team!
		cur.execute('INSERT INTO `team_members` (tid,username,admin) VALUES (%s, %s,%s)', (team_id,session['username'],1))
		g.db.commit()

		# Notify that we've succeeded
		flash('Team created successfully', 'alert-success')

		## Show the new team
		return redirect(url_for('team_view', name=team_name))
