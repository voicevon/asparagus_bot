# https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf


# ================== Import Statements ==================
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import time
from picamera2 import Picamera2
from libcamera import controls
import numpy as np

# ================== Constant Definitions ==================
# MQTT Configuration
MQTT_BROKER = "voicevon.vicp.io"
MQTT_PORT = 1883
MQTT_TOPIC_CAPTURE = "as_p8/capture"
MQTT_TOPIC_COUNTER = "as_p8/counter"
MQTT_TOPIC_POWER_DOWN = "as_p8/power_down"
MQTT_CREDENTIALS = ("von", "von1970")

# Hardware Pins
ENCODER_PIN_CLK = 18
ENCODER_PIN_DT = 15
ENCODER_PIN_ABS_ZERO = 14  # 新增绝对零位引脚
POWER_PIN_MAIN = 23  # 假设使用GPIO23检测主电源

# Camera Parameters
# 更新相机配置参数
CAMERA_SETTINGS = {
    'main': {
        'size': (1456, 1088),  # 更高的传感器原生分辨率
        'format': 'XBGR8888'   # 更高效的像素格式
    },
    'controls': {
        'AwbEnable': False,
        'AeEnable': False,
        'FrameRate': 60.0,
        'ExposureTime': 5000  # 新增曝光时间设置（单位：微秒）
    }
}

# Timing Parameters
TIMING = {
    'sensor_stabilize': 0.5,  # Sensor stabilization time (seconds)
    'timeout_interval': 5      # Auto-capture interval (seconds)
}

# ================== Global Variables ==================
image_counter = 0
encoder_counter = 0
power_down_counter = 0
last_clk_state = None
last_trigger_time = time.time()
cam = None
encoder_at = "not_todo"  # “todo”， “done”

# ================== Constant Definitions ==================

ENCODER_TRIGGER_POSITION = 100  # 根据实际需求调整触发位置

# ================== Function Definitions ==================
def abs_zero_callback(channel):
    global encoder_counter
    print(f"[ZERO] 计数器已重置  at | {encoder_counter}")
    encoder_counter = 0  # 重置编码器计数

def encoder_callback(channel):
    global encoder_counter, last_clk_state, encoder_at

    clk_state = GPIO.input(ENCODER_PIN_CLK)
    dt_state = GPIO.input(ENCODER_PIN_DT)
    
    if clk_state != last_clk_state:
        # direction = "+" if dt_state != clk_state else "-"
        # print(f"[ENCODER] 方向：{direction} | 新值：{encoder_counter}")
        
        if dt_state != clk_state:
            encoder_counter += 1
        else:
            encoder_counter -= 1
    last_clk_state = clk_state


    if encoder_counter >= ENCODER_TRIGGER_POSITION:
        if encoder_at == "not_todo":
            encoder_at = "todo"
    else:
        encoder_at = "not_todo"



def power_failure_callback(channel):
    global power_down_counter
    power_down_counter += 1


    """电源故障回调函数"""
    print("!!! 主电源断开，准备关机 !!!")
    
    import subprocess
    # subprocess.run(["sudo", "shutdown", "-h", "now"])
    # 需要配置sudo权限允许无密码执行shutdown命令：

    # bash
    # sudo visudo
    # # 添加以下内容（假设用户为pi）：
    # pi ALL=(ALL) NOPASSWD: /sbin/shutdown


def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ENCODER_PIN_CLK, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
    GPIO.setup(ENCODER_PIN_DT, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
    GPIO.setup(ENCODER_PIN_ABS_ZERO, GPIO.IN, pull_up_down=GPIO.PUD_OFF)  # 初始化新引脚 
    GPIO.add_event_detect(ENCODER_PIN_ABS_ZERO, GPIO.FALLING, callback=abs_zero_callback, bouncetime=None)  # 新增事件检测
    GPIO.add_event_detect(ENCODER_PIN_CLK, GPIO.BOTH, callback=encoder_callback, bouncetime=None)

    # 配置电源检测引脚（使用内部下拉电阻，当外部供电正常时保持高电平）
    GPIO.setup(POWER_PIN_MAIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(POWER_PIN_MAIN, GPIO.FALLING, 
                         callback=power_failure_callback, bouncetime=200)
    
def initialize_camera():
    global cam
    cam = Picamera2()
    config = cam.create_preview_configuration(main=CAMERA_SETTINGS['main'])
    cam.configure(config)
    cam.set_controls(CAMERA_SETTINGS['controls'])
    cam.start()



def capture_frame():
    try:
        # 使用Picamera2的捕获方法
        image = cam.capture_array("main")
        # 转换为OpenCV兼容的BGR格式
        bgr_image = image[:, :, :3].copy()[:, :, ::-1]
        return bgr_image
        
    except Exception as e:
        print(f"Camera error: {str(e)}")
        return None

def send_via_mqtt(frame):
    global image_counter, power_down_counter

    try:
        # 创建内存流对象
        from io import BytesIO
        import cv2  # 添加OpenCV导入
        
        # Update and send counter
        image_counter += 1
        counter_info = client.publish(MQTT_TOPIC_COUNTER, image_counter, qos=1)
        counter_info = client.publish(MQTT_TOPIC_POWER_DOWN, power_down_counter, qos=1)


        # 将BGR帧转换为JPEG
        _, jpeg_buffer = cv2.imencode('.jpg', frame)
        image_data = jpeg_buffer.tobytes()
        info = client.publish(MQTT_TOPIC_CAPTURE, image_data, qos=1)
        
        # Print transmission status
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Image {image_counter} published successfully")
        else:
            print(f"Image publish failed with code: {info.rc}")
            
    except Exception as e:
        print(f"MQTT transmission error: {str(e)}")


# ================== Main Program ==================
if __name__ == "__main__":
    # global flag  ？？
    setup_gpio()
    initialize_camera()  # 初始化相机
    client = mqtt.Client()
    client.username_pw_set(*MQTT_CREDENTIALS)
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()
        print("MQTT client connected")
        
        while True:

            if encoder_at == "todo":
                if (frame := capture_frame()) is not None:
                    send_via_mqtt(frame)
                    last_trigger_time = time.time()  # 重置计时器
                    print(f"Triggered capture at position {encoder_counter}")
                encoder_at = "done"
            
            # 保留原有的超时拍照逻辑（可选）
            current_time = time.time()
            if current_time - last_trigger_time >= TIMING['timeout_interval']:
                print("capture frame,  reason:  timeout")

                if (frame := capture_frame()) is not None:
                    send_via_mqtt(frame)
                    last_trigger_time = current_time
            time.sleep(0.001)


    except KeyboardInterrupt:
        GPIO.cleanup()
        client.disconnect()