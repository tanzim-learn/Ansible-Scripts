#!/usr/bin/python

'''
AUTHOR : Tanzim Rahmathullah (tanzim@netapp.com)

TOOL SUMMARY
--------------
"scale_ontap_objects.py" is a tool that scales an ONTAP cluster with the following objects:
1: Aggregates
2: Vservers
3: LIFs (NFS/CIFS/ISCSI)
4: Export Policy 
5: Export Policy Rules (1 per Export Policy)
6: Volumes
7: Qtrees
8: Luns (1 per volume)
9: Igroups 

HOW TO RUN
----------

python scale_ontap_objects.py



PRE_REQUISITES
--------------

1: Ansible >= 2.6

2: Developed and tested in the following environment
     Red Hat 7.5
     Python 2.7.5

3: netapp-lib >= (2017.10.30) 
   
   Install using ‘pip install netapp-lib’

   -Pip Installation-
	mkdir ~/.pip
	cp /x/eng/globaldc/bin/pip/pip.conf ~/.pip/pip.conf
	chmod 755 ~/.pip/pip.conf
	cp /x/eng/globaldc/bin/pip/get-pip2.py ~/
	chmod 755 ~/get-pip2.py
	python ~/get-pip2.py

4: Ensure that the following are in place
	ONTAP Ansible playbooks (custom) 
	host_vars file (custom)
	hosts file (custom)
	ansible.cfg
	


ANSIBLE COMMANDS
----------------
Create Aggregate:   ansible-playbook create_aggregate.yml --extra-vars "aggregate_name=systemic_aggr1 aggregate_disk_count=5 time_out=300" -vvv

Create SVM:  ansible-playbook create_svm.yml --extra-vars "svm_name=systemic_svm svm_aggregate=tan_aggr " -vvv       

Enable NFS:  ansible-playbook enable_svm_nfs.yml --extra-vars "svm_nfs_name=systemic_svm " -vvv 

Create LIF:  ansible-playbook create_interface.yml --extra-vars "interface_name=systemic_lif home_port_name=e0e home_node=sti60-vsim-ucs133q interface_address:10.10.10.5" -vvv

Create Export Policy: ansible-playbook create_export_policy.yml --extra-vars "export_policy_name=systemic_export_policy export_policy_vserver_name=systemic_svm_1 " -vvv

Create Export Policy Rules: ansible-playbook create_export_policy_rule.yml --extra-vars "export_policy_rule_name=systemic_ep_rule export_policy_rule_vserver_name=systemic_svm_1  " -vvv

Create Volumes (NFS): ansible-playbook create_volume.yml --extra-vars "volume_name=systemic_volume volume_aggregate_name=tan_aggr volume_vserver_name=systemic_svm_1 volume_size=100 volume_size_unit=mb volume_snapshot_percent=40 " -vvv

Create qtrees:  ansible-playbook create_qtree.yml --extra-vars "qtree_name=systemic_qtree qtree_volume_name=systemic_volume qtree_vserver_name=systemic_svm_1 qtree_export_policy=default " -vvv

Create LUN:  ansible-playbook create_lun.yml --extra-vars "lun_name=systemic_lun lun_volume_name=systemic_volume_1 lun_vserver_name=systemic_svm_1 lun_size=5 lun_size_unit=mb " -vvv

Create Igroup: ansible-playbook create_igroup.yml --extra-vars "igroup_name=systemic_igroup igroup_vserver=systemic_svm



'''

import re, os, pprint, datetime, time, sys, subprocess, random, json
#import ansible_runner

##########################
# Variable Declaration
##########################

#Aggregates
aggregate_list = []
aggregate_prefix = "test_run1"
aggregate_disk_count = "5"
aggregate_time_out = "300"
aggregate_count = 3

#Vservers
vserver_list   = [] 
vserver_prefix = "test_vserver"
vserver_aggregate_list = []
vserver_count = 3

