from rest_framework.viewsets import ModelViewSet
from rest_framework import filters
from .serializer import *
from rest_framework.settings import api_settings
from rest_framework import status
from rest_framework.response import Response


class TemplateViewSet(ModelViewSet):
    model = Template
    serializer_class = TemplateSerializer
    queryset = Template.objects.all().order_by('name')
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    http_method_names = ['get', 'post','patch','delete']


class ServiceGroupViewSet(ModelViewSet):
    model = ServiceGroup
    serializer_class = ServiceGroupSerializer
    queryset = ServiceGroup.objects.all().order_by('name')
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    http_method_names = ['get', 'post','patch','delete']


    def destroy(self, request, *args, **kwargs):
        super().destroy(self,*args, **kwargs)
        return Response(data='delete success',status=200)