#!/usr/bin/env python3

import sys, os
import logging
import queue
import hashlib
import binascii

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from ble import (
    get_adapter_address,
    find_gatt_object,
    remove_all_devices,
    Advertisement,
    Characteristic,
    Service,
    Application,
    Descriptor,
    Agent,
)

import struct
import array
from enum import Enum
import sys
try:
    # python 3
    from gi.repository import GLib as GObject
except ImportError:
    # python 2
    import gobject as GObject



logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

mainloop = None

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class NotPermittedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotPermitted"


class InvalidValueLengthException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.InvalidValueLength"


class FailedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.Failed"


def register_app_cb():
    logger.info("GATT application registered")


def register_app_error_cb(error):
    logger.critical("Failed to register application: " + str(error))
    mainloop.quit()

def dbus_system_reboot():
    # dbus-send --system --print-reply --dest=org.freedesktop.login1 /org/freedesktop/login1 "org.freedesktop.login1.Manager.Reboot" boolean:true
    bus = dbus.SystemBus()
    systemd = bus.get_object(
        'org.freedesktop.login1',
        '/org/freedesktop/login1'
    )
    manager = dbus.Interface(
        systemd,
        'org.freedesktop.login1.Manager'
    )
    manager.Reboot(True)

def dbus_systemd_restart_service(unit_name):
    # gdbus call --system --dest org.freedesktop.systemd1 --object-path /org/freedesktop/systemd1 --method org.freedesktop.systemd1.Manager.RestartUnit sshd replace

    bus = dbus.SystemBus()
    systemd = bus.get_object(
        'org.freedesktop.systemd1',
        '/org/freedesktop/systemd1'
    )
    manager = dbus.Interface(
        systemd,
        'org.freedesktop.systemd1.Manager'
    )
    manager.RestartUnit(unit_name, 'replace')

def wpa_psk(ssid, passphrase):
    dk = hashlib.pbkdf2_hmac('sha1', str.encode(passphrase), str.encode(ssid), 4096, 32)
    return (binascii.hexlify(dk).decode('utf8'))

def rpi_wpa_supplicant_config(ssid, passphrase):
    if passphrase == "":
        return'''ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    scan_ssid=1
    ssid="{ssid}"
    key_mgmt=NONE
}}
'''.format(ssid=ssid)
    else:
        psk = wpa_psk(ssid, passphrase)
        return'''ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    scan_ssid=1
    ssid="{ssid}"
    psk={psk}
}}
'''.format(ssid=ssid, psk=psk)

class WifiConfigS1Service(Service):
    """
    Dummy test service that provides characteristics and descriptors that
    exercise various API functionality.

    """

    ESPRESSO_SVC_UUID = "a39955e0-72e5-11ec-90d6-0242ac120003"
    queue = queue.Queue()

    def __init__(self, bus, index):
        Service.__init__(self, bus, index, self.ESPRESSO_SVC_UUID, True)
        self.add_characteristic(SSIDCharacteristic(bus, 0, self))
        self.add_characteristic(PassphraseCharacteristic(bus, 1, self))
        self.add_characteristic(CommandCharacteristic(bus, 2, self))


class SSIDCharacteristic(Characteristic):
    uuid = "a39955e1-72e5-11ec-90d6-0242ac120003"
    description = b"Get/set SSID"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            # self.uuid, ["encrypt-read", "encrypt-write"],
            self.uuid, ["read", "write"],
            service,
        )
        self.value = []
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        logger.debug("SSID Read: " + repr(self.value))
        return self.value

    def WriteValue(self, value, options):
        logger.debug("SSID Write: " + repr(value))
        self.value = value
        self.service.queue.put(dict(ssid=bytes(value).decode('utf8')))


class PassphraseCharacteristic(Characteristic):
    uuid = "a39955e2-72e5-11ec-90d6-0242ac120003"
    description = b"Get/set Passphrase"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            # self.uuid, ["encrypt-read", "encrypt-write"],
            self.uuid, ["read", "write"],
            service,
        )

        self.value = []
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        logger.info("Passphrase read: " + repr(self.value))
        return self.value

    def WriteValue(self, value, options):
        logger.info("Passphrase Write: " + repr(value))
        self.value = value
        self.service.queue.put(dict(passphrase=bytes(value).decode('utf8')))

class CommandCharacteristic(Characteristic):
    uuid = "a39955e3-72e5-11ec-90d6-0242ac120003"
    description = b"Commit change"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            # self.uuid, ["secure-read", "secure-write"],
            self.uuid, ["read", "write"],
            service,
        )

        self.value = []
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        logger.info("Last commit: " + repr(self.value))
        return self.value

    def WriteValue(self, value, options):
        logger.info("Commit: " + repr(value))
        self.value = value
        self.service.queue.put(dict(cmd=bytes(value).decode('utf8')))