#LIF
lif_dict_nfs_cifs = {}
lif_dict_iscsi = {}
lif_prefix_nfs_cifs = "systemic_nas"
lif_prefix_iscsi = "systemic_iscsi"
lif_address = "10.10."
home_port_node_dict = {'sti60-vsim-ucs133q' : 'e0e',
		       'sti60-vsim-ucs133r' : 'e0c',
		       'sti60-vsim-ucs133s' : 'e0d',
		       'sti60-vsim-ucs133t' : 'e0f'
			}
lif_per_vserver_count = 4

#Export Policy
export_policy_list = []
export_policy_prefix = ""
export_policy_count = 0

#Export Policy Rules
export_policy_rule_dict = {}
export_policy_rule_prefix = "systemic_ep"
export_policy_rule_per_vserver_count = 3

#Volumes
volume_dict = {}
volume_prefix = "systemic_volume"
volume_size = "100"
volume_size_unit = "mb"
volume_snapshot_percent = "5"
volume_per_vserver_count = 5

#Qtrees
qtree_dict = {}
qtree_prefix = "systemic_qtree"
qtree_export_policy = "default"
qtree_per_volume_count = 3  

#Luns
lun_dict = {}
lun_prefix = "systemic_lun"
lun_size = "20" # this should be preferably less than the volume size  
lun_size_unit = "mb"
lun_per_vserver_count = 3 #This should be less that the volume per vserver count

#IGroups
igroup_dict = {}
igroup_prefix = "systemic_igroup"
igroup_per_vserver_count = 3


##########################
# Functions
##########################


'''

Function 	: create_aggregates(aggregate_count_local,aggregate_prefix_local,aggregate_disk_count_local,aggregate_time_out_local)
Description	: Create aggregates evenly distributed across all nodes of the cluster
Reference	: subprocess.call(["ansible-playbook", "create_aggregate.yml", "--extra-vars","\"aggregate_name=test_tan aggregate_disk_count=5 time_out=300 \"", "-vvv"])

'''

def create_aggregates(aggregate_count_local,aggregate_prefix_local,aggregate_disk_count_local,aggregate_time_out_local):

	list_aggregate = []
	inc_aggr = 1

	while (inc_aggr <= aggregate_count_local):
		aggregate_args = 'aggregate_name=' + aggregate_prefix_local + '_' + str(inc_aggr)  + ' aggregate_disk_count=' + aggregate_disk_count_local + ' time_out=' + aggregate_time_out_local + ' -vvv'
		subprocess.call(['ansible-playbook', 'create_aggregate.yml', '--extra-vars', aggregate_args,"-vvv"])
		list_aggregate.append( aggregate_prefix_local + '_' + str(inc_aggr))
		inc_aggr = inc_aggr + 1
	return list_aggregate


'''

Function        : create_vservers(vserver_count_local,vserver_prefix_local,aggregate_list_local)
Description     : Create vservers using aggregates across the cluster for the root aggregate creation
Reference       : subprocess.call(["ansible-playbook", "create_svm.yml", "--extra-vars","\"svm_name=systemic_svm svm_aggregate=tan_aggr \"", "-vvv"])

'''

def create_vservers(vserver_count_local,vserver_prefix_local,aggregate_list_local):
	
	list_vserver = []
	inc_vserver = 1  
	
	while (inc_vserver <= vserver_count_local):
		vserver_args = 'svm_name=' + vserver_prefix_local + '_' + str(inc_vserver) + ' svm_aggregate=' + random.choice(aggregate_list_local) + ' -vvv'
		subprocess.call(["ansible-playbook", "create_svm.yml", "--extra-vars", vserver_args,"-vvv"])
		list_vserver.append(vserver_prefix_local + '_' + str(inc_vserver))
		inc_vserver = inc_vserver + 1
	return list_vserver 


'''

Function        : enable_nfs_vservers(vserver_list_local)
Description     : Enable NFS v 4.1 across all teh created vservers
Reference       : subprocess.call(["ansible-playbook", "enable_svm_nfs.yml", "--extra-vars","\"svm_nfs_name=systemic_svm \"", "-vvv"])

'''

