import sim
import utime
import modem
import net
import _thread
import dataCall
import osTimer
import checkNet
from queue import Queue
from usr.common import get_logger
from usr.common import Abstract
from usr.common import Lock
from usr import EventMesh
from usr.audio_control import TTS_CONTENT, AUDIO_FILE_NAME
from machine import Pin
from machine import UART
from machine import ExtInt
from misc import PowerKey
from misc import Power


class FactoryManager(Abstract):
    """
    工厂模式
    """
    def __init__(self):
        self._pin19 = Pin(Pin.GPIO19, Pin.OUT, Pin.PULL_DISABLE, 0)
        self._pin6 = Pin(Pin.GPIO6, Pin.OUT, Pin.PULL_DISABLE, 0)
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        self.log.info("enter factory mode")
        self.check_factory()
        # 主控制灯关闭
        self._pin6.write(1)

    def check_factory(self):
        # 检测工厂模式
        u_count = 0
        sim_cid = -1
        while True:
            if self._pin19.read():
                if sim_cid == -1:
                    sim_cid = sim.getIccid()
                    utime.sleep_ms(200)
                    continue
                if u_count < 1:
                    # 进入工厂模式
                    EventMesh.publish("tts_play", TTS_CONTENT.FACTORY_MODE)
                    # white color
                    EventMesh.publish("red_on")
                    EventMesh.publish("green_on")
                    EventMesh.publish("blue_on")
                # send uart
                imei = EventMesh.publish("get_device_imei")
                csq = EventMesh.publish("get_csq")
                EventMesh.publish("main_uart_write", str(imei) + "|" + str(sim_cid) + "\r\n")
                EventMesh.publish("main_uart_write", "rssi=" + str(csq) + "\r\n")
                EventMesh.publish("main_uart_write", "test=success" + "\r\n")

                utime.sleep(4)
                u_count += 1
            else:
                break

class DeviceInfoManager(Abstract):
    """设备信息管理"""

    def __init__(self):
        self.__iccid = ""
        self.__imei = ""
        self.__fw_version = ""
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_instantiation(self):
        # 注册事件
        EventMesh.subscribe("get_sim_iccid", self.get_iccid)
        EventMesh.subscribe("get_device_imei", self.get_imei)
        EventMesh.subscribe("get_fw_version", self.get_device_fw_version)
        EventMesh.subscribe("get_csq", self.get_csq)

    def get_iccid(self, event=None, msg=None):
        """查询 ICCID"""
        if self.__iccid == "":
            msg = sim.getIccid()
            if msg != -1:
                self.__iccid = msg
            else:
                self.log.warn("get sim iccid fail, please check sim")
        return self.__iccid

    def get_imei(self, event=None, msg=None):
        """查询 IMEI"""
        if self.__imei == "":
            self.__imei = modem.getDevImei()
        return self.__imei

    def get_device_fw_version(self, event=None, msg=None):
        """查询 固件版本"""
        if self.__fw_version == "":
            self.__fw_version = modem.getDevFwVersion()
        return self.__fw_version

    def get_csq(self, event=None, msg=None):
        """查询 信号值"""
        return net.csqQueryPoll()

class UartManager(Abstract):
    '''
    工厂模式测试
    '''
    def __init__(self):
        self.__no = UART.UART2
        self.__bate = 115200
        self.__data_bits = 8
        self.__parity = 0
        self.__stop_bits = 1
        self.__flow_control = 0
        self.__uart = None
        self.log = get_logger(__name__ + "." + self.__class__.__name__)
        self.__uart = UART(self.__no, self.__bate, self.__data_bits, self.__parity, self.__stop_bits, self.__flow_control)
        self.__uart.set_callback(self.uart_cb)

    def post_processor_after_instantiation(self):
        # 注册事件
        EventMesh.subscribe("main_uart_write", self.write)

    def write(self, data):
        # self.log.info("write msg:{}".format(data))
        self.__uart.write(data)

    def read(self, number):
        data = self.__uart.read(number)
        return data

    def uart_cb(self, data):
        '''
        uart回调函数
        :param data: data是个元组包括（状态，通道，可读数据）
        :return:
        '''
        raw_data = self.read(data[2])
        if not raw_data or raw_data == b"":
            return
        self.log.info("UartRead msg: {}".format(raw_data))

