import errno

from middlewared.service import CallError, Service

from .state_utils import IX_APPS_MOUNT_PATH, Status


class DockerFilesystemManageService(Service):

    class Config:
        namespace = 'docker.fs_manage'
        private = True

    async def common_func(self, mount):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            try:
                if mount:
                    await self.middleware.call('zfs.dataset.mount', docker_ds, {'recursive': True, 'force_mount': True})
                else:
                    await self.middleware.call('zfs.dataset.umount', docker_ds, {'force': True})
                return await self.middleware.call('catalog.sync')
            except Exception as e:
                await self.middleware.call(
                    'docker.state.set_status', Status.FAILED.value,
                    f'Failed to {"mount" if mount else "umount"} {docker_ds!r}: {e}',
                )
                raise

    async def mount(self):
        return await self.common_func(True)

    async def umount(self):
        return await self.common_func(False)

    async def ix_apps_is_mounted(self, dataset_to_check=None):
        """
        This will tell us if some dataset is mounted on /mnt/.ix-apps or not.
        """
        try:
            fs_details = await self.middleware.call('filesystem.statfs', IX_APPS_MOUNT_PATH)
        except CallError as e:
            if e.errno == errno.ENOENT:
                return False
            raise

        if fs_details['source'].startswith('boot-pool/'):
            return False

        if dataset_to_check:
            return fs_details['source'] == dataset_to_check

        return True
