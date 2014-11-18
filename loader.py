from web import mongo, shorten
import collections
import datetime
import json

# seen = set()

# with open('data/results-2014-11-12-AM.json') as infile:
# 	data = json.load(infile)
# 	links = data['data']['link_history']

# data = collections.defaultdict(list)

# for index, link in enumerate(links):

# 	slug = link['link'].rsplit('/', 1)[-1]

# 	if slug not in seen:

# 		doc = shorten(link['long_url'], slug=slug, save=False)

# 		doc['title'] = link['title']
# 		doc['created_at'] = datetime.datetime.utcfromtimestamp(link['created_at'])
# 		doc['created_by'] = 'snlght'
# 		doc['archived'] = link['archived']
# 		doc['private'] = link['private']
		
# 		mongo.links.save(doc)

# 		print index, slug

# 		seen.add(slug)
