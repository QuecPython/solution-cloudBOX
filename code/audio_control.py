# -*- coding: UTF-8 -*-
"""
Audio TTS 功能

AUDIO_FILE_NAME :音频文件
TTS_CONTENT:TTS播报内容
AudioManager: audio 功能管理
"""

import audio
from machine import Pin
from usr.common import get_logger
from usr.common import Abstract
from usr import EventMesh


class AUDIO_FILE_NAME(object):
    FILE_PATH = "U:/audio_file/"
    DEVICE_SHUTDOWN = FILE_PATH + "off.amr"
    DEVICE_START = FILE_PATH + "on.amr"
    NO_ORDER = FILE_PATH + "no_order.amr"
    BATT_LOW = FILE_PATH + "batt_low.amr"
    UPDATE_OVER = FILE_PATH + "update_over.amr"

class TTS_CONTENT(object):
    VOLUME_MAX = " 音量最大"
    VOLUME_MIN = " 音量最小"
    VOLUME_NUM = " 音量"
    FACTORY_MODE = " 进入工厂模式"
    STR_NO_SIM_CARD = " 请插入流量卡,并重启设备"
    STR_CONNECT_NET_OK = " 网络连接成功,正在连接服务器,请稍后"
    STR_CONNECT_NET_FAILED = " 网络连接失败,正在尝试重新连接,"
    SET_MQTT_SN_ERROR = " 阿里云连接参数获取失败"
    SERVER_CONN_FAIL = " 服务器连接失败,正在重新连接,"
    SERVER_CONN_SUCCESS = " 服务器连接成功"

class AudioManager(Abstract):
    """
    audio 初始化
    音频文件播放
    TTS 播报管理
    """

    def __init__(self):
        self.__audio = audio.Audio(0)
        self.__tts = audio.TTS(0)
        self.__audio_volume = 3
        self.__tts_priority = 2
        self.__tts_breakin = 0
        self.__tts_mode = 2
        self.__volume_level = {
            1: 1,
            2: 3,
            3: 6,
            4: 9,
            5: 11
        }
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        self.__set_audio_pa()
        vol_num = EventMesh.publish("persistent_config_get", "vol_num")
        self.__audio_volume = vol_num
        # 设置TTS音量
        self.__audio.setVolume(self.__volume_level.get(self.__audio_volume))
        EventMesh.subscribe("audio_play", self.audio_play)
        EventMesh.subscribe("tts_play", self.tts_play)
        EventMesh.subscribe("get_audio_state", self.get_audio_state)
        EventMesh.subscribe("get_tts_state", self.get_tts_state)
        EventMesh.subscribe("add_audio_volume", self.add_audio_volume)
        EventMesh.subscribe("reduce_audio_volume", self.reduce_audio_volume)
        self.audio_play(None, AUDIO_FILE_NAME.DEVICE_START)

    def __set_audio_pa(self):
        """Set audio pa"""
        state = self.__audio.set_pa(Pin.GPIO16)
        if not state:
            self.log.warn("set audio pa error!")

    def audio_play(self, topic=None, filename=None):
        """Play audio"""
        if filename is None:
            return
        state = self.__audio.play(self.__tts_priority, self.__tts_breakin, filename)
        return True if state == 0 else False

    def audio_play_stop(self, topic=None, data=None):
        """audio stop"""
        state = self.__audio.stop()
        return True if state == 0 else False

    def get_audio_state(self, topic=None, data=None):
        """get audio state"""
        state = self.__audio.getState()
        return True if state == 0 else False

    def get_tts_state(self, topic=None, data=None):
        """获取TTS播放状态"""
        state = self.__tts.getState()
        return True if state == 0 else False

    def get_audio_volume(self, topic=None, data=None):
        """get audio volume"""
        return self.__audio_volume

    def add_audio_volume(self, topic=None, vol_num=None):
        """添加音量"""
        vol_num = self.__audio_volume + 1
        self.__audio_volume = 5 if vol_num > 5 else vol_num
        self.__set_audio_volume(self.__volume_level.get(self.__audio_volume))

    def reduce_audio_volume(self, topic=None, vol_num=None):
        """减少音量"""
        vol_num = self.__audio_volume - 1
        self.__audio_volume = 1 if vol_num < 1 else vol_num
        self.__set_audio_volume(self.__volume_level.get(self.__audio_volume))

    def __set_audio_volume(self, vol_num):
        """set audio volume"""
        print("__set_audio_volume vol num = %d" % self.__audio_volume)
        if self.__audio_volume >= 5:
            self.tts_play(None, TTS_CONTENT.VOLUME_MAX)
        elif self.__audio_volume <= 1:
            self.tts_play(None, TTS_CONTENT.VOLUME_MIN)
        else:
            self.tts_play(None, TTS_CONTENT.VOLUME_NUM + str(self.__audio_volume))
        self.__audio.setVolume(vol_num)
        EventMesh.publish("persistent_config_store", {"vol_num": self.__audio_volume})

    def tts_play(self, topic=None, content=None):
        """Play tts
        __tts_priority 播放优先级，支持优先级0 ~ 4，数值越大优先级越高
        __tts_breakin 打断模式，0表示不允许被打断，1表示允许被打断
        __tts_mode 编码模式 2 - UTF-8
        content  播报内容
        """
        if content is None:
            return
        state = self.__tts.play(self.__tts_priority, self.__tts_breakin, self.__tts_mode, content)
        return True if state == 0 else False

if __name__ == '__main__':
    a = AudioManager()
    a.post_processor_after_initialization()

