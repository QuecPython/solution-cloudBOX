"""
LED 三色指示灯管理
"""

import utime
from machine import Pin
from usr import EventMesh
from usr.common import Abstract


class Light(Abstract):
    def __init__(self, pin):
        self.l = pin
        self._timeout = 0

    def on(self, topic=None, data=None):
        self.l.write(1)

    def off(self, topic=None, data=None):
        self.l.write(0)

    def read(self, topic=None, data=None):
        return self.l.read()

    def get_timeout(self, topic=None, data=None):
        return self._timeout

    def set_timeout(self, topic=None, time=None):
        self._timeout = time

    def blink_O(self, topic=None, data=None):
        self.on()
        utime.sleep(0.3)
        self.off()

class RLight(Light):
    def __init__(self):
        super(RLight, self).__init__(Pin(Pin.GPIO13, Pin.OUT, Pin.PULL_DISABLE, 0))

    def post_processor_after_initialization(self):
        """订阅此类所有的事件到 EventMesh中"""
        EventMesh.subscribe("red_on", self.on)
        EventMesh.subscribe("red_off", self.off)
        EventMesh.subscribe("red_blink", self.blink_O)
        EventMesh.subscribe("red_read", self.read)
        EventMesh.subscribe("red_set_timeout", self.set_timeout)

class GLight(Light):
    def __init__(self):
        super(GLight, self).__init__(Pin(Pin.GPIO31, Pin.OUT, Pin.PULL_DISABLE, 0))

    def post_processor_after_initialization(self):
        """订阅此类所有的事件到 EventMesh中"""
        EventMesh.subscribe("green_on", self.on)
        EventMesh.subscribe("green_off", self.off)
        EventMesh.subscribe("green_blink", self.blink_O)
        EventMesh.subscribe("green_read", self.read)
        EventMesh.subscribe("green_set_timeout", self.set_timeout)

class BLight(Light):
    def __init__(self):
        super(BLight, self).__init__(Pin(Pin.GPIO17, Pin.OUT, Pin.PULL_DISABLE, 0))

    def post_processor_after_initialization(self):
        """订阅此类所有的事件到 EventMesh中"""
        EventMesh.subscribe("blue_on", self.on)
        EventMesh.subscribe("blue_off", self.off)
        EventMesh.subscribe("blue_blink", self.blink_O)
        EventMesh.subscribe("blue_read", self.read)
        EventMesh.subscribe("blue_set_timeout", self.set_timeout)