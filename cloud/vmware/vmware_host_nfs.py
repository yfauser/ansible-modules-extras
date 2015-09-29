#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2015 VMware, Inc. All Rights Reserved.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: vmware_host_nfs
short_description: Mount or Unmount a NFS Datastore from a ESXi Host
description:
    - Mount or Unmount a NFS Datastore from a ESXi Host
version_added: 2.0
author: "Yves Fauser (@yfauser)"
notes:
    - Tested on vSphere 5.5
requirements:
    - "python >= 2.6"
    - PyVmomi
options:
    hostname:
        description:
            - The hostname or IP address of the vSphere vCenter API server
        required: True
    username:
        description:
            - The username of the vSphere vCenter
        required: True
        aliases: ['user', 'admin']
    password:
        description:
            - The password of the vSphere vCenter
        required: True
        aliases: ['pass', 'pwd']
    esxi_hostname:
        description:
            - The ESXi hostname
        required: True
    datastore_name:
        description:
            - The name of the NFS Datastore as seen in vCenter
        required: True
    nfs_server:
        description:
            - The Hostname, FQDN or IP Address of the NFS Server to mount the Host to
        required: True
    nfs_path:
        description:
            - The path of the share exposed by the NFS Server (e.g. /export/)
        required: True
    nfs_readonly:
        description:
            - Defines if the Datastore should be mounted as Read Only
        required: False
        default: False
    state:
        description:
            - If the datastore should be mounted or unmounted on the Host
        choices: ['present', 'absent']
        required: True
'''

EXAMPLES = '''
# Example vmware_host_nfs command from Ansible Playbooks
- name: Mount NFS datastore to host
  vmware_host_nfs:
    state: present
    hostname: vcenter_ip_or_hostname
    username: vcenter_username
    password: vcenter_password
    esxi_hostname: esxi_hostname_as_listed_in_vcenter
    datastore_name: name_of_target_datastore
    nfs_server: hostname_fqdn_or_ip_of_nfs_server
    nfs_path: path_on_nfs_server
'''

try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


def mount_nfsvolume(host_mo, nfs_server, nfs_path, local_path, nfs_readonly):
    host_mo = host_mo
    nfs_ds_spec = vim.host.NasVolume.Specification()
    nfs_ds_spec.remoteHost = nfs_server
    nfs_ds_spec.remotePath = nfs_path
    nfs_ds_spec.localPath = local_path
    if nfs_readonly:
        nfs_ds_spec.accessMode = 'readOnly'
    else:
        nfs_ds_spec.accessMode = 'readWrite'

    result = host_mo.configManager.datastoreSystem.CreateNasDatastore(nfs_ds_spec)

    return True, result


def unmount_nfsvolume(host_mo, datastore_mo):
    result = host_mo.configManager.datastoreSystem.RemoveDatastore(datastore_mo)
    return True, result


def state_mount_datastore(module):
    nfs_server = module.params['nfs_server']
    nfs_path = module.params['nfs_path']
    local_path = module.params['datastore_name']
    nfs_readonly = module.params['nfs_readonly']
    host_mo = module.params['host_mo']
    changed = True
    result = None

    if not module.check_mode:
        changed, result = mount_nfsvolume(host_mo, nfs_server, nfs_path, local_path, nfs_readonly)

    module.exit_json(changed=changed, result=str(result))


def state_unmount_datastore(module):
    host_mo = module.params['host_mo']
    datastore_mo = module.params['datastore_mo']
    changed = True
    result = None

    if not module.check_mode:
        changed, result = unmount_nfsvolume(host_mo, datastore_mo)

    module.exit_json(changed=changed, result=str(result))


def state_exit_unchanged(module):
    module.exit_json(changed=False)


def check_datastore_status(module):
    datastore_name = module.params['datastore_name']
    esxi_hostname = module.params['esxi_hostname']
    content = connect_to_api(module)
    module.params['content'] = content
    host_mo = find_hostsystem_by_name(content, esxi_hostname)
    module.params['host_mo'] = host_mo
    host_datastores = host_mo.configManager.datastoreSystem.datastore

    for host_datastore in host_datastores:
        if host_datastore.name == datastore_name:
            module.params['datastore_mo'] = host_datastore
            return 'present'
        else:
            return 'absent'


def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(dict(esxi_hostname=dict(required=True, type='str'),
                              datastore_name=dict(required=True, type='str'),
                              nfs_server=dict(required=True, type='str'),
                              nfs_path=dict(required=True, type='str'),
                              nfs_readonly=dict(default=False, choices=[True, False], type='bool'),
                              state=dict(default='present', choices=['present', 'absent'], type='str')))

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_PYVMOMI:
        module.fail_json(msg='pyvmomi is required for this module')

    try:
        datastore_states = {
            'absent': {
                'present': state_unmount_datastore,
                'absent': state_exit_unchanged
            },
            'present': {
                'present': state_exit_unchanged,
                'absent': state_mount_datastore
            }
        }
        datastore_states[module.params['state']][check_datastore_status(module)](module)
    except vmodl.RuntimeFault as runtime_fault:
        module.fail_json(msg=runtime_fault.msg)
    except vmodl.MethodFault as method_fault:
        module.fail_json(msg=method_fault.msg)
    except Exception as e:
        module.fail_json(msg=str(e))


from ansible.module_utils.vmware import *
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