def  enable_nfs_vservers(vserver_list_local):
	
	nfs_vserver_list = vserver_list_local
	for nfs_vserver in nfs_vserver_list:
		nfs_vserver_args = 'svm_nfs_name=' + nfs_vserver + ' -vvv'
		subprocess.call(["ansible-playbook", "enable_svm_nfs.yml", "--extra-vars",nfs_vserver_args, "-vvv"])

	return nfs_vserver_list
	

'''

Function        : create_lifs_nfs_cifs(lif_count_local,lif_address_local,home_port_node_dict_local,vserver_list_local)
Description     : Create nfs cifs lifs evenly distributed across the vservers
Reference       : subprocess.call(["ansible-playbook", "create_interface.yml", "--extra-vars","\"interface_name=systemic_lif home_port_name=e0e home_node=sti60-vsim-ucs133q interface_address:10.10.10.5 \"", "-vvv"])

'''
def create_lifs_nfs_cifs(lif_per_vserver_count_local,lif_prefix_local,lif_address_local,home_port_node_dict_local,vserver_list_local):

	dict_lif_nfs_cifs = {}
	#inc_lif = 1
	ip_octet_3 = 1

	for lif_vserver in vserver_list_local:

		#print ("\nVSERVER FOR LIF CREATION : " +lif_vserver)

		list_lif_nfs_cifs = []
		inc_lif = 1
		
		#print ("\n LIF PER VSERVER COUNT : " + str(lif_per_vserver_count_local))

		while (inc_lif <= lif_per_vserver_count_local):
			home_node, home_port  = random.choice(list(home_port_node_dict_local.items()))
			lif_args = 'interface_name=' + lif_prefix_local + '_' + lif_vserver + '_' + str(inc_lif) + ' home_port_name=' + home_port + ' home_node=' + home_node + ' interface_address='+ lif_address_local + str(ip_octet_3) + '.' + str(inc_lif ) + ' interface_vserver_name=' + lif_vserver  + ' interface_protocols=nfs,cifs' + ' -vvv'
			subprocess.call(["ansible-playbook", "create_interface.yml", "--extra-vars",lif_args,"-vvv"])
			list_lif_nfs_cifs.append(lif_prefix_local + "_" + lif_vserver +  '_' + str(inc_lif))
			inc_lif = inc_lif + 1
			
			#print ("\n INC VALUE : " + str(inc_lif))

		dict_lif_nfs_cifs[lif_vserver] = list_lif_nfs_cifs	
		
		ip_octet_3 = ip_octet_3 + 1		
	
	return dict_lif_nfs_cifs



'''

Function        : create_lifs_iscsi(lif_count_local,lif_address_local,home_port_node_dict_local,vserver_list_local)
Description     : Create iscsi lifs evenly distributed across the vservers
Reference       : subprocess.call(["ansible-playbook", "create_interface.yml", "--extra-vars","\"interface_name=systemic_lif home_port_name=e0e home_node=sti60-vsim-ucs133q interface_address:10.10.10.5 \"", "-vvv"])

'''
def create_lifs_iscsi(lif_per_vserver_count_local,lif_prefix_local,lif_address_local,home_port_node_dict_local,vserver_list_local):

        dict_lif_iscsi = {}
        #inc_lif = 1
        ip_octet_3 = 101

        for lif_vserver in vserver_list_local:

                list_lif_iscsi = []
                inc_lif = 1

                while (inc_lif <= lif_per_vserver_count_local):
                        home_node, home_port  = random.choice(list(home_port_node_dict_local.items()))
                        lif_args = 'interface_name=' + lif_prefix_local + '_' + lif_vserver + '_' + str(inc_lif) + ' home_port_name=' + home_port + ' home_node=' + home_node + ' interface_address='+ lif_address_local + str(ip_octet_3) + '.' + str(inc_lif ) + ' interface_vserver_name=' + lif_vserver  + ' interface_protocols=iscsi' + ' -vvv'
                        subprocess.call(["ansible-playbook", "create_interface.yml", "--extra-vars",lif_args,"-vvv"])
                        list_lif_iscsi.append(lif_prefix_local + "_" + lif_vserver + '_' +  str(inc_lif))
                        inc_lif = inc_lif + 1

                dict_lif_iscsi[lif_vserver] = list_lif_iscsi

                ip_octet_3 = ip_octet_3 + 1

        return dict_lif_iscsi


