import modem
import net
import ubinascii
import uhashlib
import request
import ujson
import utime
import app_fota
from misc import Power
from usr.common import get_logger
from usr.common import Abstract
from usr import EventMesh
from usr.audio_control import TTS_CONTENT, AUDIO_FILE_NAME


PROCESS_CODE = {
    "DO_NOT_UPGRADE": 0,
    "DOWNLOADING_FIRMWARE": 3,
    "DOWNLOADED_NOTIFY_UPDATE": 4,
    "DOWNLOAD_FAILED": 5,
    "UPDATE_START": 6,
    "UPGRADE_SUCCESS": 7,
    "UPGRADE_FAILED": 8,
}

class UCloudOTA(object):

    def __init__(self, version, module_type, battery, url="http://220.180.239.212:8274/v1"):
        self.imei = modem.getDevImei()
        self.rsrp = net.csqQueryPoll()
        self.url = url
        self.version = version
        self.module_type = module_type
        self.battery = battery
        self.uid = ""
        self.pk = ""
        self.cellId = ""
        self.mnc = ""
        self.mcc = ""
        self.lac = ""
        self.report_url = "/fota/status/report"
        self.access_token = ""
        self.upgrade_info = {}
        self.status_code_dict = {
            "OK": 2000,
            "UPGRADE": [
                3001,  # need upgrade
                3002  # not need upgrade
            ],
            "ERROR": [
                5001,  # get_token error
                5002,  # get upgrade url ERROR
                5003,  # sh fota ERROR
                5004,  # request error
                5005  # params error
            ]
        }
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def get_token(self, prefix="/oauth/token", kwargs=None):
        uri = self.url + prefix
        try:
            secret = ubinascii.hexlify(uhashlib.md5("QUEC" + str(self.imei) + "TEL").digest())
            secret = secret.decode()
            uri = uri + "?imei=" + self.imei + "&" + "secret=" + secret
            self.log.info("uri = {}".format(uri))
            resp = request.get(uri)
            json_data = resp.json()
            self.access_token = json_data["data"]["access_Token"]
            return self.status_code_dict["OK"]
        except Exception as e:
            return self.status_code_dict["ERROR"][0]

    def report(self, code, msg=None):
        self.log.info(code)
        self.log.info(msg)
        data_info = {
            "version": str(self.version),
            "ver": "v1.0",
            "imei": str(self.imei),
            "code": PROCESS_CODE.get(code, 0),
            "msg": str(msg) if msg else code
        }

        self.log.info(data_info)
        uri = self.url + self.report_url
        headers = {"access_token": self.access_token, "Content-Type": "application/json"}
        try:
            resp = request.post(uri, data=ujson.dumps(data_info), headers=headers)
            return resp
        except Exception as e:
            return -1

    def get_upgrade_url(self, prefix="/fota/fw"):
        params = "?" + "version=" + str(self.version) + "&" + "imei=" + str(self.imei) + "&" + "moduleType=" + str(
            self.module_type) + "&" + "battery=" + str(
            self.battery) + "&" + "rsrp=" + str(self.rsrp)
        uri = self.url + prefix + params
        headers = dict(access_token=self.access_token)
        try:
            resp = request.get(uri, headers=headers)
            json_data = resp.json()
            self.log.info(json_data)
            if json_data["code"] == 200:
                self.upgrade_info = json_data
                return self.status_code_dict["OK"]
            else:
                return self.status_code_dict["ERROR"][3], None
        except Exception as e:
            return self.status_code_dict["ERROR"][1], None

    def upgrade_fota_bin(self, upgrade_info=None):
        "升级fota bin"
        pass

    def upgrade_fota_sh(self, upgrade_path):
        try:
            action = self.upgrade_info["action"]
            url = self.upgrade_info["url"]
        except Exception as e:
            return self.status_code_dict["ERROR"][4]
        try:
            if action:
                self.report("DOWNLOADING_FIRMWARE")
                fota = app_fota.new()
                fota.download(url, upgrade_path)
                self.report("DOWNLOADED_NOTIFY_UPDATE")
                fota.set_update_flag()
                self.report("UPDATE_START")
                return self.status_code_dict["UPGRADE"][0]
            else:
                return self.status_code_dict["UPGRADE"][1]
        except Exception as e:
            self.report(PROCESS_CODE[5])
            return self.status_code_dict["ERROR"][2]

class OTAManager(Abstract):
    """
    设备OTA升级
    """
    def __init__(self):
        self.log = get_logger(__name__ + "." + self.__class__.__name__)

    def post_processor_after_initialization(self):
        # 注册事件
        EventMesh.subscribe("ota_check", self.check_ota_event)

    def check_ota_event(self, topic=None, event=None):
        mv = Power.getVbatt() * 1.07
        if mv < 3.6:
            return
        try:
            # 读取本地配置
            version = EventMesh.publish("persistent_config_get", "version")
            flag = EventMesh.publish("persistent_config_get", "flag")
        except Exception as e:
            self.log.error("ota config info {}".format(e))
            return

        self.log.info("===============get get_token==================")
        try:
            ota = UCloudOTA(version=version, module_type="EC600N-CX", battery=100)
            code = ota.get_token()
            self.log.info("get_token:code == {}".format(code))
            if code != 2000:
                return
        except Exception as e:
            self.log.error("get_token {}".format(e))
            return
        self.log.info("==============flag upgrade yes or no ============")
        try:
            self.log.info("ota_config_info[flag] = " + flag)
            # 判断升级是否继续  ota的标志
            if flag == "1":
                ota.report("UPGRADE_SUCCESS", version)
                EventMesh.publish("persistent_config_store", {"flag": "0"})
                utime.sleep(2)
                return
        except Exception as e:
            self.log.error("flag === {}".format(e))
            return
        self.log.info("==============get_url ============")
        try:
            code = ota.get_upgrade_url()
            self.log.info("get_upgrade_url == {}".format(code))
            if code != 2000:
                return
        except Exception as e:
            self.log.error("get_upgrade_url() {}".format(e))
            return
        self.log.info("==============pull and upgrade ============")
        try:
            code = ota.upgrade_fota_sh("/usr/main_t.py")
            self.log.info(ota.upgrade_info)
            self.log.info("code: =={}".format(code))
            if code == 3001:
                EventMesh.publish("persistent_config_store", {"version": ota.upgrade_info["targetVersion"]})
                EventMesh.publish("persistent_config_store", {"flag": "1"})
                EventMesh.publish("audio_play", AUDIO_FILE_NAME.UPDATE_OVER)
                utime.sleep(3)
                EventMesh.publish("audio_play", AUDIO_FILE_NAME.DEVICE_SHUTDOWN)
                utime.sleep(2)
                EventMesh.publish("device_restart")
        except Exception as e:
            return