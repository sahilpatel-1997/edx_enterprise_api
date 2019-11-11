import uuid

from django.db import models
from django.contrib.auth.models import User

from model_utils.models import TimeStampedModel

from openedx.features.edx_enterprise_api.helpers import delete_edxorg_courses_from_search


class EdxOrgCoursesQuerySet(models.QuerySet):

    def delete(self, *args, **kwargs):
        """set is_active false for delete courses and remove from ElasticSearch"""
        for obj in self:
            delete_edxorg_courses_from_search(course_id=obj.course_id)
            obj.is_active = False
            obj.save()


class EdxOrgCourse(TimeStampedModel):
    """This table contain details of EdX Enterprise Courses"""
    course_id = models.CharField(max_length=128, unique=True)
    course_title = models.CharField(max_length=255)
    course_number = models.CharField(max_length=255)
    course_image = models.CharField(max_length=1024)
    short_description = models.TextField(null=True, blank=True)
    full_description = models.TextField(null=True, blank=True)
    course_marketing_url = models.CharField(
        max_length=512, null=True, blank=True)
    course_enrollment_url = models.CharField(
        max_length=512, null=True, blank=True)
    course_details_json = models.TextField()
    is_edx = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    objects = EdxOrgCoursesQuerySet.as_manager()

    class Meta:
        app_label = "edx_enterprise_api"

    def delete(self, *args, **kwargs):
        """set is_active false for delete course and remove from ElasticSearch"""
        delete_edxorg_courses_from_search(course_id=self.course_id)
        self.is_active = False
        self.save()

    def __unicode__(self):
        return self.course_id

    def __repr__(self):
        return self.__unicode__()
