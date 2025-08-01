import pathlib

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetDetailsArgs,
    PoolDatasetDetailsResult,
)
from middlewared.plugins.zfs_.utils import zvol_path_to_name, TNUserProp
from middlewared.service import Service, private
from middlewared.utils.filesystem.stat_x import statx
from middlewared.utils.mount import getmntinfo


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @private
    def build_filters_and_options(self):
        options = {
            'extra': {
                'retrieve_user_props': True,
                'flat': True,
                'order_by': 'name',
                'properties': [
                    'atime',
                    'casesensitivity',
                    'readonly',
                    'used',
                    'available',
                    'usedbysnapshots',
                    'usedbydataset',
                    'usedbychildren',
                    'refquota',
                    'origin',
                    TNUserProp.REFQUOTA_CRIT.value,
                    TNUserProp.REFQUOTA_WARN.value,
                    'quota',
                    TNUserProp.QUOTA_CRIT.value,
                    TNUserProp.QUOTA_WARN.value,
                    'refreservation',
                    'reservation',
                    'mountpoint',
                    'mounted',
                    'encryption',
                    'encryptionroot',
                    'keyformat',
                    'keystatus',
                    'volsize',
                    'sync',
                    'compression',
                    'compressratio',
                    'dedup',
                ],
                'snapshots_count': True,
            }
        }
        return [], options

    @api_method(PoolDatasetDetailsArgs, PoolDatasetDetailsResult, roles=['DATASET_READ'])
    def details(self):
        """
        Retrieve all dataset(s) details outlining any
        services/tasks which might be consuming them.
        """
        filters, options = self.build_filters_and_options()
        datasets = self.middleware.call_sync('pool.dataset.query', filters, options)
        mnt_info = getmntinfo()
        info = self.build_details(mnt_info)
        for dataset in datasets:
            self.collapse_datasets(dataset, info, mnt_info)

        return datasets

    @private
    def normalize_dataset(self, dataset, info, mnt_info):
        dataset['thick_provisioned'] = any((dataset['reservation']['value'], dataset['refreservation']['value']))
        dataset['nfs_shares'] = self.get_nfs_shares(dataset, info['nfs'])
        dataset['smb_shares'] = self.get_smb_shares(dataset, info['smb'])
        dataset['iscsi_shares'] = self.get_iscsi_shares(dataset, info['iscsi'])
        dataset['vms'] = self.get_vms(dataset, info['vm'])
        dataset['apps'] = self.get_apps(dataset, info['app'])
        dataset['virt_instances'] = self.get_virt_instances(dataset, info['virt_instance'])
        dataset['replication_tasks_count'] = self.get_repl_tasks_count(dataset, info['repl'])
        dataset['snapshot_tasks_count'] = self.get_snapshot_tasks_count(dataset, info['snap'])
        dataset['cloudsync_tasks_count'] = self.get_cloudsync_tasks_count(dataset, info['cloud'])
        dataset['rsync_tasks_count'] = self.get_rsync_tasks_count(dataset, info['rsync'])

    @private
    def collapse_datasets(self, dataset, info, mnt_info):
        self.normalize_dataset(dataset, info, mnt_info)
        for child in dataset.get('children', []):
            self.collapse_datasets(child, info, mnt_info)

    @private
    def get_mount_info(self, path, mntinfo):
        mount_info = {}
        if path.startswith('zvol/'):
            path = f'/dev/{path}'

        try:
            mnt_id = statx(path).stx_mnt_id
        except Exception:
            # path deleted/umounted/locked etc
            pass
        else:
            if mnt_id in mntinfo:
                mount_info = mntinfo[mnt_id]

        return mount_info

    @private
    def build_details(self, mntinfo):
        results = {
            'iscsi': [], 'nfs': [], 'smb': [],
            'repl': [], 'snap': [], 'cloud': [],
            'rsync': [], 'vm': [], 'app': [],
            'virt_instance': [],
        }

        # iscsi
        t_to_e = self.middleware.call_sync('iscsi.targetextent.query')
        t = {i['id']: i for i in self.middleware.call_sync('iscsi.target.query')}
        e = {i['id']: i for i in self.middleware.call_sync('iscsi.extent.query')}
        for i in filter(lambda x: x['target'] in t and t[x['target']]['groups'] and x['extent'] in e, t_to_e):
            """
            1. make sure target's and extent's id exist in the target to extent table
            2. make sure the target has `groups` entry since, without it, it's impossible
                that it's being shared via iscsi
            """
            results['iscsi'].append({
                'extent': e[i['extent']],
                'target': t[i['target']],
                'mount_info': self.get_mount_info(e[i['extent']]['path'], mntinfo),
            })

        # nfs and smb
        for key in ('nfs', 'smb'):
            for share in self.middleware.call_sync(f'sharing.{key}.query'):
                share['mount_info'] = self.get_mount_info(share['path'], mntinfo)
                results[key].append(share)

        # replication
        options = {'prefix': 'repl_'}
        for task in self.middleware.call_sync('datastore.query', 'storage.replication', [], options):
            # replication can only be configured on a dataset so getting mount info is unnecessary
            results['repl'].append(task)

        # snapshots
        for task in self.middleware.call_sync('datastore.query', 'storage.task', [], {'prefix': 'task_'}):
            # snapshots can only be configured on a dataset so getting mount info is unnecessary
            results['snap'].append(task)

        # cloud sync
        for task in self.middleware.call_sync('datastore.query', 'tasks.cloudsync'):
            task['mount_info'] = self.get_mount_info(task['path'], mntinfo)
            results['cloud'].append(task)

        # rsync
        for task in self.middleware.call_sync('rsynctask.query'):
            task['mount_info'] = self.get_mount_info(task['path'], mntinfo)
            results['rsync'].append(task)

        # vm
        for vm in self.middleware.call_sync('vm.device.query', [['attributes.dtype', 'in', ['RAW', 'DISK']]]):
            if vm['attributes']['dtype'] == 'DISK':
                # disk type is always a zvol
                vm['zvol'] = zvol_path_to_name(vm['attributes']['path'])
            else:
                # raw type is always a file
                vm['mount_info'] = self.get_mount_info(vm['attributes']['path'], mntinfo)

            results['vm'].append(vm)

        for app in self.middleware.call_sync('app.query'):
            for path_config in filter(
                lambda p: p.get('source', '').startswith('/mnt/') and not p['source'].startswith('/mnt/.ix-'),
                app['active_workloads']['volumes']
            ):
                results['app'].append({
                    'name': app['name'],
                    'path': path_config['source'],
                    'mount_info': self.get_mount_info(path_config['source'], mntinfo),
                })

        # virt instance
        for instance in self.middleware.call_sync('virt.instance.query'):
            for device in self.middleware.call_sync('virt.instance.device_list', instance['id']):
                if device['dev_type'] != 'DISK':
                    continue
                if not device['source']:
                    continue
                device['instance'] = instance['id']
                if device['source'].startswith('/dev/zvol/'):
                    # disk type is always a zvol
                    device['zvol'] = zvol_path_to_name(device['source'])
                else:
                    # raw type is always a file
                    device['mount_info'] = self.get_mount_info(device['source'], mntinfo)
                results['virt_instance'].append(device)

        return results

    @private
    def get_nfs_shares(self, ds, nfsshares):
        nfs_shares = []
        for share in nfsshares:
            if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
                nfs_shares.append({'enabled': share['enabled'], 'path': share['path']})

        return nfs_shares

    @private
    def get_smb_shares(self, ds, smbshares):
        smb_shares = []
        for share in smbshares:
            if share['path'] == ds['mountpoint'] or share['mount_info'].get('mount_source') == ds['id']:
                smb_shares.append({
                    'enabled': share['enabled'],
                    'path': share['path'],
                    'share_name': share['name']
                })

        return smb_shares

    @private
    def get_iscsi_shares(self, ds, iscsishares):
        iscsi_shares = []
        for share in iscsishares:
            if share['extent']['type'] == 'DISK' and ds['type'] == 'VOLUME':
                if zvol_path_to_name(f"/dev/{share['extent']['path']}") == ds['id']:
                    # we store extent information prefixed with `zvol/` (i.e. zvol/tank/zvol01).
                    iscsi_shares.append({
                        'enabled': share['extent']['enabled'],
                        'type': 'DISK',
                        'path': f'/dev/{share["extent"]["path"]}',
                    })
            elif share['extent']['type'] == 'FILE' and ds['type'] == 'FILESYSTEM':
                if share['mount_info'].get('mount_source') == ds['id']:
                    # this isn't common but possible, you can share a "file"
                    # via iscsi which means it's not a dataset but a file inside
                    # a dataset so we need to find the source dataset for the file
                    iscsi_shares.append({
                        'enabled': share['extent']['enabled'],
                        'type': 'FILE',
                        'path': share['extent']['path'],
                    })

        return iscsi_shares

    @private
    def get_repl_tasks_count(self, ds, repltasks):
        count = 0
        for repl in filter(lambda x: x['direction'] == 'PUSH', repltasks):
            # we only care about replication tasks that are configured to push
            for src_ds in filter(lambda x: x == ds['id'], repl['source_datasets']):
                count += 1

        return count

    @private
    def get_snapshot_tasks_count(self, ds, snaptasks):
        return len([i for i in snaptasks if i['dataset'] == ds['id']])

    @private
    def get_cloudsync_tasks_count(self, ds, cldtasks):
        return self._get_push_tasks_count(ds, cldtasks)

    @private
    def get_rsync_tasks_count(self, ds, rsynctasks):
        return self._get_push_tasks_count(ds, rsynctasks)

    def _get_push_tasks_count(self, ds, tasks):
        count = 0
        if ds['mountpoint']:
            for i in filter(lambda x: x['direction'] == 'PUSH', tasks):
                # we only care about cloud sync tasks that are configured to push
                if pathlib.Path(ds['mountpoint']).is_relative_to(i['path']):
                    count += 1

        return count

    @private
    def get_vms(self, ds, _vms):
        vms = []
        vms_mapping = {vm['id']: vm for vm in self.middleware.call_sync('datastore.query', 'vm.vm')}
        for i in _vms:
            if (
                'zvol' in i and i['zvol'] == ds['id'] or
                i['attributes']['path'] == ds['mountpoint'] or
                i.get('mount_info', {}).get('mount_source') == ds['id']
            ):
                vms.append({'name': vms_mapping[i['vm']]['name'], 'path': i['attributes']['path']})

        return vms

    @private
    def get_virt_instances(self, ds, _instances):
        instances = []
        for i in _instances:
            if (
                'zvol' in i and i['zvol'] == ds['id'] or
                i['source'] == ds['mountpoint'] or
                i.get('mount_info', {}).get('mount_source') == ds['id']
            ):
                instances.append({'name': i['instance'], 'path': i['source']})

        return instances

    @private
    def get_apps(self, ds, _apps):
        apps = []
        for app in _apps:
            if app['path'] == ds['mountpoint'] or app['mount_info'].get('mount_source') == ds['id']:
                apps.append({'name': app['name'], 'path': app['path']})

        return apps
