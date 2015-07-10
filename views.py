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
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
import MySQLdb as mysql

################################################################################
#### HOME PAGE

@app.route('/')
def default():
	if 'username' in session:
		return redirect(url_for('repo_list'))
	else:
		next = request.args.get('next',default=None)
		return render_template('default.html', next=next)

################################################################################
#### ABOUT 

@app.route('/about')
@trackit.core.login_required
def about():
	return render_template('about.html', active='help')

################################################################################
#### Suspended page

@app.route('/suspended')
def suspended():
	return render_template('suspended.html')

################################################################################
#### God audit

@app.route('/admin/audit')
@trackit.core.login_required
@trackit.core.admin_required
@trackit.core.db_required
def audit():
	curd = g.db.cursor(mysql.cursors.DictCursor)
	curd.execute('SELECT * FROM `audit` ORDER BY `utime` DESC')
	log = curd.fetchall()

	for entry in log:
		entry['when'] = trackit.core.ut_to_string(entry['utime'])

	return render_template('audit.html',log=log,active='god')

################################################################################
#### God settings viewer

@app.route('/admin/settings')
@trackit.core.login_required
@trackit.core.admin_required
def settings():
	return render_template('god_settings.html', active='god')

################################################################################
#### Settings poll url for monitoring

@app.route('/status')
def system_status():
	status = trackit.core.get_system_status()
	if status:
		return "OK"
	else:
		return "ERR"

################################################################################
#### God admin page

@app.route('/admin',methods=['GET','POST'])
@trackit.core.login_required
@trackit.core.admin_required
def admin():
	if request.method == 'GET':
		status = trackit.core.get_system_status()

		if not status:
			errlog = trackit.core.get_system_errlog()
		else:
			errlog = ""

		if g.db:
			## count repos and teams
			curd = g.db.cursor(mysql.cursors.DictCursor)
			curd.execute('SELECT COUNT(*) AS `total` FROM `repos`')
			res = curd.fetchone()
			repo_count = int(res['total'])
			curd.execute('SELECT COUNT(*) AS `total` FROM `teams`')
			res = curd.fetchone()
			team_count = int(res['total'])

			## Get total size on disk
			curd.execute('SELECT SUM(total_size) AS `total` FROM `repo_stats`')
			res = curd.fetchone()
			total_size = res['total']
		else:
			repo_count = 0
			team_count = 0
			total_size = 0

		return render_template('admin.html', active='god', status=status, repo_count = repo_count, team_count = team_count, total_size=total_size, errlog=errlog)

	elif request.method == 'POST':
		try:
			trackitd = trackit.core.trackitd_connect()
			result, error_string = trackitd.clear_attention_state()
			if result:
				flash("Error state reset to OK","alert-success")
			else:
				flash("trackitd returned an error: " + str(error_string),"alert-danger")
		except Exception as ex:
			flash("Could not contact trackitd to clear error state: " + str(ex),"alert-danger")

		return redirect(url_for('admin'))
