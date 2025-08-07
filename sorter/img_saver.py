import paho.mqtt.client as mqtt
import cv2
import numpy as np
import os
import time

# MQTT配置（与capture.py保持一致）
MQTT_BROKER = "voicevon.vicp.io"
MQTT_PORT = 1883
MQTT_TOPIC = "as_p8/capture"
MQTT_USERNAME = "von"
MQTT_PASSWORD = "von1970"

# 保存路径配置
SAVE_DIR = "saved_images"  # 默认保存目录
# 仅在目录不存在时创建
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)
    print(f"创建保存目录：{SAVE_DIR}")

def on_connect(client, userdata, flags, rc):
    print("连接成功" if rc == 0 else f"连接失败，错误码：{rc}")

def on_message(client, userdata, msg):
    try:
        # 将字节数据转为numpy数组
        img_data = np.frombuffer(msg.payload, dtype=np.uint8)
        # 解码图像
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        
        if img is not None:
            # 生成带时间戳的文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{SAVE_DIR}/capture_{timestamp}.jpg"
            cv2.imwrite(filename, img)
            print(f"图像已保存至：{filename}")
        else:
            print("图像解码失败")
    except Exception as e:
        print(f"处理消息时发生错误：{str(e)}")

def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPIC)
        print(f"开始监听主题：{MQTT_TOPIC}")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n程序终止")
    except Exception as e:
        print(f"MQTT连接异常：{str(e)}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
