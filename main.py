
import pyrealsense2 as rs

import numpy as np

import cv2

import os

# 创建保存图像的文件夹

save_folder = "capturedimages"

if not os.path.exists(save_folder):

    os.makedirs(save_folder)

# 创建一个管道

pipeline = rs.pipeline()

# 配置管道

config = rs.config()

config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)

config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)

# 启动管道，无需传递配置参数

pipeline.start()  

def captureandsave_images():

    global frame_count

    # 等待获取一帧数据

    frames = pipeline.wait_for_frames()

    # 获取彩色图像帧

    colorframe = frames.get_color_frame()

    # 获取深度图像帧

    depthframe = frames.get_depth_frame()

    if not colorframe or not depthframe:

        return

    # 将图像帧转换为 numpy 数组

    color_image = np.asanyarray(colorframe.get_data())

    depth_image = np.asanyarray(depthframe.get_data())

    # 显示彩色图像

    cv2.imshow('Color Image', color_image)

    # 显示深度图像（通常需要进行一些处理来更好地可视化）

    depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

    cv2.imshow('Depth Image', depth_colormap)

    # 保存彩色图像

    cv2.imwrite(os.path.join(save_folder, f"color{frame_count}.jpg"), color_image)

    # 保存深度图像

    cv2.imwrite(os.path.join(save_folder, f"depth{frame_count}.jpg"), depth_colormap)

    frame_count += 1

try:

    frame_count = 0

    continue_capture = True

    while True:

        captureandsave_images()

        key = cv2.waitKey(3000)

        if key & 0xFF == ord('q'):
            break

        elif key & 0xFF == ord('c'):
            continue_capture = not continue_capture

        if not continue_capture:
            break

finally:

    # 停止管道

    pipeline.stop()

    cv2.destroyAllWindows()