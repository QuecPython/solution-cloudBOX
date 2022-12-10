import ujson
import utime
import _thread
from aLiYun import aLiYun
from usr.common import get_logger
from usr.common import Abstract
from usr import EventMesh
from usr.audio_control import TTS_CONTENT, AUDIO_FILE_NAME

class AliYunManage(Abstract):
    '''
    MQTT interface
    '''
    def __init__(self):
        self.__mqtt_client = None
        self.product_key = ''  # 产品识别码
        self.product_secret = None  # 产品密钥
        self.device_name = ''  # 设备（备注）名称
        self.device_secret = ''  # 设备密钥
        self.client_id = ''  # 自定义
        self.clean_session = True  # 客户端类型 (False: 持久客户端，True: 临时的)
        self.keep_alive = 300  # 允许最长通讯时间（s）
        self.sub_topic = ''  # 订阅地址
        self.qos = 1  # 消息服务质量 0：发送者只发送一次消息，不进行重试 1：发送者最少发送一次消息，确保消息到达Broker
        self.conn_flag = False
        self.start_mqtt_flag = False
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        EventMesh.subscribe("mqtt_connect", self.start_mqtt_connect)

    def check_connect_param(self):
        # 检查三元组参数
        while True:
            product_key = EventMesh.publish("persistent_config_get", "pk")
            barcode = EventMesh.publish("persistent_config_get", "barcode")
            self.log.info("product_key = {}, barcode = {}".format(product_key, barcode))
            if product_key == "" or barcode == "":
                # 序列号未写入或串号异常
                EventMesh.publish("tts_play", TTS_CONTENT.SET_MQTT_SN_ERROR)
            else:
                # DeviceSecret,ProductKey
                self.product_key = product_key
                self.device_name, self.device_secret = barcode.split(",")
                self.client_id = self.device_name
                self.sub_topic = "/sys/{}/{}/thing/event/property/post".format(self.product_key, self.device_name)
                self.connect()
                break
            utime.sleep(45)

    def start_mqtt_connect(self, topic=None, data=None):
        if self.start_mqtt_flag and self.conn_flag:
            self.log.info("重新连接MQTT")
            # 切换网络后重新连接mqtt云服务器
            try:
                self.disconnect()
            except:
                self.log.info("mqtt disconnect error")
            self.log.info("关闭之前的MQTT连接")
            utime.sleep(1)
        self.start_mqtt_flag = True
        self.log.info("MQTT 参数检查")
        _thread.start_new_thread(self.check_connect_param, ())

    def connect(self, topic=None, data=None):
        if not self.conn_flag:
            self.conn_flag = True
        self.__mqtt_client = aLiYun(self.product_key,self.product_secret,self.device_name,self.device_secret)
        con_state = self.__mqtt_client.setMqtt(self.client_id,clean_session=self.clean_session,reconn=True)
        self.log.info("connect   con_state --{}".format(con_state))
        if con_state != 0:
            self.log.warn("mqtt connect failed!")
            EventMesh.publish("tts_play", TTS_CONTENT.SERVER_CONN_FAIL)
            return False
        self.__mqtt_client.start()
        self.__mqtt_client.setCallback(self.callback)
        sub_sta = self.__mqtt_client.subscribe(self.sub_topic, qos=self.qos)
        if sub_sta != 0:
            self.log.warn("mqtt subscribe topic failed!")
            return False
        EventMesh.publish("tts_play", TTS_CONTENT.SERVER_CONN_SUCCESS)
        self.log.info("mqtt connect success!")
        return True

    def publish(self, topic, data):
        pass

    def callback(self, topic, msg):
        '''
        mqtt 消息回调
        '''
        json_data = ujson.loads(msg)
        params = json_data.get('params', False)
        self.log.info("json_data {}".format(json_data))
        EventMesh.publish("put_msg_queue", params)

    def disconnect(self):
        self.__mqtt_client.disconnect()

