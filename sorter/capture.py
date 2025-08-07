# pip install opencv-python paho-mqtt
# pip install RPi.GPIO

# 新增运行环境配置（设置为 'windows' 或 'raspberry'）
RUN_ENV = "raspberry" 
# RUN_ENV = "windows"  

# 根据环境导入硬件相关库
if RUN_ENV == "raspberry":
    import RPi.GPIO as GPIO
else:
    GPIO = None  # Windows环境下不导入

import cv2
import paho.mqtt.client as mqtt
import numpy as np
import time

# 在MQTT配置下方添加客户端初始化
# MQTT配置（需根据实际服务器修改）
MQTT_BROKER = "voicevon.vicp.io"
MQTT_PORT = 1883
MQTT_TOPIC = "as_p8/capture"
MQTT_COUNTER_TOPIC = "as_p8/counter"
MQTT_USERNAME = "von"
MQTT_PASSWORD = "von1970"
TIMER_INTERVAL = 0.5

# 初始化MQTT客户端
# 新增全局计数器（需要移动到函数定义之前）
image_counter = 0

# 在全局配置后添加客户端初始化
client = mqtt.Client()

# 修改编码器配置部分
if RUN_ENV == "raspberry":
    # 原树莓派GPIO配置
    ENCODER_CLK = 17
    ENCODER_DT = 18
    # 调整初始化顺序（树莓派环境）
    if RUN_ENV == "raspberry":
        # 先完成GPIO设置
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENCODER_CLK, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENCODER_DT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # 最后获取初始状态
        last_clk_state = GPIO.input(ENCODER_CLK)

else:
    # Windows环境下的虚拟配置
    ENCODER_CLK = None
    ENCODER_DT = None

# 全局变量记录编码器状态
encoder_counter = 0
last_clk_state = None

if RUN_ENV == "raspberry":
    last_clk_state = GPIO.input(ENCODER_CLK)  # 需要确保GPIO已初始化

# 应该调整到GPIO初始化之后

# 修改摄像头为全局对象
cap = cv2.VideoCapture(0) if RUN_ENV == "windows" else None

def capture_frame():
    """从摄像头捕获一帧图像"""
    global cap
    if RUN_ENV == "windows" and not cap.isOpened():
        cap.open(0)  # Windows环境下保持摄像头长连接
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return None
    
    ret, frame = cap.read()
    return frame if ret else None

def send_via_mqtt(image):
    """通过MQTT发送图像"""
    global image_counter, client  # 现在可以正确访问全局计数器
    # 将图像编码为JPEG格式
    _, img_encoded = cv2.imencode('.jpg', image)
    msg = img_encoded.tobytes()
    
    try:
        client.publish(MQTT_TOPIC, msg)
        print("图像发送成功")
        
        # 成功发送后递增并发布计数器
        image_counter += 1
        print(f"当前计数器值: {image_counter}")
        # client.publish(MQTT_COUNTER_TOPIC, image_counter.to_bytes(4, byteorder='big'))
        client.publish(MQTT_COUNTER_TOPIC, image_counter)
        
    except Exception as e:
        print(f"MQTT发送失败: {str(e)}")
        print(f"当前服务器配置: broker={MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC}")
        print(f"认证信息: username={MQTT_USERNAME} (密码已设置)" if MQTT_PASSWORD else "无密码认证")
    finally:
        # 移除了 client.disconnect()  # 重要修复：保持长连接
        pass

# 在全局变量部分新增
TIMEOUT_INTERVAL = 5  # 超时时间（秒）
last_trigger_time = time.time()

# 修改编码器回调函数
def encoder_callback(channel):
    global encoder_counter, last_clk_state, last_trigger_time
    clk_state = GPIO.input(ENCODER_CLK)
    dt_state = GPIO.input(ENCODER_DT)
    
    if clk_state != last_clk_state:
        # 更新最后触发时间
        last_trigger_time = time.time()
        # 增加状态变化阈值检查
        if dt_state != clk_state:
            encoder_counter += 1
        else:
            encoder_counter -= 1
        
        # 修改为双向绝对值判断
        if abs(encoder_counter) >= 4:
            frame = capture_frame()
            if frame is not None:
                try:  # 增加异常捕获
                    send_via_mqtt(frame)
                except Exception as e:
                    print(f"发送过程中发生异常: {str(e)}")
                finally:
                    encoder_counter = 0  # 确保计数器重置

# 修改主循环部分
if __name__ == "__main__":
    # 确保客户端已初始化
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)  # 移动认证设置到此处
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()
        print("MQTT客户端已连接")
    except Exception as e:
        print(f"MQTT初始化连接失败: {str(e)}")
        client = None  # 确保client变量存在
    
    try:
        print("Ctrl+c  退出程序")
        last_capture_time = time.time()
        while True:
            # 树莓派环境超时检测
            if RUN_ENV == "raspberry":
                current_time = time.time()
                # 同时检测超时和定时器
                if current_time - last_trigger_time >= TIMEOUT_INTERVAL:
                    frame = capture_frame()
                    if frame is not None:
                        print("空闲超时，自动拍摄")
                        send_via_mqtt(frame)
                        last_trigger_time = current_time  # 重置超时计时器
                        
            # Windows环境原有定时逻辑保持不变
            if RUN_ENV == "windows":
                # 定时触发逻辑
                current_time = time.time()
                if current_time - last_capture_time >= TIMER_INTERVAL:  # 使用配置变量
                    frame = capture_frame()
                    if frame is not None:
                        cv2.imshow('Preview', frame)
                        print("定时捕获，正在发送 MQTT 图像")
                        send_via_mqtt(frame)
                        last_capture_time = current_time  # 重置计时器
                    
                # 保持窗口响应
                cv2.waitKey(100)  # 适当延长等待时间

            time.sleep(0.1)

    except KeyboardInterrupt:
        if RUN_ENV == "windows" and cap.isOpened():
            cap.release()  # 正确释放摄像头资源
        if RUN_ENV == "raspberry":
            GPIO.cleanup()
        cv2.destroyAllWindows()  # 退出时关闭所有OpenCV窗口
        client.loop_stop()  # 停止网络线程
        client.disconnect()  # 断开连接