import cv2
import numpy as np
import math

def analyze_asparagus(image):
    """分析芦笋参数
    返回：{
        'diameter': 直径(mm),
        'green_length': 绿色部分长度(mm),
        'curvature': 弯曲度(0-1)
    }
    """
    # 预处理
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 轮廓检测
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # 获取最大轮廓
    main_contour = max(contours, key=cv2.contourArea)
    
    # 在直径计算后添加长度计算
    # 直径分析（使用最小外接圆）
    (x, y), radius = cv2.minEnclosingCircle(main_contour)
    diameter = round(radius * 2, 1)  # 假设1像素=1mm
    
    # 新增视野内长度计算（从图像顶部到底部轮廓）
    top_point = np.min(main_contour[:,0,1])  # 轮廓最顶端Y坐标
    bottom_point = np.max(main_contour[:,0,1])  # 轮廓最底端Y坐标
    visible_length = bottom_point - top_point  # 视野内可见长度（像素）
    
    # 总长度 = 视野内长度 + 固定120mm
    total_length = visible_length + 120  # 假设1像素=1mm
    
    # 添加完整计算流程
    [vx, vy, x0, y0] = cv2.fitLine(main_contour, cv2.DIST_L2, 0, 0.01, 0.01)
    green_length = calculate_green_length(green_mask, vx, vy, x0, y0)
    curvature = calculate_curvature(main_contour, vx, vy, x0, y0)
    
    # 修正长度计算
    visible_length_px = bottom_point - top_point
    visible_length_mm = visible_length_px * PIXEL_TO_MM
    total_length = visible_length_mm + FIXED_LENGTH
    
    return {
        'diameter': diameter * PIXEL_TO_MM,  # 直径也需要转换
        'green_length': green_length,
        'curvature': round(curvature, 2),
        'total_length': round(total_length, 1)
    }

def calculate_green_length(mask, vx, vy, x0, y0):
    """沿主轴方向计算绿色部分长度"""
    # 创建采样线段（每5像素采样）
    step = 5
    max_length = 0
    current_green = 0
    
    # 可添加标定参数（在文件开头）
    # 标定参数
    PIXEL_TO_MM = 0.5  # 需要实际标定
    FIXED_LENGTH = 120  # 视野外固定长度(mm)
    
    # 修改长度计算部分
    visible_length_mm = visible_length * PIXEL_TO_MM
    total_length = visible_length_mm + 120
    
    for t in np.arange(-1000, 1000, step):
        px = int(x0 + t*vx)
        py = int(y0 + t*vy)
        if 0 <= px < mask.shape[1] and 0 <= py < mask.shape[0]:
            if mask[py, px] == 255:
                current_green += step
                max_length = max(max_length, current_green)
            else:
                current_green = 0
                
    return max_length

def calculate_curvature(contour, line_points):
    """通过轮廓点与拟合线的平均距离计算弯曲度"""
    total_dist = 0
    for point in contour[:,0,:]:
        dist = cv2.pointPolygonTest(line_points, tuple(point), True)
        total_dist += abs(dist)
    
    avg_dist = total_dist / len(contour)
    # 标准化弯曲度（假设超过10像素为完全弯曲）
    return min(avg_dist / 10, 1.0)


def batch_analyze_asparagus(directory):
    """批量分析目录中的芦笋图像"""
    import os
    import csv
    
    # 获取目录下所有图像文件（支持常见格式）
    image_exts = ['.jpg', '.jpeg', '.png', '.bmp']
    files = sorted([f for f in os.listdir(directory) 
                   if os.path.splitext(f)[1].lower() in image_exts])
    
    # 创建结果保存目录
    result_dir = os.path.join(directory, "analysis_results")
    os.makedirs(result_dir, exist_ok=True)
    
    # 准备CSV报告
    csv_path = os.path.join(result_dir, "report.csv")
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['文件名', '直径(mm)', '总长度(mm)', '绿色部分(mm)', '弯曲度'])
        
        for filename in files:
            filepath = os.path.join(directory, filename)
            image = cv2.imread(filepath)
            if image is None:
                print(f"无法读取文件: {filename}")
                continue
                
            result = analyze_asparagus(image)
            if result:
                # 保存分析结果图像
                result_img = image.copy()
                cv2.putText(result_img, f"D:{result['diameter']}mm", (10,30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                cv2.imwrite(os.path.join(result_dir, f"result_{filename}"), result_img)
                
                # 写入CSV
                writer.writerow([
                    filename,
                    result['diameter'],
                    result['total_length'],
                    result['green_length'],
                    result['curvature']
                ])
                print(f"已处理: {filename}")
                
    print(f"分析完成！结果保存在: {csv_path}")

if __name__ == "__main__":
    # 使用示例（分析指定目录）
    batch_analyze_asparagus("saved_images")  # 修改为实际目录路径
    
    # 原测试代码保留
    # image = cv2.imread("asparagus.jpg")
    # result = analyze_asparagus(image)
    # ...