'''

Function        : create_export_policies_rules(export_policy_rule_per_vserver_count_local,export_policy_rule_prefix_local,vserver_list_local)
Description     : Create Export Policies and Rules (1:1) across all the created vservers 
Reference       : subprocess.call(["ansible-playbook", "create_export_policy_rule.yml", "--extra-vars","\"export_policy_rule_name=systemic_ep_rule export_policy_rule_vserver_name=systemic_svm_1 \"", "-vvv"])

'''


def create_export_policies_rules(export_policy_rule_per_vserver_count_local,export_policy_rule_prefix_local,vserver_list_local):
	
	dict_export_policies_rules = {}
	
	for ep_vserver in vserver_list_local:
		
		list_export_policies_rules = []
		inc_ep = 1
		#print ("\nIN EXPORT POLICY RULE : VSERVER " +ep_vserver)	
		while (inc_ep <= export_policy_rule_per_vserver_count_local):

			ep_args = 'export_policy_rule_name=' + export_policy_rule_prefix_local + '_' + ep_vserver + '_' + str(inc_ep) + ' export_policy_rule_vserver_name=' + ep_vserver + ' -vvv'
			subprocess.call(["ansible-playbook", "create_export_policy_rule.yml", "--extra-vars",ep_args,"-vvv"])
			list_export_policies_rules.append( export_policy_rule_prefix_local + '_' + ep_vserver + '_' + str(inc_ep))

			inc_ep = inc_ep + 1

		dict_export_policies_rules[ep_vserver] = list_export_policies_rules


	return dict_export_policies_rules

'''

Function        : create_volumes(volume_per_vserver_count_local,volume_prefix_local,volume_size_local,volume_size_unit_local,volume_snapshot_percent_local,vserver_list_local,aggregate_list_local)
Description     : Create volumes across all vservers
Reference       : subprocess.call(["ansible-playbook", ".create_volume.yml", "--extra-vars","\"volume_name=systemic_volume volume_aggregate_name=tan_aggr volume_vserver_name=systemic_svm_1 volume_size=100 volume_size_unit=mb volume_snapshot_percent=40 \"", "-vvv"])

'''

def  create_volumes(volume_per_vserver_count_local,volume_prefix_local,volume_size_local,volume_size_unit_local,volume_snapshot_percent_local,vserver_list_local,aggregate_list_local):
	
	dict_volumes = {} 

	for volume_vserver in vserver_list_local:
		
		list_volumes = []
		inc_volume = 1

		while (inc_volume <= volume_per_vserver_count_local):
			
			volume_args = 'volume_name=' + volume_prefix_local + '_' + volume_vserver + '_' + str(inc_volume) + ' volume_aggregate_name=' +  random.choice(aggregate_list_local) + ' volume_vserver_name=' + volume_vserver + ' volume_size=' + volume_size_local + ' volume_size_unit=' + volume_size_unit_local + ' volume_snapshot_percent=' + volume_snapshot_percent_local + ' -vvv'
			subprocess.call(["ansible-playbook", "create_volume.yml", "--extra-vars",volume_args,"-vvv"])
			list_volumes.append(volume_prefix_local + '_' + volume_vserver + '_' + str(inc_volume))

			inc_volume = inc_volume + 1

		dict_volumes[volume_vserver] = list_volumes


	return dict_volumes