class KeypadManager(Abstract):
    """
    按键事件处理
    """
    def __init__(self):
        self.__pk = PowerKey()
        self.__pk_start_time = 0
        self.__pk_end_time = 0
        self.__ic_start_time = 0
        self.__pu_start_time = 0
        # self.__key_1 = ExtInt(ExtInt.GPIO17, ExtInt.IRQ_RISING_FALLING, ExtInt.PULL_DISABLE, self.increase)
        # self.__key_2 = ExtInt(ExtInt.GPIO18, ExtInt.IRQ_RISING_FALLING, ExtInt.PULL_DISABLE, self.reduce_pu)
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        self.__pk.powerKeyEventRegister(self.pwk_callback)
        # self.__key_1.enable()
        # self.__key_2.enable()

    def pwk_callback(self, status):
        """pwk按键处理"""
        self.log.info("pwk_callback status {}".format(status))
        if status == 1:
            self.__pk_start_time = utime.time()
        else:
            self.__pk_end_time = utime.time()
            if self.__pk_end_time - self.__pk_start_time >= 3:
                # 设备关机
                EventMesh.publish("device_shutdown")
            else:
                order_info = EventMesh.publish("get_order_info")
                if isinstance(order_info, str):
                    # tts 播报上一笔订单
                    EventMesh.publish("tts_play", order_info)
                else:
                    # tts 播报无订单信息
                    EventMesh.publish("audio_play", AUDIO_FILE_NAME.NO_ORDER)
            # 刷新进入待机状态时间
            EventMesh.publish("update_wait_time")

    def increase(self, args):
        self.log.info("increase args {}".format(args))
        if not args[0][1]:
            diff = utime.time() - self.__ic_start_time
            if diff < 3:
                # 音量加
                EventMesh.publish("add_audio_volume")
            else:
                # audio播报设备信号
                pass
        else:
            self.__ic_start_time = utime.time()
            print("ic_start_time = {}".format(self.__ic_start_time))
        # 刷新进入待机状态时间
        EventMesh.publish("update_wait_time")

    def reduce_pu(self, args):
        self.log.info("reduce_pu args {}".format(args))
        if not args[0][1]:
            diff = utime.time() - self.__pu_start_time
            if diff < 3:
                # 音量减
                EventMesh.publish("reduce_audio_volume")
            else:
                # 重新连接服务器
                # audio 播放重连提示
                pass
        else:
            self.__pu_start_time = utime.time()
            print("pu_start_time = {}".format(self.__pu_start_time))
        # 刷新进入待机状态时间
        EventMesh.publish("update_wait_time")

class DeviceActionManager(Abstract):
    """
    设备行为
    """
    def __init__(self):
        self.__led_flag = 1
        self.__await_start_time = 0
        self.__lock = Lock()
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        # 注册事件
        EventMesh.subscribe("device_start", self.device_start)
        EventMesh.subscribe("device_shutdown", self.device_shutdown)
        EventMesh.subscribe("device_restart", self.device_restart)
        EventMesh.subscribe("update_wait_time", self.update_device_standby_wait_time)
        EventMesh.subscribe("update_led_flag", self.update_led_flag)
        # LED 灯闪烁
        _thread.start_new_thread(self.blink_thread, ())
        # 开启待机闪烁
        _thread.start_new_thread(self.device_standby, ())

    def device_shutdown(self, topic=None, data=None):
        # 设备关机
        EventMesh.publish("audio_play", AUDIO_FILE_NAME.DEVICE_SHUTDOWN)
        utime.sleep(5)
        Power.powerDown()

    def device_start(self, topic=None, data=None):
        # 设备开机
        EventMesh.publish("audio_play", AUDIO_FILE_NAME.DEVICE_START)

    def device_restart(self, topic=None, data=None):
        # 设备重启
        Power.powerRestart()

    def device_standby (self):
        # 设备待机状态
        while True:
            # self.log.info("device_standby led_flag {}".format(self.__led_flag))
            if self.__led_flag == 1:
                if utime.time() - self.__await_start_time > 30:
                    EventMesh.publish("blue_blink")
                    utime.sleep(8)
                    continue
            utime.sleep(10)
            continue

    def update_device_standby_wait_time(self, topic=None, data=None):
        # 更新设备进入待机状态时间
        self.__await_start_time = utime.time()

    def update_led_flag(self, topic=None, flag=None):
        # 更新设备led 模式
        with self.__lock:
            if flag:
                self.__led_flag = flag
            else:
                return self.__led_flag

    def blink_thread(self):
        # 闪烁线程
        while True:
            light_flag = EventMesh.publish("update_led_flag")
            # self.log.info("blink_thread --  light_flag {}".format(light_flag))
            if light_flag < 4 and light_flag != 1:
                if light_flag == 3:
                    # 语音提示低电量
                    EventMesh.publish("audio_play", AUDIO_FILE_NAME.BATT_LOW)
                if light_flag == 1:
                    EventMesh.publish("blue_blink")
                elif light_flag == 2:
                    EventMesh.publish("green_blink")
                elif light_flag == 3:
                    EventMesh.publish("red_blink")
                utime.sleep(8)
            else:
                utime.sleep(8)

