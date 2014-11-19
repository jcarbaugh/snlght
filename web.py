from flask import (Flask, Response, abort, flash, jsonify,
	redirect, render_template, request, url_for)
from flask.ext.login import (LoginManager, UserMixin,
    current_user, login_user, logout_user, login_required)
import datetime
import lxml.html
import os
import pymongo
import random
import requests
import unicodecsv
import StringIO

try:
    from urlparse import urlparse       # python 2.x
except:
    from urllib.parse import urlparse   # python 3.x


SLUG_CHARS = list('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
DEFAULT_SLUG_LENGTH = 5
DEFAULT_SLUG_ATTEMPTS = 100

SECRET_KEY = os.environ.get('SECRET_KEY')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')


#
# set up MongoDB connection
#

mongo_url = os.environ.get('MONGOHQ_URL', 'mongodb://localhost:27017/snlght')
mongo_conn = pymongo.MongoClient(mongo_url)

mongo_params = urlparse(mongo_url)

mongo = mongo_conn[mongo_params.path.strip('/')]

if mongo_params.username and mongo_params.password:
    mongo.authenticate(mongo_params.username, mongo_params.password)


#
# utility methods
#

def slug_is_unique(slug):
	return mongo.links.find({'slug': slug}).count() == 0


def generate_slug(length=DEFAULT_SLUG_LENGTH, attempts=DEFAULT_SLUG_ATTEMPTS):
	# make several attempts to generate a unique slug, checking against
	# existing data set
	for attempt in range(attempts):
		slug = "".join(random.choice(SLUG_CHARS) for i in range(length))
		if slug_is_unique(slug):
			break
	return slug


def shorten(url, slug=None, save=True):

	if not url:
		raise ValueError('URL is required')

	if slug:
		if not slug_is_unique(slug):
			raise ValueError('slug is already taken')
	else:
		slug = generate_slug()

	doc = {
		'archived': False,
		'private': False,
		'slug': slug,
		'url': url,
		'visits': 0,
		'created_at': datetime.datetime.utcnow(),
		'created_by': 'snlght',
		'title': '',
	}

	if save:
		mongo.links.save(doc)

	return doc


def fetch_title(url):

	try:

		resp = requests.get(url)
		if resp.status_code != 200:
			return

		doc = lxml.html.document_fromstring(resp.content)
		elem = doc.find(".//title")

		if elem is not None:
			return elem.text

	except requests.exceptions.ConnectionError:
		pass # we'll just ignore this
	except requests.exceptions.MissingSchema:
		pass # ignore this too


#
# CSV generator
#

def generate_csv(docs):
	bffr = StringIO.StringIO()
	writer = unicodecsv.writer(bffr)
	writer.writerow(('slug', 'url', 'title', 'created_at', 'created_by', 'visits'))
	bffr.seek(0)
	yield bffr.read()
	for doc in docs:
		bffr.truncate(0)
		writer.writerow((
			doc['slug'],
			doc['url'],
			doc['title'] or '',
			doc['created_at'].isoformat(),
			doc['created_by'],
			doc['visits'],
		))
		bffr.seek(0)
		yield bffr.read()
	bffr.close()

#
#
#

app = Flask(__name__)
app.secret_key = SECRET_KEY


# login stuff

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, is_admin=False):
        self.is_admin = is_admin

    @classmethod
    def admin_user(self):
        user = User(is_admin=True)
        user.id = 'admin'
        return user

    @classmethod
    def basic_user(self):
        user = User(is_admin=False)
        user.id = 'basic'
        return user


@login_manager.user_loader
def load_user(user_id):
    if user_id == 'admin':
        return User.admin_user()
    elif user_id == 'basic':
        return User.basic_user()


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == 'POST':

        password = request.form.get('password')
        
        if password == ADMIN_PASSWORD:
            user = User.admin_user()
            login_user(user)
            return redirect(url_for('recent_view'))
        else:
        	flash('NOPE!') 

    return render_template('login.html')


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))


# routes

@app.route('/', methods=['GET'])
def index():
	return redirect('https://sunlightfoundation.com')


@app.route('/make', methods=['GET', 'POST'])
@login_required
def make():

	data = {
		'url': '',
		'title': '',
	}

	if request.method == 'POST':

		data['url'] = request.form.get('url')
		data['title'] = request.form.get('title')
		data['slug'] = request.form.get('slug')

		try:

			link = shorten(data['url'], data['slug'], save=False)
			link['title'] = data['title'] or fetch_title(data['url'])
			
			mongo.links.save(link)

			flash('Congrats! Your link is now short.', 'success')
			return redirect(url_for('recent_view'))

		except ValueError, ve:
			flash('Oh noes! %s' % ve.message, 'error')
			
	else:
		data['slug'] = generate_slug()
	return render_template('make.html', **data)


@app.route('/slug', methods=['GET'])
@login_required
def slug_view():
	slug = generate_slug()
	data = {'slug': slug}
	return jsonify(data)


@app.route('/slug/<slug>', methods=['GET'])
@login_required
def slug_exists_view(slug):
	data = {'ok': slug_is_unique(slug)}
	return jsonify(data)


@app.route('/dump', methods=['GET'])
@login_required
def dump_view():
	if 'format' in request.args:
		if request.args.get('format') == 'csv':
			headers = {
				'Content-Disposition': 'attachment; filename=short-links.csv',
				'Content-Type': 'text/csv',
			}
			docs = mongo.links.find().sort('created_at', 1)
			return Response(generate_csv(docs), headers=headers)
	return render_template('dump.html')


@app.route('/recent', methods=['GET'])
@login_required
def recent_view():
	links = mongo.links.find().limit(20).sort('created_at', -1)
	return render_template('list.html', links=links, title='Some recent shorts for you')


@app.route('/top', methods=['GET'])
@login_required
def top_view():
	links = mongo.links.find().limit(20).sort('visits', -1)
	return render_template('list.html', links=links, title='Most popular shorts for you')


@app.route('/<slug>', methods=['GET'])
def redirect_view(slug):
	link = mongo.links.find_one({'slug': slug})
	if not link:
		abort(404)
	mongo.links.update({'_id': link['_id']}, {'$inc': {'visits': 1}})
	return redirect(link['url'], code=301)


if __name__ == '__main__':
	app.run(debug=True, port=8000)
