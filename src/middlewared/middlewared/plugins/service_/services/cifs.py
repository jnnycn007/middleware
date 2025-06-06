from .base import SimpleService


class CIFSService(SimpleService):
    name = "cifs"
    reloadable = True

    etc = ["smb"]

    systemd_unit = "smbd"

    async def start(self):
        if not await self.middleware.call("smb.configure_wait"):
            return

        await self._systemd_unit("smbd", "start")

    async def after_start(self):
        # We reconfigure mdns (add SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)

    async def stop(self):
        await self._systemd_unit("smbd", "stop")

    async def after_stop(self):
        # reconfigure mdns (remove SMB service, possibly also ADISK)
        await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)