class OrderManager(Abstract):
    """
    订单管理
    """
    def __init__(self):
        self.__history_order_list = list()
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        # 注册事件
        EventMesh.subscribe("add_order_info", self.add_order_history_list)
        EventMesh.subscribe("get_order_info", self.get_order_history_list)

    def add_order_history_list(self, topic, data):
        # 保存最新五条订单信息
        self.__history_order_list.append(data)
        self.log.info("history_order_list = {}".format(self.__history_order_list))
        if len(self.__history_order_list) > 5:
            self.__history_order_list = self.__history_order_list[1:]

    def get_order_history_list(self,topic=None, data=None):
        # 查询获取订单信息
        if self.__history_order_list:
            # 返回最后一条订单信息
            return self.__history_order_list[-1]
        else:
            return False

class ChargeManager(Abstract):
    """
    电池管理
    充电管理
    """
    def __init__(self):
        self.__charge_full_flag = False  # 正常是False 充满是True
        self.__gpio4 = Pin(Pin.GPIO4, Pin.IN, Pin.PULL_DISABLE, 1)
        self.__gpio5 = Pin(Pin.GPIO5, Pin.IN, Pin.PULL_DISABLE, 1)
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        _thread.start_new_thread(self.check_charge_state_task, ())
        _thread.start_new_thread(self.check_battery_v, ())

    def check_charge_state_task(self):
        # 检查充电状态
        while True:
            light_flag = EventMesh.publish("update_led_flag")
            if not self.__gpio4.read():
                # 充电中切换成4状态
                if light_flag != 4:
                    EventMesh.publish("update_led_flag", 4)
                if not self.__charge_full_flag:
                    self.charge_full_light_operate(0x01)
                else:
                    self.charge_full_light_operate(0x02)
            else:
                if not self.__gpio5.read():
                    if light_flag != 4:
                        EventMesh.publish("update_led_flag", 4)
                    self.charge_full_light_operate(0x02)
                else:
                    if light_flag == 4:
                        # 检测拔出信号, 拔掉关闭所有等, 充满标志位清零
                        self.update_charge_full_flag(False)
                        EventMesh.publish("blue_off")
                        EventMesh.publish("green_off")
                        EventMesh.publish("update_led_flag", 1)
            utime.sleep_ms(1000)

    def update_charge_full_flag(self, flag):
        self.__charge_full_flag = flag

    def charge_full_light_operate(self, idx):
        # 关闭充电常量灯
        # self.log.info("charge_full_light_operate  ---idx=%d" % idx)
        if idx == 1:
            if EventMesh.publish("blue_read"):
                EventMesh.publish("blue_off")
            if not EventMesh.publish("green_read"):
                EventMesh.publish("green_on")
        else:
            if EventMesh.publish("green_read"):
                EventMesh.publish("green_off")
            if not EventMesh.publish("blue_read"):
                EventMesh.publish("blue_on")

    def check_battery_v(self):
        mv_list = list()
        while True:
            # self.log.info("check_battery_v")
            mv = Power.getVbatt() * 1.07
            # self.log.info("Checking battery mv {}".format(mv))
            mv_list.append(mv)
            if len(mv_list) >= 6:
                self.check_battery_o(mv_list)
                mv_list = mv_list[1:]
                continue
            if mv > 3750:
                if mv > 4200 and not self.__charge_full_flag:
                    self.update_charge_full_flag(True)
                utime.sleep(40)
            else:
                if self.__charge_full_flag:
                    self.update_charge_full_flag(False)
                utime.sleep(20)

    def check_battery_o(self, mv_list):
        # 检查电池电量
        # reduce max min value
        mv_list.remove(max(mv_list))
        mv_list.remove(min(mv_list))
        mv = float(sum(mv_list)) / len(mv_list)
        light_flag = EventMesh.publish("update_led_flag")
        if 3400 <= mv < 3600:
            if light_flag < 3:
                EventMesh.publish("update_led_flag", 3)
                EventMesh.publish("red_set_timeout", 8)
            utime.sleep(30)
        elif mv < 3400:
            EventMesh.publish("device_shutdown")
        else:
            EventMesh.publish("update_led_flag", 1)
            EventMesh.publish("blue_set_timeout", 8)
            sleep_defer = 30
            if mv >= 3750:
                sleep_defer = 60
            utime.sleep(sleep_defer)

