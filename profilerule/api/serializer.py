from rest_framework import serializers
from profilerule.models import *
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import logging
logger = logging.getLogger(__name__)

class AllowedProfilesSerializer(serializers.ModelSerializer):
    profile_id = serializers.ListField(required=False, allow_null=True)
    class Meta:
        model = AllowedProfiles
        fields = ('id', 'branch', 'profile_id')


class ServiceTemplateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ServiceTemplate
        fields = ('id', 'service_group', 'services', 'template')


class TemplateSerializer(serializers.ModelSerializer):
    branch_list = serializers.ListField(required=False, allow_null=True)
    service_template = ServiceTemplateSerializer(required=False, allow_null=True, many=True)

    class Meta:
        model = Template
        fields = ('id', 'name', 'branch_list', 'service_template')


    def validate_name(self, attr):
        logger.info('ilk')
        instance = getattr(self, 'instance',None)
        template = Template.objects.filter(name__iexact=attr)
        if instance:
            logger.info('ifin ici')
            template = template.exclude(id=instance.id) 
            logger.info('ifin sonu')
        if template.exists():
            raise ValidationError(_("Name must be unique for Template"))
        logger.info('son')
        return attr


    @staticmethod
    def validate_service(services, template, service_group):
    #     # for item in services:
    #     template = ServiceTemplate.objects.filter(template=template,
    #                                               services__contained_by=services).exclude(service_group=service_group).exists()
    #     if template:
    #         raise ValidationError({"error": "Service assigned other service group"})
        return template


    def update(self, instance, validated_data):
        service_template = validated_data.pop("service_template")
        branch_list = validated_data.pop("branch_list")
        data = super().update(instance, validated_data)
        service_group_ids = []
        for item in service_template:
            services = item.get("services") if item.get("services") else []
            service_group = item.get("service_group")
            service_group_ids.append(service_group)
            self.validate_service(services, instance, service_group)
            defaults = {
                "services": services
            }
            others = {
                "service_group": service_group,
                "template": instance,
            }
            ServiceTemplate.objects.update_or_create(defaults=defaults, **others)

        #Exclude == Beraber olmuyanlari goturmek ucun 
        logger.info(f"{service_group_ids},'IDLERR'")
        ServiceTemplate.objects.filter(template=instance).exclude(service_group__in=service_group_ids).delete()

        branch_ids = []
        for item in branch_list:
            branch_ids.append(item.get("branch_id"))
            others = {
                "branch_id": item.get("branch_id"),
                "template": instance,
            }
            logger.info(f"{others},'OTherss'")
            logger.info(f"{Branch.objects.filter(**others)}")
            if Branch.objects.filter(branch_id=item.get("branch_id")):
                Branch.objects.filter(branch_id=item.get("branch_id")).update(**others)
            else:
                Branch.objects.create(**others)


        Branch.objects.filter(template=instance).exclude(branch_id__in=branch_ids).update(template=None)
        logger.info(f"{ServiceGroupBranch.objects.filter(branch__template=instance).exclude(branch_id__in=branch_ids)},'EXCLUDELERERR',{branch_ids}")
        ServiceGroupBranch.objects.filter(branch__template=instance).exclude(branch_id__in=branch_ids).delete() # yoxla
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update({"service_template":ServiceTemplate.objects.filter(template=instance).values('id','service_group','services').order_by('service_group__name')})
        data.update({"count":Branch.objects.filter(template=instance).count(),"branch_list":Branch.objects.filter(template=instance).values('branch_id')})
        return data


class ServiceGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceGroup
        fields = ('id','name')

    def validate_name(self,attr):
        obj = ServiceGroup.objects.filter(name__iexact=attr)
        if obj:
            raise ValidationError(_("Name must be unique"))
        return attr


class ServiceGroupSettingSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField()

    class Meta:
        model = ServiceGroupBranch
        fields = ('id','group_id','percent')


    def validate(self,instance):
        logger.info(f"{instance},'THIS IS INSTANCE'")
        # sum_percent = 0
        # for group in service_groups:
        #     sum_percent+=group.get('percent')
        # if sum_percent!=100:
        #     raise ValidationError("The sum of the percentages must be 100 1")
        return instance


class UserNameSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField()
    branch_id = serializers.IntegerField()
    username = serializers.CharField()
    ip = serializers.CharField()
    class Meta:
        fields = ('profile_id','branch_id','username','ip')

    def validate_profile_id(self,attr):
        logger.info(f"'validate',{attr}")
        # logger.info(instance,'INSTANCEE'
        logger.info(f"{self.instance},'INSTANCE'")
        obj = AllowedProfiles.objects.filter(profile_id__overlap=[attr],branch__branch_id=self.instance.get('branch_id')) # burda branch idni de qeyd elemek lazimdi
        logger.info(f"{obj},'oobbjj'")
        if not obj:
            logger.info("RAISE")
            raise ValidationError(_("Profile id not allowed"))
        return attr