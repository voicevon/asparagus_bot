# pip install opencv-python paho-mqtt
import cv2
import paho.mqtt.client as mqtt
import numpy as np
import time

# MQTT配置
MQTT_BROKER = "voicevon.vicp.io"
MQTT_PORT = 1883
MQTT_TOPIC = "as_p8/capture"
MQTT_COUNTER_TOPIC = "as_p8/counter"
MQTT_USERNAME = "von"
MQTT_PASSWORD = "von1970"
TIMER_INTERVAL = 0.5

# 全局变量
image_counter = 0
client = mqtt.Client()
cap = cv2.VideoCapture(0)

def capture_frame():
    """从摄像头捕获一帧图像"""
    if not cap.isOpened():
        print("无法打开摄像头")
        return None
    
    ret, frame = cap.read()
    return frame if ret else None

def send_via_mqtt(image):
    """通过MQTT发送图像"""
    global image_counter
    _, img_encoded = cv2.imencode('.jpg', image)
    
    try:
        client.publish(MQTT_TOPIC, img_encoded.tobytes())
        print(f"发送成功 计数器：{image_counter}")
        
        image_counter += 1
        client.publish(MQTT_COUNTER_TOPIC, image_counter)
        
    except Exception as e:
        print(f"发送失败: {str(e)}")

if __name__ == "__main__":
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()
        last_capture = time.time()
        
        while True:
            # 定时捕获逻辑
            if time.time() - last_capture >= TIMER_INTERVAL:
                frame = capture_frame()
                if frame is not None:
                    cv2.imshow('Preview', frame)
                    send_via_mqtt(frame)
                    last_capture = time.time()
                
                if cv2.waitKey(100) == ord('q'):
                    break
                    
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        client.loop_stop()
        client.disconnect()