'''

Function        : create_qtrees(qtree_per_volume_count_local,qtree_prefix_local,qtree_export_policy_local,volume_dict_local)
Description     : subprocess.call(["ansible-playbook", "create_qtree.yml", "--extra-vars","\"qtree_name=systemic_qtree qtree_volume_name=systemic_volume qtree_vserver_name=systemic_svm_1 qtree_export_policy=default \"", "-vvv"])
Reference       : Create qtrees across all created volumes in all created vservers

'''
def create_qtrees(qtree_per_volume_count_local,qtree_prefix_local,qtree_export_policy_local,volume_dict_local):


	dict_qtrees = {}

	for qtree_vserver,qtree_volume_list in volume_dict_local.items():
		dict_qtrees_volumes = {}
		for qtree_volume in qtree_volume_list:
		
			list_qtrees = []
			inc_qtree = 1

			while (inc_qtree <= qtree_per_volume_count_local ):

				qtree_args = 'qtree_name=' + qtree_prefix_local + '_' + qtree_volume + '_' + str(inc_qtree) + ' qtree_volume_name=' + qtree_volume + ' qtree_vserver_name=' + qtree_vserver + ' qtree_export_policy=' + qtree_export_policy_local + ' -vvv'
				subprocess.call(["ansible-playbook", "create_qtree.yml", "--extra-vars",qtree_args,"-vvv"])			
				list_qtrees.append(qtree_prefix_local + '_' + qtree_volume + '_' + str(inc_qtree))

				inc_qtree = inc_qtree + 1	
			
			dict_qtrees_volumes[qtree_volume] =  list_qtrees

		dict_qtrees[qtree_vserver] = dict_qtrees_volumes	

	return dict_qtrees



'''

Function        : create_luns(lun_per_vserver_count_local,lun_prefix_local,lun_size_local,lun_size_unit_local,volume_dict_local)
Description     : subprocess.call(["ansible-playbook", "create_lun.yml", "--extra-vars","\"lun_name=systemic_lun lun_volume_name=systemic_volume_1 lun_vserver_name=systemic_svm_1 lun_size=5 lun_size_unit=mb \"", "-vvv"])
Reference       : Create luns across all created volumes in all created vservers in a 1:1 lun to volume ratio

'''

def  create_luns(lun_per_vserver_count_local,lun_prefix_local,lun_size_local,lun_size_unit_local,volume_dict_local):
	
	dict_luns = {}

	for lun_vserver, lun_volume_list in volume_dict_local.items():

		dict_luns_volumes = {}
		inc_lun = 0

		while (inc_lun < lun_per_vserver_count_local ): 	
			
			#lun_args = 'lun_name=' + lun_prefix_local + '_' + lun_volume_list[inc_lun] + '_' + str(inc_lun) + ' lun_volume_name=' + lun_volume_list[inc_lun] + ' lun_vserver_name=' + lun_vserver + ' lun_size=' + lun_size_local + ' lun_size_unit=' + lun_size_unit_local + ' -vvv'
                        lun_args = 'lun_name=' + lun_prefix_local + '_' + lun_volume_list[inc_lun] + '_1' +  ' lun_volume_name=' + lun_volume_list[inc_lun] + ' lun_vserver_name=' + lun_vserver + ' lun_size=' + lun_size_local + ' lun_size_unit=' + lun_size_unit_local + ' -vvv'
			subprocess.call(["ansible-playbook", "create_lun.yml", "--extra-vars",lun_args,"-vvv"])
                        #list_luns.append(lun_prefix_local + '_' + lun_volume_list[inc_lun] + '_' + str(inc_lun))

			dict_luns_volumes[lun_volume_list[inc_lun]] =  lun_prefix_local + '_' + lun_volume_list[inc_lun] + '_1'

			inc_lun = inc_lun + 1

                dict_luns[lun_vserver] = dict_luns_volumes	

	return dict_luns



'''

Function        : create_igroups(igroup_per_vserver_count_local,igroup_prefix_local,vserver_list_local)
Description     : Create igroups across all the created vservers
Reference       : subprocess.call(["ansible-playbook", "create_igroup.yml", "--extra-vars","\"igroup_name=systemic_igroup igroup_vserver=systemic_svm_1 \"", "-vvv"])

'''


