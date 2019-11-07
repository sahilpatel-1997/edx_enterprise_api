import logging

from django.core.management.base import BaseCommand

from openedx.features.edx_enterprise_api.views import EdxorgCourses

log = logging.getLogger(__name__)


class Command(BaseCommand):

	def handle(self, *args, **options):
		try:
			edx_courses = EdxorgCourses()
			edx_courses.set_edxorg_courses()
		except Exception as e:
			log.error(e)
