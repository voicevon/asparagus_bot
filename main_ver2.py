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
config.enable_stream(rs.stream.color, 1280, 720, rs.format.rgb8, 6)
config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 6)

# 启动管道
pipeline.start(config)

def capture_and_save_images(do_save):
    global frame_count

    # 等待获取一帧数据
    frames = pipeline.wait_for_frames()

    # 获取彩色图像帧和深度图像帧
    color_frame = frames.get_color_frame()
    depth_frame = frames.get_depth_frame()

    if not color_frame or not depth_frame:
        return

    # 将图像帧转换为 numpy 数组
    color_image = np.asanyarray(color_frame.get_data())
    color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)
    depth_image = np.asanyarray(depth_frame.get_data())

    # 显示彩色图像和深度图像
    cv2.imshow('Color Image', color_image)
    # 将深度图的最大值设置为1米（1000毫米）
    depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=255.0/1000.0), cv2.COLORMAP_JET)
    cv2.imshow('Depth Image', depth_colormap)

    if do_save:
        # 保存彩色图像和深度图像
        cv2.imwrite(os.path.join(save_folder, f"color{frame_count}.jpg"), color_image)
        cv2.imwrite(os.path.join(save_folder, f"depth{frame_count}.png"), depth_image.astype(np.uint16))
        frame_count += 1
        print(f"File saved, index= {frame_count}")

try:
    frame_count = 0
    continue_capture = True
    do_save = False

    while continue_capture:
        capture_and_save_images(do_save)
        do_save = False
        key = cv2.waitKey(20)

        if key & 0xFF == ord('q'):
            break
        elif key & 0xFF == ord(' '):
            do_save = True

finally:
    # 停止管道
    pipeline.stop()
    cv2.destroyAllWindows()