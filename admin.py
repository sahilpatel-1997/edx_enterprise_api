import datetime

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.conf.urls import url
from django.http import JsonResponse


from openedx.features.edx_enterprise_api import views
from openedx.features.edx_enterprise_api.models import (
	EdxOrgCourse,
)


class EdxOrgCoursesAdmin(admin.ModelAdmin):
	list_display = ('course_id', 'course_title', 'is_edx', 'is_active')
	list_filter = ('is_edx', 'is_active',)
	search_fields = ('course_id', 'course_title',)

	def save_model(self, request, obj, form, change):
		"""if course is not active it removes from ElasticSearch else Save to table and reindex into ElasticSearch"""
		default_date = '2017-01-01T00:00:00+00:00'
		if not obj.is_active:
			views.delete_edxorg_courses_from_search(obj.course_id)
		else:
			course_info = {
				'id': obj.course_id,
				'course': obj.course_id,
				'content': {
					'number': obj.course_number,
					'display_name': obj.course_title
				},
				'org': 'edX Courses',
				'is_edx': True,
				'image_url': obj.course_image if obj.course_image else None,
				'start': datetime.datetime.strptime("2017-01-01", '%Y-%m-%d').strftime('%b %d, %Y'),
				'enrollment_start': default_date,
			}
			reindex_edxorg_courses(course_info)
		return super(EdxOrgCoursesAdmin, self).save_model(request, obj, form, change)


admin.site.register(EdxOrgCourse, EdxOrgCoursesAdmin)