def  create_igroups(igroup_per_vserver_count_local,igroup_prefix_local,vserver_list_local):

        dict_igroups = {}

        for igroup_vserver in vserver_list_local:

                list_igroups = []
                inc_igroup = 1

                while (inc_igroup <= igroup_per_vserver_count_local):

                        igroup_args = 'igroup_name=' + igroup_prefix_local + '_' + igroup_vserver + '_' + str(inc_igroup) + ' igroup_vserver=' + igroup_vserver + ' -vvv'
                        subprocess.call(["ansible-playbook", "create_igroup.yml", "--extra-vars",igroup_args,"-vvv"])
                        list_igroups.append( igroup_prefix_local + '_' + igroup_vserver + '_' + str(inc_igroup))

                        inc_igroup = inc_igroup + 1

                dict_igroups[igroup_vserver] = list_igroups


        return dict_igroups






#########################
# Main Code
#########################


if __name__ == '__main__':

	print ("################################   Starting ONTAP scale operations   ################################")


	# AGGREGATE CREATION	

	print ("--------------------------------   Creating Aggregates   ---------------------------------------")
	#aggregate_args = 'aggregate_name=' + aggregate_prefix + ' aggregate_disk_count=' + aggregate_disk_count + ' time_out=' + aggregate_time_out + ' -vvv' 
        #subprocess.call(['ansible-playbook', 'create_aggregate.yml', '--extra-vars', aggregate_args])
	aggregate_list = create_aggregates(aggregate_count,aggregate_prefix,aggregate_disk_count,aggregate_time_out)
	print ("Number of Aggregates created : " + str(len(aggregate_list)))
	#print(*aggregate_list, sep = "\n")
	for aggr_index in range(len(aggregate_list)):
		print (aggregate_list[aggr_index] + "\n")

	# VSERVER CREATION

	print ("--------------------------------   Creating Vservers   ---------------------------------------")
	vserver_list = create_vservers(vserver_count,vserver_prefix,aggregate_list)
	print ("Number of Vservers created : " + str(len(vserver_list)) )
	#print (*vserver_list, sep= "\n")
	for vserver_index in range(len(vserver_list)):
		print (vserver_list[vserver_index] + "\n")

	# ENABLE NFS

	print ("--------------------------------   Enabling NFS v 4.1 on Vservers   ---------------------------------------")
        vserver_list = enable_nfs_vservers(vserver_list)
        #print (*vserver_list, sep= "\n")
        for vserver_nfs_index in range(len(vserver_list)):
                print (vserver_list[vserver_nfs_index] + "\n")

	# LIF CREATION - NFS CIFS

	print ("--------------------------------   Creating NFS CIFS LIFs   ---------------------------------------")
	lif_dict_nfs_cifs = create_lifs_nfs_cifs(lif_per_vserver_count,lif_prefix_nfs_cifs,lif_address,home_port_node_dict,vserver_list)
        #print (*lif_list, sep= "\n")
	print(json.dumps(lif_dict_nfs_cifs, indent=4, sort_keys=True))


	 # LIF CREATION - ISCSI

        print ("--------------------------------   Creating ISCSI LIFs   ---------------------------------------")
        lif_dict_iscsi = create_lifs_iscsi(lif_per_vserver_count,lif_prefix_iscsi,lif_address,home_port_node_dict,vserver_list)
        #print (*lif_list, sep= "\n")
        print(json.dumps(lif_dict_iscsi, indent=4, sort_keys=True))



	# EXPORT POLICY CREATION - Skipping this as Export Policy Rule creates an Export Policy too


	# EXPORT POLICY RULE CREATION

	print ("--------------------------------   Creating Export Policies and Rules   ---------------------------------------")
        export_policy_rule_dict = create_export_policies_rules(export_policy_rule_per_vserver_count,export_policy_rule_prefix,vserver_list)
        print(json.dumps(export_policy_rule_dict, indent=4, sort_keys=True))

	# VOLUME CREATION

	print ("--------------------------------  Creating Volumes   ---------------------------------------")
        volume_dict = create_volumes(volume_per_vserver_count,volume_prefix,volume_size,volume_size_unit,volume_snapshot_percent,vserver_list,aggregate_list)
        print(json.dumps(volume_dict, indent=4, sort_keys=True))


	# QTREE CREATION

	print ("--------------------------------  Creating Qtrees   ---------------------------------------")
        qtree_dict = create_qtrees(qtree_per_volume_count,qtree_prefix,qtree_export_policy,volume_dict)
        print(json.dumps(qtree_dict, indent=4, sort_keys=True))



	# LUN CREATION

	print ("--------------------------------  Creating Luns   ---------------------------------------")
       	lun_dict = create_luns(lun_per_vserver_count,lun_prefix,lun_size,lun_size_unit,volume_dict)
        print(json.dumps(lun_dict, indent=4, sort_keys=True))	




	# IGROUP CREATION	


	print ("--------------------------------  Creating IGroups   ---------------------------------------")
        igroup_dict = create_igroups(igroup_per_vserver_count,igroup_prefix,vserver_list)
        print(json.dumps(igroup_dict, indent=4, sort_keys=True))





