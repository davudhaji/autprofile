from posixpath import basename
from django.urls import path,include
from .views import *
from .viewset import TemplateViewSet,ServiceGroupViewSet
from rest_framework import routers

router = routers.SimpleRouter()
router.register(r'template',  TemplateViewSet, basename='template')
router.register(r'servicegroup',  ServiceGroupViewSet, basename='servicegroup')


urlpatterns = [
    path('branch/data/', BranchAPI.as_view()), #  Branch.as_view({'get': 'list'}) bele olsaydi Branch View yox gerek Viewset olardi
    path('branch/data/<int:id>/', BranchAPI.as_view()),
    path('service-list/',AllServicesAPI.as_view()),
    path('username/',GetUserNameAPI.as_view()),
    path('profiles/<int:pk>/',ProfileAPI.as_view()),
    path('branch-group/<int:pk>/', BranchGroupSettingsAPI.as_view()),
    path('', include(router.urls))
]