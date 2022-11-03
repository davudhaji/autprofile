from rest_framework.response import Response
from rest_framework.views import APIView
import requests
from rest_framework import status
from requests.auth import HTTPBasicAuth
from django.shortcuts import get_object_or_404
from profilerule.models import Branch, ServiceGroupBranch,Template,QueuesProfile#,AllowedProfiles
import psycopg2
import json
from .serializer import *
from django.db.models import F, CharField, IntegerField, ExpressionWrapper, Value
from rest_framework.exceptions import ValidationError

from profilerule.api import serializer
import logging
logger = logging.getLogger(__name__)

AUTH = HTTPBasicAuth('superadmin', 'Ab123456Ab')

class ProfileAPI(APIView):
    
    def get(self,request,pk=None,*args, **kwargs):
        profile_data = requests.get(f'http://94.130.176.68:8080/qsystem/rest/managementinformation/branches/{pk}/profiles/',auth=AUTH)
        return Response(profile_data.json())
        
class BranchAPI(APIView):
    
    def get(self,request,*args, **kwargs):
        if not kwargs.get("id"):
            data = requests.get('http://94.130.176.68:8080/qsystem/rest/managementinformation/branches/',auth=AUTH)
            branch_list = [{"id":branch.get("id"),"name":branch.get("name")} for branch in data.json()]
            created_branchs = Branch.objects.all().values('branch_id')
            print(created_branchs,"all branchs which created")
            current_branch_ids = [branch.get("id") for branch in data.json()]
            print(current_branch_ids,"thiss current branch ids")
            temp3 = [x for x in created_branchs if x.get('branch_id') not in current_branch_ids]
            temp3 = [x.get("branch_id") for x in temp3]
            print(temp3,'thiss temp 3')
            Branch.objects.filter(branch_id__in=temp3).delete()
            branch_list = sorted(branch_list, key=lambda d: d['name'],reverse=True)
            return Response(branch_list)
        else:
            branch_id = kwargs.get('id')
            queue_search = request.query_params.get('queue', None)
            logger.info(f'{queue_search} SEARCHH')
            if type(branch_id)==int and branch_id>=0:
                logger.info('create den evvel')

                branch,create = Branch.objects.get_or_create(branch_id=branch_id)
                logger.info('createdn sonra')
                data = branch.__dict__
                data.pop('_state')
                template_id = data.pop('template_id')
                
                groups = ServiceGroupBranch.objects.filter(branch=branch).annotate(name=ExpressionWrapper(F('service_group__name'),output_field=CharField()),group_id=ExpressionWrapper(F('service_group__id'),output_field=IntegerField())).values('id','name','group_id','percent') if template_id else []
                if not groups:
                    logger.info(f'gruoup idye girdi {template_id}')
                    groups = ServiceTemplate.objects.filter(template__id=template_id).annotate(percent=Value(0,output_field=IntegerField()),name=ExpressionWrapper(F('service_group__name'),output_field=CharField()),group_id=ExpressionWrapper(F('service_group__id'),output_field=IntegerField())).values('name','group_id','percent')
                logger.info(f'{groups} GROUPS')

                data.update({"service_groups":groups})
                logger.info('ifin ustu')
                if template_id:
                    data.update({"template_id":template_id,"template_name":Template.objects.get(id=template_id).name})

                    conn = psycopg2.connect(
                    database="qp_central", user='', password='', host='', port= '5432'
                    )
                    services2 = Template.objects.get(id=template_id).servicetemplate_set.values_list('services',flat=True)
                    services_ids = []
                    for item in services2:
                        services_ids.extend(item)
                    services_ids = ','.join([str(x) for x in services_ids])
                    services_ids = "(" + services_ids + ")" if services_ids else ()
                    cursor = conn.cursor()
                    dict_queue = []
                    logger.info(f'{services_ids} SERVICES IDS')
                    if services_ids:
                        logger.info('IFIN ICINE GIRDI')
                        cursor.execute(f'''
                        select q."name" as queue_name, q.id as queue_id 
                        from service_group_service sgs 
                        join service_definitions sd on sd.id = sgs.service_id 
                        join service_groups sg on sg.id = sgs.service_group_id
                        join queues q on q.id = sg.defaultqueue_id 
                        join branch_profiles bp on bp.id = sg.branch_profile_id 
                        join branch b on b.branch_profile_id = bp.id WHERE sd.id IN {services_ids} AND b.id = {branch_id};
                        ''')
                        # data.update({"profile_data":profile_data.json()})
                        dbdata = cursor.fetchall()
                        queues = set(dbdata)
                        for i in queues:
                            queue_name,queue_id = i
                            dict_queue.append({'name':queue_name,'id':queue_id})
                    
                    logger.info(f'{dict_queue} DICT QUEUE')
                    if queue_search:
                        queue_ids = []
                        for i in dict_queue:
                            if queue_search.upper() in i.get('name').upper():
                                logger.info('Append oldu')
                                queue_ids.append(i.get('id'))
                                

                    queues_with_profile = QueuesProfile.objects.filter(branch__branch_id=branch_id)
                    if queue_search:
                        logger.info('SEARCH IFININ ICINIE GIRDI')
                        if queue_ids:
                            queues_with_profile.filter(queue_id__in=queue_ids)
                        else:
                            queues_with_profile = []
                    data.update({"queues_with_profile":queues_with_profile.values('id','queue_id','profile_id') if queues_with_profile else []})
                    data.update({'queues':dict_queue})
                    data.update({'allowed_profiles':AllowedProfiles.objects.filter(branch__branch_id=branch_id).values('profile_id')[0].get('profile_id') if AllowedProfiles.objects.filter(branch__branch_id=branch_id).values('profile_id') else []})

                
                    
               

                return Response(data)
            else:
                return Response(status=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def calculate_percent(service_groups,branch_id):
        #Sum Check burda olmalidi
        if service_groups and not service_groups[0].get('id'):
            old = ServiceGroupBranch.objects.filter(branch__branch_id=branch_id).values('service_group','percent')
            all_groups = list(old)+service_groups
            
        else:
            all_groups = service_groups
        sum_percent = 0
        for group in all_groups:
            sum_percent+=group.get('percent')
        if sum_percent!=100:
            raise ValidationError("The sum of the percentages must be 100 1")
        for group in service_groups:
            if ServiceGroup.objects.filter(id=group.get("group_id")).last() and Branch.objects.filter(branch_id=branch_id).last():
                if group.get('id'):
                    logger.info('ifff')
                    group_dict = {"service_group":ServiceGroup.objects.filter(id=group.get("group_id")).last(),"percent":group.get("percent"),'branch':Branch.objects.filter(branch_id=branch_id).last()}
                    a=ServiceGroupBranch.objects.filter(id=group.get("id")).update(**group_dict)
                    
                else:
                    logger.info('elseeee2')
                    group_dict = {"service_group":ServiceGroup.objects.filter(id=group.get("group_id")).last() ,"percent":group.get("percent"),'branch':Branch.objects.filter(branch_id=branch_id).last()}
                    # serializer = ServiceGroupSettingSerializer(data=group_dict,many=True)
                    # if serializer.is_valid(raise_exception=True):
                    #     logger.info('IS VALIDDIII SAVE OLMALIDI')
                    #     serializer.save()
                    a=ServiceGroupBranch.objects.create(**group_dict)
                    logger.info(f'{a}')
            
            else:
                raise ValidationError("Servicgroup id or branch id not valid")
            

    
    def post(self,request,*args, **kwargs):
        all_json = json.loads(request.body)
        branch = all_json.get("branch_id")
        if Branch.objects.filter(branch_id=branch).last().template:
            service_groups = all_json.pop('service_groups')
            if service_groups:
                self.calculate_percent(service_groups,branch)
            queue_profile = all_json.pop('queues_with_profile')
            if queue_profile:
                logger.info("QUEUE PROFILLER VARRR")
                for queue in queue_profile:
                    
                    #logger.info(QueuesProfile.objects.filter(queue_id=queue.get('queue_id')),"BILINNN")
                    if not QueuesProfile.objects.filter(queue_id=queue.get('queue_id'),branch__branch_id=branch):
                        queue.update({"branch":get_object_or_404(Branch,branch_id=branch)})
                        logger.info(queue,"CREATE OLUNMALIDI")
                        QueuesProfile.objects.create(**queue)
                        logger.info('create olundu')
                    elif QueuesProfile.objects.filter(queue_id=queue.get('queue_id'),branch__branch_id=branch):
                        q = QueuesProfile.objects.filter(queue_id=queue.get('queue_id'),branch__branch_id=branch).last() 
                        if q:
                            # queue.pop('id')
                            q.__dict__.update(queue)
                            q.save()
                        else:
                            logger.info("Q idye uyqun filter tapilmadi tapilmadi")
                    else:
                        logger.info("ve ya hemin q idye bagli profile var")
            allowed_profiles = all_json.pop('allowed_profiles')
            if allowed_profiles:
                profile=AllowedProfiles.objects.filter(branch__branch_id=branch).last() 
                if profile:
                    allowed_profiles = {"profile_id":allowed_profiles}
                    profile.__dict__.update(allowed_profiles)   
                    profile.save()
                else:
                    profile_data = {'branch':get_object_or_404(Branch, branch_id=branch),'profile_id':allowed_profiles}
                    AllowedProfiles.objects.create(**profile_data)
                    
                    # serializer = AllowedProfilesSerializer(data=profile_data,many=True)
                    # if serializer.is_valid(raise_exception=True):
                    #     serializer.save()
                    
            branch = get_object_or_404(Branch, branch_id=branch)
            branch.__dict__.update(all_json)
            branch.save()

            return Response(all_json)
        else:
            return Response([])

class AllServicesAPI(APIView):
    def get(self,request):
        conn = psycopg2.connect(
            database="", user='', password='', host='', port= '5432'
            )
        cursor = conn.cursor()
        cursor.execute("""
        select sd.internal_name as service_name, sd.id as service_id
        from service_group_service sgs 
        join service_definitions sd on sd.id = sgs.service_id 
        join service_groups sg on sg.id = sgs.service_group_id
        join queues q on q.id = sg.defaultqueue_id 
        join branch_profiles bp on bp.id = sg.branch_profile_id 
        join branch b on b.branch_profile_id = bp.id;
        """)
        dbdata = cursor.fetchall()
        services = set(dbdata)
        services_list = []
        for service in services:
            service_name,service_id = service
            services_list.append({'service':service_name,'id':service_id})

        return Response(services_list)

class BranchGroupSettingsAPI(APIView):

    def get(self,request,pk):
        data = ServiceGroupBranch.objects.filter(branch__branch_id=pk).annotate(name=ExpressionWrapper(F('service_group__name'),output_field=CharField()),group_id=ExpressionWrapper(F('service_group__id'),output_field=IntegerField())).values('id','name','group_id','percent')
        if data:
            logger.info(f'{data}')
        
        # groups = ServiceGroupBranch.objects.filter(branch__branch_id=pk).annotate(name=ExpressionWrapper(F('service_group__name'),output_field=CharField()),group_id=ExpressionWrapper(F('service_group__id'),output_field=IntegerField())).values('id','name','group_id','percent') if template_id else []
        # if not groups:
        #     groups = ServiceTemplate.objects.filter(template__id=template_id).annotate(percent=Value(0,output_field=IntegerField()),name=ExpressionWrapper(F('service_group__name'),output_field=CharField()),group_id=ExpressionWrapper(F('service_group__id'),output_field=IntegerField())).values('name','group_id','percent')
        
        
        
        return Response(data)

    def post(self,request,pk):
        groups = json.loads(request.body)
        logger.info('GROUP')
        serializers = ServiceGroupSettingSerializer(data=groups,many=True)
        if serializers.is_valid(raise_exception=True):
            logger.info("is valid")
            BranchAPI.calculate_percent(groups,pk)
            return Response(serializers.data)
        return Response([])


class GetUserNameAPI(APIView):
    def post(self,request,*args, **kwargs):
        if request.body:
            serializers = UserNameSerializer(data=json.loads(request.body),instance=json.loads(request.body))
            if serializers.is_valid(raise_exception=True):

                branch_id = serializers.data.get('branch_id')
                username = serializers.data.get('username')
                ip = serializers.data.get('ip')
                if Branch.objects.filter(branch_id=branch_id).last() and Branch.objects.filter(branch_id=branch_id).last().enable:
                    # profile_id = serializers.data.get('profile_id')
                    branch_now = Branch.objects.filter(branch_id=branch_id).last()
                    branch_now.reset = False
                    branch_now.save()
                    conn = psycopg2.connect(
                    database="", user='', password='', host=f'{ip}', port= '5432'
                    )
                    cursor = conn.cursor()
                    
                    query = f"""
                    select cs.user_name, cs.work_profile_id, cs.branch_id, cwp.orig_id,cs.session_state from qp_agent.cfm_session cs
                    join qp_agent.cfm_work_profile cwp on cwp.id = cs.work_profile_id 
                    where user_name != '{username}' and session_state not in ('NO_STARTED_SERVICE_POINT_SESSION', 'NO_STARTED_USER_SESSION')
                    and branch_id ={branch_id};
                    """
                    cursor.execute(query)
                    dbdata = cursor.fetchall()
                    profiles = set(dbdata)
                    serv = 0
                    logger.info(f"ACTIVE PROFILES: {profiles}")
                    
                    
                    
                    allowed_profile_ids = []
                    if not profiles:
                        self.set_unv_profile(branch_id,ip,username)
                        return Response(["unv profile"],status=200)
                    for i in profiles:
                        user_name,staff_profile,branch,orig_id,session = i
                        if self.check_profile(orig_id,branch_id):

                            allowed_profile_ids.append({"profile_id":staff_profile,"user_name":user_name,"orig_id":orig_id,"session":session})


                        logger.info(f"'Username:',{user_name},'staff_Id:',{staff_profile},'bracnh_id:',{branch},'orig_id:',{orig_id},'session:',{session}")
                        if session == 'SERVING':
                            serv=1
                            
                
                    if not serv:
                        self.set_unv_profile(branch_id,ip,username)
                        return Response(['Unv Prof set'],200)
                        



                    else:
                        logger.info("ALLOWED PROFILES IDS WHICH ACTIVE IN QMATIC")        
                        # Hansilar SERVING edir hansilar etmir onu tapmaliyam
                        all_data = requests.get(f'http://94.130.176.68:8080/qsystem/rest/managementinformation/branches/{branch_id}/servicePoints/',auth=AUTH).json()
                        visits = []
                        for allowed in allowed_profile_ids:
                            logger.info('fora girdi')
                            for i in all_data:
                                if i.get('staffName') == allowed.get('user_name'):
                                    allowed.update({"visit_id":i.get('currentVisitId')})
                                    if i.get('currentVisitId'):
                                        visits.append(i.get('currentVisitId'))
                        


                        if len(visits)==1:
                            visits = '('+str(visits[0])+')'
                        else:
                            visits = tuple(visits)
                        logger.info('Connon evvel')
                        conn = psycopg2.connect(
                            database="", user='', password='', host=f'{ip}', port= '5432'
                            )
                        cursor = conn.cursor()
                        logger.info("VISITSSS")
                        #visits = (2995, 3025, 3022)
                        services = []
                        if type(visits) == str:
                            data = requests.get(f"http://94.130.176.68:8080/qsystem/rest/servicepoint/branches/{branch_id}/visits/{visits[1:-1]}/",auth=AUTH)
                            data = data.json()
                            services.append(data.get('currentVisitService').get('serviceId'))
                            logger.info(f"{services} services")
                        else:
                            for i in visits:
                                logger.info(i,"tuplee")
                                try:
                                    data = requests.get(f"http://94.130.176.68:8080/qsystem/rest/servicepoint/branches/{branch_id}/visits/{i}/",auth=AUTH)
                                    data = data.json()
                                    logger.info('tuple contentt')
                                    services.append(data.get('currentVisitService').get('serviceId'))
                                    logger.info(services,"THISSSS CONTENTT")
                                except:
                                    logger.info("EXCEPTDEEE GIRDIII")
                        
                        # query = f"""
                        # select cv.current_visit_event_id, cve.parameters_string from cfm_visits cv
                        # join cfm_visit_events cve on cv.current_visit_event_id = cve.id
                        # where cv.id in {visits};
                        # """
                        # logger.info('Executeden evvel')
                        # cursor.execute(query)
                        # logger.info('EXecute etdikden sonra')
                        # dbdata = cursor.fetchall()
                        # logger.info(dbdata,'DBDATAA')
                        # services = set(dbdata)
                        # conn.commit()
                        # conn.close()
                        logger.info('Executden sonra')
                        services_ids = []
                        logger.info(allowed_profile_ids,"END VERSIONN NN",len(allowed_profile_ids))
                        for i in services:
                            #services_ids.append(json.loads(i[1]).get('serviceOrigId'))
                            services_ids.append(i)

                        logger.info(services_ids,'servicess idss ')
                        servicegroups = []
                        if services_ids:
                            for i in services_ids:
                                obj = ServiceTemplate.objects.filter(services__overlap=[i]).last()
                                if obj:
                                    logger.info(ServiceGroupBranch.objects.filter(),'AALLLLLLLLLL')
                                    servicegroups.append(obj.service_group)

                        logger.info(servicegroups,'SERVICE GROUP')
                        if not servicegroups:
                            pass
                        else:
                            active_allowed_profile_count = len(allowed_profile_ids)+1
                            logger.info("ACTIVE ALLOWED PROFILESSS")

                            template = Branch.objects.filter(branch_id=branch_id).last().template

                            all_percents = ServiceGroupBranch.objects.filter(branch__branch_id = branch_id).values('percent','branch','service_group','id')
                            logger.info("THISSSSSSSSSSSS")

                            if (len(all_percents)>active_allowed_profile_count) or (active_allowed_profile_count==2):
                                self.set_unv_profile(branch_id,ip,username)
                                logger.info('return oldu')
                                return Response(serializers.data)

                            else:

                                check_count = 0
                                if len(all_percents)==active_allowed_profile_count:
                                    for i in all_percents:
                                        check_count+=round(active_allowed_profile_count/100*i.get('percent')) # roundun yerine int olmali idi
                                        i.update({"max":1})
                                else:
                                    for i in all_percents:
                                        check_count+=round(active_allowed_profile_count/100*i.get('percent')) # roundun yerine int olmali idi
                                        i.update({"max":round(active_allowed_profile_count/100*i.get('percent'))})
                                # logger.info(active_allowed_profile_count-check_count,'MUST BE UNVERSEL WHEN FULL')

                                # logger.info(all_percents,'ALL PERCENTSS',servicegroups[0].id)
                                
                                for sgb in all_percents:
                                    for i in servicegroups:
                                        if sgb.get('service_group') == i.id:
                                            logger.info("TAPDII")
                                            sgb.update({"max":sgb.get("max")-1})
                                    
                                logger.info('ALL PERCENTS NOWW')
                                ready_for_serving = []
                                for sgb in all_percents:
                                    if sgb.get('max')>0:
                                        ready_for_serving.append(sgb)

                                if not ready_for_serving:
                                    self.set_unv_profile(branch_id,ip,username)
                                    return Response(['Unv Prof set'],200)
                                
                                #Else
                                logger.info("SONNNN")

                                services_for_queues = []

                                for i in ready_for_serving:
                                    st = ServiceTemplate.objects.filter(service_group=i.get('service_group'),template=template).last()
                                    if st:
                                        for sid in st.services:
                                            services_for_queues.append(sid)
                                    else:
                                        logger.info('ST YOXDUUU')

                                if not services_for_queues:
                                    return Response(['not services'],400)

                                if len(services_for_queues)==1:
                                    services_for_queues = '('+str(services_for_queues[0])+')'
                                else:
                                    services_for_queues = tuple(services_for_queues)
                                
                                logger.info('sfqqqqqqq')
                                conn = psycopg2.connect(
                                database="", user='', password='', host='', port= '5432'
                                )
                                cursor = conn.cursor()
                                query = f"""
                                    select  b.id as branch_id, sd.id as service_id, q.id as queue_id 
                                    from service_group_service sgs 
                                    join service_definitions sd on sd.id = sgs.service_id 
                                    join service_groups sg on sg.id = sgs.service_group_id
                                    join queues q on q.id = sg.defaultqueue_id 
                                    join branch_profiles bp on bp.id = sg.branch_profile_id 
                                    join branch b on b.branch_profile_id = bp.id
                                    where sd.id in {services_for_queues} and b.id = {branch_id};
                                """
                                logger.info(f"{query}")
                                cursor.execute(query)
                                dbdata = cursor.fetchall()
                                queues = set(dbdata)
                                conn.commit()
                                conn.close()

                                only_queue = []

                                for i in queues:
                                    only_queue.append(i[-1])


                                only_queue = set(only_queue)
                                only_queue = tuple(only_queue)
                                
                                logger.info("ONLLYY222222222222")

                                all_data = requests.get(f'http://94.130.176.68:8080/qsystem/rest/managementinformation/branches/{branch_id}/queues/',auth=AUTH)
                                # logger.info(all_data.json(),'THIS ALL')
                                

                                q_and_waiting_time = []
                                for q in only_queue:
                                    for i in all_data.json():
                                        if i.get('id')==q:
                                            q_and_waiting_time.append({'q':q,'waiting_time':i.get('waitingTime')})
                                            

                                logger.info(f"{q_and_waiting_time},'Q AND WAITING TIME'")
                                q_and_waiting_time = sorted(q_and_waiting_time, key=lambda d: d['waiting_time'],reverse=True)
                                logger.info(f"{q_and_waiting_time[0]},'Sorted',{q_and_waiting_time}") if q_and_waiting_time else logger.info("none")
                                if q_and_waiting_time[0].get('waiting_time') == 0:
                                    self.set_unv_profile(branch_id,ip,username)
                                    return Response(['Unv Set'],200)


                                elif q_and_waiting_time:
                                    logger.info('q tapildi')
                                    prof_id = QueuesProfile.objects.filter(branch__branch_id=branch_id,queue_id=q_and_waiting_time[0].get('q')).values('profile_id')
                                    prof_id = list(prof_id)
                                    if prof_id:
                                        prof_id = prof_id[0].get('profile_id')
                                        logger.info('proffff')
                                        self.set_unv_profile(branch_id,ip,username,prof_id=prof_id)
                                        logger.info('SET OLUNUB BITMELIDI')
                                    else:
                                        logger.info('prof id yoxduu')
                                else:
                                    logger.info('Q TAPILMADI UNV SET OLUNMALIDI')
                                    self.set_unv_profile(branch_id,ip,username)
                                    logger.info('UNV SET OLNUNDU')

                                #ready for servingin icindeki profile id ye baxb servisderin qularinda en cox kim gozduyur
                                #onu tapip profilini set elemek lazimdi
                                    
                                

                        
                        
                        
                        # logger.info(servicegroups.service_group.servicegroupbranch_set.last(),"SERVICE GROUPS")
                        # Faize baxib profile set elemeliyem Kenan nan danisdiqin qaydada
                        # Profile set eliyendede men serviese baxib queueni tapip hemin queuenin da profilini set elemeliyem 
                        # frontdan mene gelen profile idin yerine
                    return Response(serializers.data)
                else:
                    # logger.info(Branch.objects.filter(branch_id=branch_id).last().enable,"THISSSSSSSSAA")
                    unv_prof = Branch.objects.filter(branch_id=branch_id).last().unversal_profile_id if Branch.objects.filter(branch_id=branch_id).last() else None
                    branc = Branch.objects.filter(branch_id=branch_id).last()
                    if unv_prof and not branc.reset: # and  branch.reset
                        ap = AllowedProfiles.objects.filter(branch__branch_id = branch_id).last()
                        ap = tuple(ap.profile_id)
                        conn = psycopg2.connect(
                        database="", user='', password='', host=f'{ip}', port= '5432'
                        )
                        cursor = conn.cursor()
                        query_for_profile = f"""
                        update qp_agent.cfm_session
                        set work_profile_id = (select id from qp_agent.cfm_work_profile where orig_id = {unv_prof}  )
                        where branch_id = {branch_id} and work_profile_id in (select id from cfm_work_profile where orig_id in {ap}) and session_state != 'NO_STARTED_USER_SESSION';
                        """

                        cursor.execute(query_for_profile)
                        conn.commit()
                        conn.close()
                        logger.info("profile id must be changed")
                        branc.reset=True
                        branc.save()
                        return Response(['All prof must set unv'],200)
                    else:
                        return Response(['Set unv prof'],400)
        return Response([])

    @staticmethod
    def check_profile(profile_id,branch_id):
        obj = AllowedProfiles.objects.filter(profile_id__overlap=[profile_id],branch__branch_id=branch_id).last() # burda branch idni de qeyd elemek lazimdi
        return obj


    @staticmethod
    def change_prof_id(branch_id,ip,username,prof_id):
        conn = psycopg2.connect(
        database="", user='', password='', host=f'{ip}', port= '5432'
        )
        cursor = conn.cursor()
        query_for_profile = f"""
        UPDATE qp_agent.cfm_session 
        SET  work_profile_id=(select id from cfm_work_profile  where orig_id = {prof_id})
        WHERE user_name = '{username}' and branch_id = {branch_id};
        """

        cursor.execute(query_for_profile)
        conn.commit()
        conn.close()
        logger.info("profile id must be changed232")



    @staticmethod
    def set_unv_profile(branch_id,ip,username,prof_id=None):
        if prof_id:
            GetUserNameAPI.change_prof_id(branch_id,ip,username,prof_id=prof_id)
        elif Branch.objects.filter(branch_id=branch_id):
            unv_profile_id = Branch.objects.get(branch_id=branch_id).unversal_profile_id 
            logger.info(f"{unv_profile_id},'UNV profile idd'")
            if not unv_profile_id:
                logger.info("BURAAA GIRDII RESPONSE QAYITMALIDIKI PROFILE ID YOXDU")
                raise ValidationError("You need set unversal profile id")
            
            GetUserNameAPI.change_prof_id(branch_id,ip,username,prof_id=unv_profile_id)
        else:
            logger.info('XETAA VARR')