'''

	#Create Aggregate
	subprocess.call(["ansible-playbook", "create_aggregate.yml", "--extra-vars","\"aggregate_name=test_tan aggregate_disk_count=5 time_out=300 \"", "-vvv"])

	#Create SVM
	subprocess.call(["ansible-playbook", "create_svm.yml", "--extra-vars","\"svm_name=systemic_svm svm_aggregate=tan_aggr \"", "-vvv"])

	#Enable NFS
	subprocess.call(["ansible-playbook", "enable_svm_nfs.yml", "--extra-vars","\"svm_nfs_name=systemic_svm \"", "-vvv"])
	
	#Create LIF
	subprocess.call(["ansible-playbook", "create_interface.yml", "--extra-vars","\"interface_name=systemic_lif home_port_name=e0e home_node=sti60-vsim-ucs133q interface_address:10.10.10.5 \"", "-vvv"])

	#Create Export Policy
	subprocess.call(["ansible-playbook", "create_export_policy.yml", "--extra-vars","\"export_policy_name=systemic_export_policy export_policy_vserver_name=systemic_svm_1 \"", "-vvv"])

	#Create Export Policy Rules
	subprocess.call(["ansible-playbook", "create_export_policy_rule.yml", "--extra-vars","\"export_policy_rule_name=systemic_ep_rule export_policy_rule_vserver_name=systemic_svm_1 \"", "-vvv"])

	#Create Volumes
	subprocess.call(["ansible-playbook", ".create_volume.yml", "--extra-vars","\"volume_name=systemic_volume volume_aggregate_name=tan_aggr volume_vserver_name=systemic_svm_1 volume_size=100 volume_size_unit=mb volume_snapshot_percent=40 \"", "-vvv"])

	#Create Qtrees
	subprocess.call(["ansible-playbook", "create_qtree.yml", "--extra-vars","\"qtree_name=systemic_qtree qtree_volume_name=systemic_volume qtree_vserver_name=systemic_svm_1 qtree_export_policy=default \"", "-vvv"])
	
	#Create LUN
	subprocess.call(["ansible-playbook", "create_lun.yml", "--extra-vars","\"lun_name=systemic_lun lun_volume_name=systemic_volume_1 lun_vserver_name=systemic_svm_1 lun_size=5 lun_size_unit=mb \"", "-vvv"])

	#Create Igroup
	subprocess.call(["ansible-playbook", "create_igroup.yml", "--extra-vars","\"igroup_name=systemic_igroup igroup_vserver=systemic_svm_1 \"", "-vvv"])
	
	#Create Snapshot


	#Create CIFS Shares


	#Create Clones


	#Create IPSpace


	#Create Broadcast Domain

'''