class LteNetManager(Abstract):
    """LTE 网络管理"""

    def __init__(self):
        self.__data_call = dataCall
        self.__net = net
        self.__data_call_flag = False
        self.__timer = osTimer()
        self.__net_error_mode = 0
        self.check_net = checkNet.CheckNetwork("QuecPython_Helios_Framework", "this latest version")
        self.check_net_timeout = 100 * 1000
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        self.data_call_start()

    def data_call_start(self):
        sim_state = False
        for i in range(1, 5):
            if sim.getStatus() == 1:
                sim_state = True
                break
            utime.sleep(1)
        if not sim_state:
            self.log.error("sim state is error")
            self.__net_error_mode = 0
            EventMesh.publish("tts_play", TTS_CONTENT.STR_NO_SIM_CARD)
            self.net_error_audio_start()
            return 0
        self.wait_connect(30)

    def data_call_stop(self, topic=None, data=None):
        self.net_error_audio_stop()

    def wait_connect(self, timeout):
        """等待设备找网"""
        self.log.info("wait net -----------")
        stagecode, subcode = self.check_net.wait_network_connected(timeout)
        if stagecode == 3 and subcode == 1:
            # 注网成功
            EventMesh.publish("tts_play", TTS_CONTENT.STR_CONNECT_NET_OK)
            self.log.info("module net success, run mqtt connect")
            EventMesh.publish('ota_check')
            EventMesh.publish('mqtt_connect')
            self.net_error_audio_stop()
        else:
            # 注网失败
            self.__net_error_mode = 1
            self.log.error("module net fail, wait try again")
            EventMesh.publish("tts_play", TTS_CONTENT.SSTR_CONNECT_NET_FAILED)
            self.net_fail_process()
        self.__data_call.setCallback(self.net_state_cb)

    def net_fail_process(self):
        # 注网失败，尝试Cfun后重新找网，若Cfun失败则模组重启
        state = net.setModemFun(0)
        if state == -1:
            self.log.error("cfun net mode error, device will restart.")
            utime.sleep(5)
            # Power.powerRestart()
        state = net.setModemFun(1)
        if state == -1:
            self.log.error("cfun net mode error, device will restart.")
            utime.sleep(5)
            # Power.powerRestart()
        self.log.info("cfun net mode success, note the net again")
        self.wait_connect(30)

    def net_error_audio_task(self, timer):
        if self.__net_error_mode:
            EventMesh.publish("tts_play", TTS_CONTENT.STR_NO_SIM_CARD)
        else:
            EventMesh.publish("tts_play", TTS_CONTENT.STR_CONNECT_NET_FAILED)

    def net_error_audio_start(self):
        self.__timer.stop()
        self.__timer.start(60 * 1000, 1, self.net_error_audio_task)

    def net_error_audio_stop(self):
        self.__timer.stop()

    def net_state_cb(self, args):
        """网络状态变化，会触发该回调函数"""
        nw_sta = args[1]
        if nw_sta == 1:
            EventMesh.publish("tts_play", TTS_CONTENT.STR_CONNECT_NET_OK)
            self.log.info("network connected!")
            self.net_error_audio_stop()
        else:
            self.net_error_audio_start()
            EventMesh.publish("tts_play", TTS_CONTENT.SSTR_CONNECT_NET_FAILED)
            self.log.info("network not connected!")

class CloudHornManager(Abstract):
    """
    云端消息处理
    """
    def __init__(self):
        self.__queue = Queue(100)
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        _thread.start_new_thread(self.listen_queue, ())
        EventMesh.subscribe("put_msg_queue", self.put_msg_queue)

    def put_msg_queue(self, topic, data):
        self.__queue.put(data)

    def listen_queue(self):
        while True:
            data = self.__queue.get()
            self.pay_play(data)
            utime.sleep_ms(500)

    def pay_play(self, data):
        pay_msg = data["pay_msg"]
        notice_type = data["notice_type"]
        EventMesh.publish("tts_play", pay_msg)
        EventMesh.publish("add_order_info", data)
        EventMesh.publish("update_wait_time")
        if notice_type == "1003":
            EventMesh.publish("red_blink")
        else:
            EventMesh.publish("green_blink")




