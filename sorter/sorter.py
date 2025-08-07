import cv2
import numpy as np

def measure_asparagus(image_path):
    # 读取图像并转换为HSV颜色空间
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # 定义芦笋颜色的HSV范围（需根据实际颜色调整）
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # 形态学操作去噪
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # 取最大轮廓
    max_contour = max(contours, key=cv2.contourArea)
    
    # 获取最小外接矩形
    rect = cv2.minAreaRect(max_contour)
    (x, y), (w, h), angle = rect
    
    # 计算实际尺寸（假设每像素=0.1mm，需根据实际标定）
    pixel_to_mm = 0.1
    length = max(w, h) * pixel_to_mm
    diameter = min(w, h) * pixel_to_mm
    
    return length, diameter

# 使用示例
if __name__ == "__main__":
    result = measure_asparagus("asparagus.jpg")
    if result:
        print(f"长度：{result[0]:.1f}mm，直径：{result[1]:.1f}mm")
    else:
        print("未检测到芦笋")
