from usr.audio_control import AudioManager
from usr.cloud import AliYunManage
from usr.common import ConfigStoreManager, Abstract
from usr.led_control import RLight, GLight, BLight
from usr.ota_control import OTAManager
from usr.mgr import FactoryManager, DeviceInfoManager, UartManager, KeypadManager,\
DeviceActionManager,OrderManager,ChargeManager,LteNetManager,CloudHornManager

class App(object):
    def __init__(self):
        self.managers = []

    def append_manager(self, manager):
        if isinstance(manager, Abstract):
            manager.post_processor_after_instantiation()
            self.managers.append(manager)
        return self

    def start(self):
        for manager in self.managers:
            manager.post_processor_before_initialization()
            manager.initialization()
            manager.post_processor_after_initialization()

if __name__ == '__main__':
    app = App()
    # app 注册

    app.append_manager(ConfigStoreManager())
    app.append_manager(AudioManager())
    app.append_manager(RLight())
    app.append_manager(GLight())
    app.append_manager(BLight())
    app.append_manager(OTAManager())
    app.append_manager(KeypadManager())
    app.append_manager(DeviceInfoManager())
    app.append_manager(UartManager())
    app.append_manager(DeviceActionManager())
    app.append_manager(OrderManager())
    app.append_manager(ChargeManager())
    app.append_manager(AliYunManage())
    app.append_manager(LteNetManager())
    app.append_manager(CloudHornManager())
    app.append_manager(FactoryManager())

    # 启动
    app.start()