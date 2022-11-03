from django.contrib import admin
from profilerule.models import *
# Register your models here.

admin.site.register(Branch)
admin.site.register(Template)
admin.site.register(ServiceGroup)
admin.site.register(ServiceTemplate)
admin.site.register(ServiceGroupBranch)
admin.site.register(QueuesProfile)
admin.site.register(AllowedProfiles)

