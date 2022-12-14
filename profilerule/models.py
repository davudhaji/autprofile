from dataclasses import field
import profile
from tempfile import template
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from rest_framework.exceptions import ValidationError

# Create your models here.

UNIQUE_ARRAY_FIELDS = ('services',)



class ServiceManager(models.Manager):
    
    def prevent_duplicates_in_array_fields(self, model, array_field,template=None):
        def duplicate_check(_lookup_params):
            fields = self.model._meta.get_fields()
            for unique_field in UNIQUE_ARRAY_FIELDS:
                unique_field_index = [getattr(field, 'name', '') for field in fields]
                try:
                    # template_index = unique_field_index.index('template')
                    unique_field_index = unique_field_index.index(unique_field)
                except ValueError:
                    continue
            all_items_in_db = [item for sublist in self.values_list(fields[unique_field_index].name).filter(**_lookup_params) for item in sublist]
            all_items_in_db = [item for sublist in all_items_in_db for item in sublist]
            if not set(array_field).isdisjoint(all_items_in_db):
                raise ValidationError('{} contains items already in the database'.format(array_field))
         
        lookup_params = {}
        lookup_params.update({'template_id':template.id})
        duplicate_check(lookup_params)


class Branch(models.Model):
    enable = models.BooleanField(default=False)
    branch_id = models.IntegerField()
    unversal_profile_id = models.IntegerField(max_length=50,blank=True,null=True)
    template = models.ForeignKey('Template',null=True,blank=True,on_delete=models.SET_NULL)
    reset = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if Branch.objects.filter(branch_id=self.branch_id) and not Branch.objects.filter(id=self.id) :
            raise ValidationError('This branch available')

        else:
            super().save(*args, **kwargs)


class Template(models.Model):
    name = models.CharField('Name',max_length=50)


class ServiceTemplate(models.Model):
    service_group = models.ForeignKey('ServiceGroup',on_delete=models.CASCADE)
    template = models.ForeignKey('Template',on_delete=models.CASCADE)
    services = ArrayField(models.IntegerField(),blank=True,null=True) 
    objects = ServiceManager()

    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.id and ServiceTemplate.objects.filter(template=self.template,service_group=self.service_group).last():
            pass
        else:
            st = ServiceTemplate.objects.filter(id=self.id).last()
            services = self.services.copy() if self.services else None
            if st:
                if services:
                    for i in st.services:
                        if i in self.services:
                            services.remove(i)
            if services:
                ServiceTemplate.objects.prevent_duplicates_in_array_fields(self, services, template=self.template)
            super().save(*args, **kwargs)

class ServiceGroup(models.Model):
    name = models.CharField('Name',max_length=50)
    template = models.ForeignKey("Template", on_delete=models.CASCADE,null=True,blank=True)


class ServiceGroupBranch(models.Model):
    service_group = models.ForeignKey("ServiceGroup", on_delete=models.CASCADE)
    branch = models.ForeignKey('Branch',on_delete=models.CASCADE)
    percent = models.IntegerField()
    

class QueuesProfile(models.Model):
    branch = models.ForeignKey('Branch', on_delete=models.CASCADE)
    queue_id = models.IntegerField()
    profile_id = models.IntegerField()

class AllowedProfiles(models.Model):
    branch = models.ForeignKey("Branch",on_delete=models.CASCADE)
    profile_id = ArrayField(models.IntegerField(),blank=True,null=True) 


