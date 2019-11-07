import ast
import os
import json
import datetime
import requests
import logging
import unidecode

from django.views import View
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http import Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.core.exceptions import ObjectDoesNotExist, FieldError, FieldDoesNotExist

from edxmako.shortcuts import render_to_response, render_to_string
from util.json_request import JsonResponse
from util.cache import cache_if_anonymous

from search.search_engine_base import SearchEngine
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from openedx.features.edx_enterprise_api.helpers import delete_edxorg_courses_from_search
from openedx.features.edx_enterprise_api.models import EdxOrgCourse

log = logging.getLogger(__name__)


class EdxorgCourses(object):
	""" Fetch edx.org courses and save courses information into Database."""

	def get_access_token_detail(self):
		""" Call EDX_ENTERPRISE_ACCESS_TOKEN_API  using credentials and get access token details of edx.org.

				Request method is "POST" 	

				data = {
					'grant_type': "client_credentials",
					'client_id': "CLIENT_ID",
					'client_secret': "CLIENT_SECRET",
					'token_type': "jwt"
				}

				reponse = {	
						u'token_type': u'JWT', 
						u'access_token': u'encrypted access token',
						u'expires_in': 3600, u'scope': u'read write profile email'
				}

		"""
		

		url = settings.EDX_ENTERPRISE_ACCESS_TOKEN_API

		data = {
			'grant_type': "client_credentials",
			'client_id': settings.EDX_ENTERPRISE_API_CLIENT_ID,
			'client_secret': settings.EDX_ENTERPRISE_API_CLIENT_SECRET,
			'token_type': "jwt"
		}

		return requests.request("POST", url, data=data)

	def get_client_catalog_detail(self, access_token_detail):
		""" Call EDX_ENTERPRISE_CLIENT_CATALOG_DETAIL_API and get catalog details of edx.org

				Request method is "GET"

				header =  {
						'authorization': access_token_detail.json().get('token_type')  access_token_detail.json().get('access_token'),
						'accept': "application/json",
						'cache-control': "no-cache",
				}

				response = {
						u'count': 3, 
						u'previous': u'',
						u'results': [
										{u'enterprise_customer': u'7705fbf0-b413-4e65-ac7e-da7dc17df390',
										u'uuid':	u'c794a200-6dce-4b5f-bb78-0d2013214b5e',
										u'title': u'Sterlite Catalog: All Courses (DSC)'},
										{u'enterprise_customer': u'7705fbf0-b413-4e65-ac7e-da7dc17df390',
										u'uuid': u'9c8f2ffe-d3f5-4234-8770-6716789e00bb', u'title': u'Curated Content'},
										{u'enterprise_customer': u'7705fbf0-b413-4e65-ac7e-da7dc17df390',
										u'uuid': u'af49a1e9-8662-47dd-a5cc-1d53028b48c1',
										u'title':u'All Content (9MAY2019)'}
									],
						u'next': u''
				}
		"""
		url = settings.EDX_ENTERPRISE_CLIENT_CATALOG_DETAIL_API

		headers = {
			'authorization': "{} {}".format(access_token_detail.json().get('token_type'),access_token_detail.json().get('access_token')),
			'accept': "application/json",
			'cache-control': "no-cache",
		}

		return requests.request("GET", url, headers=headers)

	def get_edx_courses_detail(self, access_token_detail, client_catalog_detail, api_url=None, response_list=[]):
		""" Make API using EDX_ENTERPRISE_COURSE_DETAIL_API and client_catalog_detail's UUID, 
		Call API and get edx.org courses detail. 

		Request method is 'GET'
		header = { 
				'authorization': access_token_detail.json().get('token_type')  access_token_detail.json().get('access_token'),
				'accept': "application/json",
				'cache-control': "no-cache" 
				}
		response = {  
					   'count':1743,
					   'previous':'',
					   'results':[  
						  {  
							 'organizations':['IUx: Indiana University'],
							 'languages':['English'],
							 'seat_types':['audit','verified'],
							 'card_image_url':None,
							 'content_type':'course',
							 'title':'Financial Reporting I',
							 'uuid':'33b60d53-f5ac-4f44-8e87-c277289fb576',
							 'full_description':'Course Full Discription',
							 'subjects':['Business & Management'],
							 'image_url':'https://prod-discovery.edx-cdn.org/media/course/image/
											33b60d53-f5ac-4f44-8e87-c277289fb576-78ced015ceba.small.png',
							 'aggregation_key':'course:IUx+BUKD-A500',
							 'key':'IUx+BUKD-A500',
							 'short_description':'Course Short Discription',
							 'enrollment_url':'https://courses.edx.org/enterprise/7705fbf0-b413-4e65-ac7e-da7dc17df390/
												course/IUx+BUKD-A500/enroll/?catalog=c794a200-6dce-4b5f-bb78-0d2013214b5e&utm_medium=enterprise&utm_source=sterlite-technologies',
							 'course_runs':[{  
								   'enrollment_mode':'verified',
								   'end':'2019-11-07T23:59:00Z',
								   'key':'course-v1:IUx+BUKD-A500+2T2019',
								   'first_enrollable_paid_seat_price':500,
								   'modified':'2019-10-17T22:43:41.734266Z',
								   'enrollment_start':None,
								   'weeks_to_complete':12,
								   'start':'2019-08-20T05:00:00Z',
												.
												.
												.
								},
								{  
								   'enrollment_mode':'verified',
								   'end':'2020-08-06T23:59:00Z',
								   'key':'course-v1:IUx+BUKD-A500+2T2020',
								   'first_enrollable_paid_seat_price':500,
								   'modified':'2019-10-17T22:43:41.753276Z',
								   'enrollment_start':None,
								   'weeks_to_complete':12,
								   'start':'2020-05-19T10:00:00Z',
												.
												.
												.
								},
							 ]
						 },
						  .
						  .
						  .
						  .
						]
					}

		 """
		try:
			url = api_url if api_url else "{}{}".format(settings.EDX_ENTERPRISE_COURSE_DETAIL_API,
				client_catalog_detail.json().get('results')[0].get('uuid'))

			headers = {
				'authorization': "{} {}".format(access_token_detail.json().get('token_type'),access_token_detail.json().get('access_token')),
				'accept': "application/json",
				'cache-control': "no-cache"
			}

			response = requests.request("GET", url, headers=headers)

			# if access token detail has been expired, its call again for access
			# token detail and get edx.org courses details
			if response.status_code == 401:
				if "expired" in response.json().get("detail", ""):
					access_token_detail = self.get_access_token_detail()
					self.get_edx_courses_detail(access_token_detail, client_catalog_detail,
												response.json().get('next', url), response_list)

			response_list.extend(response.json().get('results', []))
			if response.json().get('next', ''):
				self.get_edx_courses_detail(access_token_detail, client_catalog_detail,
											response.json().get('next', ''), response_list)
			return response_list
		except (TypeError, IndexError) as error:
			log.exception(error)
		except Exception as e:
			log.exception(e)
		

	
	def get_course_marketing_url(self, course_key, access_token_detail, client_catalog_detail):
		""" Get brief details for edx.org course and return marketing url
			url = "" https://api.edx.org/enterprise/v1/enterprise-catalogs/{catalog_id}/course-runs/{course_run_ID}""
			Request method is 'GET'
			header = { 
				'authorization': access_token_detail.json().get('token_type') access_token_detail.json().get('access_token'),
				'accept': "application/json",
				'cache-control': "no-cache" 
				}
		"""
		try:
			url ="{}{}/courses/{}".format(settings.EDX_ENTERPRISE_COURSE_DETAIL_API, client_catalog_detail.json().get('results')[0]['uuid'], course_key)

			headers = {
				'authorization': "{} {}".format(access_token_detail.json().get('token_type'),access_token_detail.json().get('access_token')),
				'accept': "application/json",
				'cache-control': "no-cache"
			}

			response = requests.request("GET", url, headers=headers)

			if response.status_code == 401:
				if "expired" in response.json().get("detail", ""):
					access_token_detail = self.get_access_token_detail()
					self.get_course_marketing_url(course_key, access_token_detail, client_catalog_detail)


			if response.json().get('course_runs'):
				return response.json().get('course_runs')[0]['marketing_url']
			else:
				return None
		except (TypeError, IndexError) as error:
			log.exception(error)
		except Exception as e:
			log.exception(e)


	def reindex_edxorg_courses(self, course_info):
		"""Reindex edx.org courses in course discovery 
		Agrs:
		course_info = {
										'id': course_id,
										'course': course_id,
										'content': {
												'number': course_key,
												'display_name': "course title"
										},
										'org': "edX Courses",
										'is_edx': True,
										'image_url': card_image_url,
										'start': course_start_date,
										'enrollment_start': enrollment_start_date,
								}

		"""
		searcher = SearchEngine.get_search_engine("courseware_index")

		if not searcher:
			return
		try:
			searcher.index("course_info", [course_info])
		except:
			log.exception(
				"Course discovery indexing error encountered, course discovery index may be out of date %s",
				course_info.get("id", ""),
			)

		log.info(
			"Successfully added %s course to the course discovery index",
			course_info.get("id", "")
		)

	def get_course_run(self, time_difference_list, sec_difference_sort, course_runs, sec_difference_item, now, index_cnt=0):
		""" Get working course_run object for course"""
		
		_index = time_difference_list.index(sec_difference_item)
		_run = course_runs[_index]
		if _run.get('enrollment_end'):
			enrollment_end = datetime.datetime.strptime(
				_run.get('enrollment_end'), '%Y-%m-%dT%H:%M:%SZ')
			if enrollment_end < now:
				index_cnt += 1
				try:
					sec_difference_item = sec_difference_sort[index_cnt][1]
					return self.get_course_run(time_difference_list, sec_difference_sort, course_runs, sec_difference_item, now, index_cnt)
				except Exception as e:
					if "index out of range" in e.message:
						sec_difference_item = sec_difference_sort[0][1]
						_index = time_difference_list.index(sec_difference_item)
						return course_runs[_index]
		return _run





	def set_edxorg_courses(self):
		"""Fetch courses from edx.org and save course information to database"""
		current_course_list = []
		now = datetime.datetime.now()
		default_card_image_url = "{}/static/edx_enterprise_api/images/course_default_image.jpeg".format(settings.LMS_ROOT_URL)
		try:
			access_token_detail = self.get_access_token_detail()
			client_catalog_detail = self.get_client_catalog_detail(
				access_token_detail)
			edx_courses_detail = self.get_edx_courses_detail(
				access_token_detail, client_catalog_detail)

			for course in edx_courses_detail:
				try:
					course_key = course.get('key')
					course_id = course.get('aggregation_key', '')
					card_image_url = course.get('card_image_url') if course.get(
						'card_image_url') else default_card_image_url
					course_details = {
						"course_id": course_id,
						"course_title": course.get('title'),
						"course_number": course_key,
						"course_image": card_image_url,
						"short_description": course.get('short_description', ''),
						"full_description": course.get('full_description', ''),
						"course_marketing_url": self.get_course_marketing_url(
							course_key, access_token_detail, client_catalog_detail),
						"course_enrollment_url": course.get('enrollment_url', ''),
						"course_details_json": course,
						"is_active": True if course.get('course_runs') else False
					}

					edx_course, created = EdxOrgCourse.objects.update_or_create(
						course_id=course_id, defaults = course_details,)
					edx_course.save()

					# edx.org course has multiple start-date of course
					# find nearest course start-date from today and consider it as course start-date
					if edx_course.is_active:
						try:
							time_difference_list = []
							for course_run in course.get("course_runs"):
								_start_date = datetime.datetime.strptime(course_run.get('start') if course_run.get(
									"start") else "2017-01-01T00:00:00Z", '%Y-%m-%dT%H:%M:%SZ')
								time_difference_list.append((now - _start_date).total_seconds())
							all_sec_difference, sec_difference_sort = [(abs(time_difference), time_difference) for time_difference in time_difference_list], [
								(abs(time_difference), time_difference) for time_difference in time_difference_list]
							sec_difference_sort.sort()
							sec_difference_item = sec_difference_sort[0][1]
							course_run_obj = self.get_course_run(
								time_difference_list, sec_difference_sort, course.get("course_runs"), sec_difference_item, now)
						except Exception as e:
							course_run_obj = course.get("course_runs")[0]
							log.error(str(e))

						course_start = datetime.datetime.strptime(
							course_run_obj.get("start").split('T')[0]
							if course_run_obj.get("start") else "2017-01-01", '%Y-%m-%d').strftime('%b %d, %Y')

						enrollment_start = datetime.datetime.strptime(
							course_run_obj.get("enrollment_start").split('T')[0]
							if course_run_obj.get("enrollment_start") else "2017-01-01", '%Y-%m-%d').strftime('%b %d, %Y')

						# make json format for reindexing courses in elasticsearch
						course_info = {
							'id': course_id,
							'course': course_id,
							'content': {
								'number': course.get("key", ""),
								'display_name': course.get("title", "")
							},
							'org': "edX Courses",
							'is_edx': True,
							'image_url': card_image_url,
							'start': course_start,
							'enrollment_start': enrollment_start,
						}
						self.reindex_edxorg_courses(course_info)
				except (IndexError, TypeError, FieldDoesNotExist, FieldError) as error:
					log.exception(error)
				except Exception as e:
					raise e

			# delete inactive or end courses from elasticsearch
			try:
				aggregation_key_list = [element['aggregation_key']
										for element in edx_courses_detail]
				edxorg_courses_list = EdxOrgCourse.objects.all().values_list('course_id', flat=True)
				difference_list = set(edxorg_courses_list) - set(aggregation_key_list)
				for course_key in difference_list:
					edxorg_courses_obj = EdxOrgCourse.objects.get(
						course_id=course_key)
					edxorg_courses_obj.is_active = False
					edxorg_courses_obj.save()
					delete_edxorg_courses_from_search(edxorg_courses_obj.course_id)

			except EdxOrgCourse.ObjectDoesNotExist as e:
				log.exception(e)

		except Exception as e:
			log.exception(e)


class EdxorgCourseAbout(View):
	"""Render course about page of edx.org courses"""

	@method_decorator(ensure_csrf_cookie)
	@method_decorator(cache_if_anonymous())
	def get(self, request, course_id):
		"""Pass edx.org course_id as Arg and Redirect to particular course about page"""

		try:
			default_card_image_url = "{}/static/edx_enterprise_api/images/course_default_image.jpeg".format(settings.LMS_ROOT_URL)
			course_obj = get_object_or_404(EdxOrgCourse, course_id=course_id)
			course_about_data = ast.literal_eval(
				course_obj.course_details_json)
			course_about_data.update(
				{'course_number': course_obj.course_number,
				 'org': 'edX Courses', 'enroll_url': course_obj.course_enrollment_url, 
				 'course_marketing_url': course_obj.course_marketing_url,
				 'is_course_available': True if course_about_data['course_runs'] else False,
				}
			)
			if not course_about_data['card_image_url']:
				course_about_data.update(
					{'card_image_url': default_card_image_url})

		except Exception as e:
			log.exception(e)
			raise Http404("This course is invalid. Please try another course.")    
		

		return render_to_response('edx_enterprise_api/edxorg_course_about.html', course_about_data)