class CharacteristicUserDescriptionDescriptor(Descriptor):
    """
    Writable CUD descriptor.
    """

    CUD_UUID = "2901"

    def __init__(
        self, bus, index, characteristic,
    ):

        self.value = array.array("B", characteristic.description)
        self.value = self.value.tolist()
        Descriptor.__init__(self, bus, index, self.CUD_UUID, ["read"], characteristic)

    def ReadValue(self, options):
        return self.value

    def WriteValue(self, value, options):
        if not self.writable:
            raise NotPermittedException()
        self.value = value


class WifiConfigAdvertisement(Advertisement):
    def __init__(self, bus, index, local_name='WifiConfig'):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_manufacturer_data(
            0xFFFF, [0x70, 0x74],
        )
        self.add_service_uuid(WifiConfigS1Service.ESPRESSO_SVC_UUID)

        self.add_local_name(local_name)
        self.include_tx_power = True


def register_ad_cb():
    logger.info("Advertisement registered")


def register_ad_error_cb(error):
    logger.critical("Failed to register advertisement: " + str(error))
    mainloop.quit()

def property_changed(interface, changed, invalidated, path):
	iface = interface[interface.rfind(".") + 1:]
	for name, value in changed.items():
		val = str(value)
		logger.info("{%s.PropertyChanged} [%s] %s = %s" % (iface, path, name,
									val))


AGENT_PATH = "/com/vinh/agent"


def main():
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    # get the system bus
    bus = dbus.SystemBus()

    bus.add_signal_receiver(property_changed, bus_name="org.bluez",
			dbus_interface="org.freedesktop.DBus.Properties",
			signal_name="PropertiesChanged",
			path_keyword="path")

    # remove all device
    remove_all_devices()

    gatt_object = find_gatt_object()
    adapter_props = dbus.Interface(gatt_object, "org.freedesktop.DBus.Properties")

    # powered property on the controller to on
    adapter_props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(1))

    # Get manager objs
    service_manager = dbus.Interface(gatt_object, GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(gatt_object, LE_ADVERTISING_MANAGER_IFACE)

    address = get_adapter_address(gatt_object.object_path)
    logger.info("Adapter address: {}".format(address))
    local_name = "rpz-" + str.lower(address[12:14]) + '.' + str.lower(address[15:17])
    advertisement = WifiConfigAdvertisement(bus, 0, local_name)
    obj = bus.get_object(BLUEZ_SERVICE_NAME, "/org/bluez")

    # agent = Agent(bus, AGENT_PATH)

    app = Application(bus)
    service = WifiConfigS1Service(bus, 2)
    app.add_service(service)

    # agent_manager = dbus.Interface(obj, "org.bluez.AgentManager1")
    # agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    # agent_manager.RequestDefaultAgent(AGENT_PATH)

    ad_manager.RegisterAdvertisement(
        advertisement.get_path(),
        {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb,
    )

    logger.info("Registering GATT application...")

    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=register_app_cb,
        error_handler=[register_app_error_cb],
    )

    mainloop = GObject.MainLoop()
    context = mainloop.get_context()
    ssid = ''
    passphrase = ''
    while mainloop is not None:
        if context.pending():
            context.iteration()
        while not service.queue.empty():
            data = service.queue.get(False)
            if 'ssid' in data:
                ssid = data['ssid']
            elif 'passphrase' in data:
                passphrase = data['passphrase']
            elif 'cmd' in data:
                if data['cmd'] == 'commit':
                    logger.info("commit ssid: {ssid}, passphrase: {passphrase}".format(ssid=ssid, passphrase=passphrase))
                    with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
                        config=rpi_wpa_supplicant_config(ssid, passphrase)
                        f.write(config)
                        dbus_systemd_restart_service('networking.service')
                        dbus_systemd_restart_service('dhcpcd.service')
                        dbus_systemd_restart_service('wpa_supplicant.service')
                    ssid = ''
                    passphrase = ''
                elif data['cmd'] == 'reboot':
                    logger.info("Rebooting...")
                    dbus_system_reboot()
                else:
                    logger.info("Unknown command: " + data['cmd'])
    # mainloop.run()
    # ad_manager.UnregisterAdvertisement(advertisement)
    # dbus.service.Object.remove_from_connection(advertisement)


if __name__ == "__main__":
    main()
