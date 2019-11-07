from django.conf.urls import url

from openedx.features.edx_enterprise_api import views

urlpatterns = [

    url(
        r'^courses/(?P<course_id>[^/]*)/course_about$',
        views.EdxorgCourseAbout.as_view(),
        name='edxorg_course_about',
    ),

]
