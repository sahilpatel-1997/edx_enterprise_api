import json
import requests

from django.conf import settings


def delete_edxorg_courses_from_search(course_id=None):
	"""Delete edxorg course from ElasticSearch"""
	headers = {'content-type': 'application/json'}
	ELASTIC_SEARCH_CONFIG = settings.ELASTIC_SEARCH_CONFIG[0]
	elasticsearch_url ="http://{}:{}".format(ELASTIC_SEARCH_CONFIG.get('host', 'localhost'),
		str(ELASTIC_SEARCH_CONFIG.get('port', 9200)))
	search_delete_1 ="{}/courseware_index/course_info/_query".format(elasticsearch_url)
	payload = {"query": {"bool": {"must": [{"term": {"course": course_id}}]}}}

	requests.delete(search_delete_1, data=json.dumps(payload), headers=headers)
