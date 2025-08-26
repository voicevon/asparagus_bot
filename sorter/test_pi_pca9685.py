import time
import smbus2
import logging
from dataclasses import dataclass
from typing import Tuple, List, Optional

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('PCA9685')

# ========== 颜色常量定义 ==========
COLOR_RED = '\x1b[31m'
COLOR_GREEN = '\x1b[32m'
COLOR_YELLOW = '\x1b[33m'
COLOR_BLUE = '\x1b[34m'
COLOR_RESET = '\x1b[0m'

# ========== PCA9685寄存器常量定义 ==========
PCA9685_MODE1_REG = 0x00
PCA9685_MODE2_REG = 0x01
PCA9685_PRESCALE_REG = 0xFE
PCA9685_LED0_ON_L = 0x06

# MODE1寄存器位定义
MODE1_ALLCALL = 0x01
MODE1_SUB3 = 0x02
MODE1_SUB2 = 0x04
MODE1_SUB1 = 0x08
MODE1_SLEEP = 0x10
MODE1_AI = 0x20
MODE1_EXTCLK = 0x40
MODE1_RESTART = 0x80

# MODE2寄存器位定义
MODE2_OUTNE1 = 0x01
MODE2_OUTNE0 = 0x02
MODE2_OUTDRV = 0x04
MODE2_OCH = 0x08
MODE2_INVRT = 0x10

@dataclass
class I2CResponse:
    success: bool
    data: Optional[List[int]] = None
    error: Optional[str] = None
    register: Optional[int] = None
    attempts: int = 0

class PCA9685:
    def __init__(self, address: int =0x40, bus_number: int =1, debug: bool =True):
        self.address = address
        self.bus_number = bus_number
        self.bus = None
        self.debug = debug
        self.initialized = False
        self.prescale_value = None
        self.frequency = None
        self.initialize()

    def initialize(self) -> None:
        """完整初始化流程，包含多重校验"""
        logger.info(f"初始化PCA9685 (地址: 0x{self.address:02X}, 总线: {self.bus_number})")

        # 1. 初始化I2C总线
        try:
            self.bus = smbus2.SMBus(self.bus_number)
            logger.debug(f"成功打开I2C总线 {self.bus_number}")
        except Exception as e:
            raise RuntimeError(f"I2C总线初始化失败: {str(e)}") from e

        # 2. 读取初始寄存器状态
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not mode1.success:
            raise RuntimeError(f"无法读取MODE1寄存器: {mode1.error}")
        logger.debug(f"初始MODE1寄存器值: 0x{mode1.data[0]:02X}")

        # 3. 执行软复位
        reset_result = self._write_register(PCA9685_MODE1_REG, MODE1_RESTART)
        if not reset_result.success:
            raise RuntimeError(f"软复位失败: {reset_result.error}")
        time.sleep(0.01)

        # 4. 验证复位状态
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not mode1.success or (mode1.data[0] & MODE1_RESTART):
            raise RuntimeError(f"复位验证失败，MODE1值: 0x{mode1.data[0]:02X}")

        # 5. 配置基本模式
        self._configure_basic_mode()

        # 6. 设置PWM频率为50Hz
        self.set_pwm_freq(50)

        # 7. 验证所有关键寄存器配置
        self._verify_initialization()

        self.initialized = True
        logger.info("PCA9685初始化完成并通过验证")

    def _configure_basic_mode(self) -> None:
        """配置基本工作模式，修复寄存器设置"""
        # 配置MODE1: 启用ALLCALL和AI(自动递增)模式
        mode1_config = MODE1_ALLCALL | MODE1_AI
        result = self._write_register_with_verify(PCA9685_MODE1_REG, mode1_config)
        if not result.success:
            raise RuntimeError(f"MODE1配置失败: {result.error}")
        # 验证AI位是否正确设置
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not (mode1.data[0] & MODE1_AI):
            raise RuntimeError(f"AI模式未启用，MODE1值: 0x{mode1.data[0]:02X}")

        # 配置MODE2: 图腾柱输出, 正常极性, 高驱动强度
        mode2_config = MODE2_OUTDRV | 0x08  # 添加0x08设置高驱动
        result = self._write_register_with_verify(PCA9685_MODE2_REG, mode2_config)
        if not result.success:
            raise RuntimeError(f"MODE2配置失败: {result.error}")

    def _verify_initialization(self) -> None:
        """验证所有关键寄存器的初始配置"""
        # 验证MODE1
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not mode1.success or (mode1.data[0] & MODE1_ALLCALL) != MODE1_ALLCALL:
            raise RuntimeError(f"MODE1验证失败，值: 0x{mode1.data[0]:02X}")

        # 验证MODE2
        mode2 = self._read_register(PCA9685_MODE2_REG)
        if not mode2.success or (mode2.data[0] & MODE2_OUTDRV) != MODE2_OUTDRV:
            raise RuntimeError(f"MODE2验证失败，值: 0x{mode2.data[0]:02X}")

        # 验证预分频器
        prescale = self._read_register(PCA9685_PRESCALE_REG)
        if not prescale.success or prescale.data[0] != self.prescale_value:
            raise RuntimeError(f"预分频器验证失败，预期: {self.prescale_value}, 实际: {prescale.data[0]}")

    def set_pwm_freq(self, freq: float) -> None:
        """设置PWM频率，带完整计算验证"""
        if freq < 24 or freq > 1526:
            raise ValueError(f"频率超出范围 (24-1526Hz): {freq}Hz")

        logger.info(f"设置PWM频率: {freq}Hz")

        # 1. 计算预分频值
        prescale_value = 25000000.0 / (4096.0 * freq) - 1
        self.prescale_value = int(round(prescale_value))
        logger.debug(f"频率计算: {freq}Hz → 预分频值: {prescale_value:.2f} → 取整: {self.prescale_value}")

        # 2. 进入睡眠模式
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not mode1.success:
            raise RuntimeError(f"读取MODE1失败: {mode1.error}")

        original_mode1 = mode1.data[0]
        sleep_mode = original_mode1 | MODE1_SLEEP
        result = self._write_register_with_verify(PCA9685_MODE1_REG, sleep_mode)
        if not result.success:
            raise RuntimeError(f"进入睡眠模式失败: {result.error}")

        # 3. 设置预分频器
        result = self._write_register_with_verify(PCA9685_PRESCALE_REG, self.prescale_value)
        if not result.success:
            raise RuntimeError(f"设置预分频器失败: {result.error}")

        # 4. 退出睡眠模式
        result = self._write_register_with_verify(PCA9685_MODE1_REG, original_mode1)
        if not result.success:
            raise RuntimeError(f"退出睡眠模式失败: {result.error}")

        # 5. 等待振荡器稳定
        time.sleep(0.005)

        # 6. 验证频率设置
        actual_freq = 25000000.0 / ((self.prescale_value + 1) * 4096)
        self.frequency = actual_freq
        logger.info(f"频率设置完成: 目标 {freq}Hz, 实际 {actual_freq:.2f}Hz")

        # 7. 验证MODE1寄存器已唤醒
        mode1 = self._read_register(PCA9685_MODE1_REG)
        if not mode1.success or (mode1.data[0] & MODE1_SLEEP):
            raise RuntimeError(f"设备仍处于睡眠模式，MODE1值: 0x{mode1.data[0]:02X}")

    def set_pwm_with_retry(self, channel: int, on: int, off: int, max_retries: int = 5) -> bool:
        """带重试机制的PWM设置，修复数据格式"""
        if not self.initialized:
            raise RuntimeError("设备未初始化，请先调用initialize()")

        if not 0 <= channel <= 15:
            raise ValueError(f"通道号超出范围 (0-15): {channel}")

        if not 0 <= on <= 4095 or not 0 <= off <= 4095:
            raise ValueError(f"PWM值超出范围 (0-4095): on={on}, off={off}")

        logger.debug(f"设置PWM通道 {channel}: on={on}, off={off} (最大重试: {max_retries})")

        # 计算PWM寄存器地址（修复地址计算）
        reg_addr = PCA9685_LED0_ON_L + 4 * channel
        logger.debug(f"PWM通道{channel}寄存器地址: 0x{reg_addr:02X}")

        # 准备数据（确保正确的字节顺序）
        on_low = on & 0xFF
        on_high = (on >> 8) & 0xFF
        off_low = off & 0xFF
        off_high = (off >> 8) & 0xFF
        data = [on_low, on_high, off_low, off_high]
        logger.debug(f"PWM数据: ON=0x{on:04X}({on}), OFF=0x{off:04X}({off}) → 字节序列:{data}")

        # 带重试的写入和验证
        for attempt in range(max_retries):
            # 写入数据（使用自动递增模式连续写入4字节）
            write_result = self._write_block(reg_addr, data)
            if not write_result.success:
                logger.warning(f"写入尝试 {attempt+1} 失败: {write_result.error}")
                self._reset_i2c_bus()
                continue

            # 读取验证
            read_result = self._read_block(reg_addr, 4)
            if not read_result.success:
                logger.warning(f"读取尝试 {attempt+1} 失败: {read_result.error}")
                continue

            # 数据比较
            if read_result.data == data:
                logger.debug(f"PWM通道 {channel} 设置成功 (尝试 {attempt+1}/{max_retries})")
                return True
            else:
                logger.warning(f"数据不匹配 - 尝试 {attempt+1}/{max_retries}:\n写入: {data} → 0x{on:04X},{off:04X}\n读取: {read_result.data} → 0x{(read_result.data[1]<<8)|read_result.data[0]:04X},{(read_result.data[3]<<8)|read_result.data[2]:04X}")
                time.sleep(0.01)

        logger.error(f"超过最大重试次数 ({max_retries})，PWM通道 {channel} 设置失败")
        return False

    def check_status(self) -> None:
        """全面状态检查和报告"""
        logger.info("\n=== PCA9685状态检查 ===")

        # 1. 基本信息
        logger.info(f"I2C地址: 0x{self.address:02X}")
        logger.info(f"I2C总线: {self.bus_number}")
        logger.info(f"初始化状态: {'已完成' if self.initialized else '未完成'}")
        logger.info(f"PWM频率: {self.frequency:.2f}Hz (预分频值: {self.prescale_value})")

        # 2. 寄存器状态
        mode1 = self._read_register(PCA9685_MODE1_REG)
        mode2 = self._read_register(PCA9685_MODE2_REG)
        prescale = self._read_register(PCA9685_PRESCALE_REG)

        if mode1.success:
            mode1_val = mode1.data[0]
            logger.info(f"MODE1寄存器: 0x{mode1_val:02X} → {self._decode_mode1(mode1_val)}")
        else:
            logger.error(f"读取MODE1寄存器失败: {mode1.error}")

        if mode2.success:
            mode2_val = mode2.data[0]
            logger.info(f"MODE2寄存器: 0x{mode2_val:02X} → {self._decode_mode2(mode2_val)}")
        else:
            logger.error(f"读取MODE2寄存器失败: {mode2.error}")

        if prescale.success:
            logger.info(f"预分频寄存器: 0x{prescale.data[0]:02X} (值: {prescale.data[0]})")
        else:
            logger.error(f"读取预分频寄存器失败: {prescale.error}")

        # 3. 功能验证
        logger.info("\n=== 功能验证 ===")
        self._verify_all_channels_idle()

        logger.info("=== 状态检查完成 ===\n")

    def scan_all_channels(self) -> None:
        """扫描所有PWM通道的当前状态"""
        logger.info("\n=== 所有PWM通道状态扫描 ===")
        for channel in range(16):
            reg_addr = PCA9685_LED0_ON_L + 4 * channel
            result = self._read_block(reg_addr, 4)
            if result.success:
                on = (result.data[1] << 8) | result.data[0]
                off = (result.data[3] << 8) | result.data[2]
                logger.info(f"通道 {channel:2d}: 0x{reg_addr:02X} → on={on:4d}, off={off:4d} ({off/4095*100:.1f}%)")
            else:
                logger.error(f"通道 {channel:2d}: 读取失败 - {result.error}")
        logger.info("=== 扫描完成 ===\n")

    def _read_register(self, reg: int) -> I2CResponse:
        """读取单个寄存器，带错误处理"""
        try:
            data = self.bus.read_i2c_block_data(self.address, reg, 1)
            return I2CResponse(success=True, data=data, register=reg)
        except Exception as e:
            return I2CResponse(success=False, error=str(e), register=reg)

    def _write_register(self, reg: int, value: int) -> I2CResponse:
        """写入单个寄存器，带错误处理"""
        try:
            self.bus.write_byte_data(self.address, reg, value)
            return I2CResponse(success=True, register=reg)
        except Exception as e:
            return I2CResponse(success=False, error=str(e), register=reg)

    def _write_register_with_verify(self, reg: int, value: int) -> I2CResponse:
        """写入寄存器并验证"""
        write_result = self._write_register(reg, value)
        if not write_result.success:
            return write_result

        # 读取验证
        read_result = self._read_register(reg)
        if not read_result.success:
            return read_result

        if read_result.data[0] != value:
            return I2CResponse(
                success=False,
                error=f"验证失败: 写入0x{value:02X}, 读取0x{read_result.data[0]:02X}",
                register=reg
            )

        return I2CResponse(success=True, data=read_result.data, register=reg)

    def _read_block(self, reg: int, length: int) -> I2CResponse:
        """读取寄存器块，带错误处理"""
        try:
            data = self.bus.read_i2c_block_data(self.address, reg, length)
            return I2CResponse(success=True, data=data, register=reg)
        except Exception as e:
            return I2CResponse(success=False, error=str(e), register=reg)

    def _write_block(self, reg: int, data: List[int]) -> I2CResponse:
        """写入寄存器块，带错误处理"""
        try:
            self.bus.write_i2c_block_data(self.address, reg, data)
            return I2CResponse(success=True, register=reg)
        except Exception as e:
            return I2CResponse(success=False, error=str(e), register=reg)

    def _reset_i2c_bus(self) -> bool:
        """重置I2C总线"""
        try:
            if self.bus:
                self.bus.close()
                time.sleep(0.01)
            self.bus = smbus2.SMBus(self.bus_number)
            logger.debug("I2C总线重置成功")
            return True
        except Exception as e:
            logger.error(f"I2C总线重置失败: {str(e)}")
            return False

    def _verify_all_channels_idle(self) -> None:
        """验证所有通道处于空闲状态"""
        for channel in range(16):
            reg_addr = PCA9685_LED0_ON_L + 4 * channel
            result = self._read_block(reg_addr, 4)
            if result.success:
                on = (result.data[1] << 8) | result.data[0]
                off = (result.data[3] << 8) | result.data[2]
                if on != 0 or off != 0:
                    logger.warning(f"通道 {channel} 非空闲: on={on}, off={off}")
            else:
                logger.error(f"通道 {channel} 状态检查失败: {result.error}")

    @staticmethod
    def _decode_mode1(value: int) -> str:
        """解码MODE1寄存器值为可读状态"""
        parts = []
        parts.append("重启" if value & MODE1_RESTART else "运行")
        parts.append("外部时钟" if value & MODE1_EXTCLK else "内部时钟")
        parts.append("AI模式" if value & MODE1_AI else "普通模式")
        parts.append("睡眠" if value & MODE1_SLEEP else "唤醒")
        parts.append("SUB1" if value & MODE1_SUB1 else "")
        parts.append("SUB2" if value & MODE2_INVRT else "")
        parts.append("SUB3" if value & MODE1_SUB3 else "")
        parts.append("ALLCALL" if value & MODE1_ALLCALL else "")
        return ", ".join(filter(None, parts))

    @staticmethod
    def _decode_mode2(value: int) -> str:
        """解码MODE2寄存器值为可读状态"""
        parts = []
        parts.append("图腾柱" if value & MODE2_OUTDRV else "开漏")
        parts.append("反转极性" if value & MODE2_INVRT else "正常极性")
        parts.append("高驱动" if value & 0x08 else "低驱动")
        return ", ".join(parts)

    def close(self) -> None:
        """关闭设备，释放资源"""
        if self.bus:
            try:
                # 重置所有PWM通道
                for channel in range(16):
                    self.set_pwm_with_retry(channel, 0, 0, max_retries=2)
                # 进入低功耗模式
                self._write_register(PCA9685_MODE1_REG, MODE1_SLEEP)
                self.bus.close()
                logger.info("PCA9685已关闭并重置")
            except Exception as e:
                logger.error(f"关闭过程中出错: {str(e)}")
            finally:
                self.bus = None
                self.initialized = False

# 舵机控制函数
def angle_to_pulse(angle: float) -> int:
    """将角度转换为PWM脉冲宽度，带安全限制"""
    MIN_ANGLE = [0, 500]    # [角度, 微秒]
    MAX_ANGLE = [180, 2500] # [角度, 微秒]
    PWM_FREQ = 50
    PWM_PERIOD_US = 1000000 / PWM_FREQ  # 20000μs

    # 限制角度范围
    angle = max(0, min(180, angle))

    # 线性插值计算微秒值
    pulse_us = MIN_ANGLE[1] + (MAX_ANGLE[1] - MIN_ANGLE[1]) * (angle - MIN_ANGLE[0]) / (MAX_ANGLE[0] - MIN_ANGLE[0])

    # 转换为PCA9685的12位步数
    pulse_steps = int(round(pulse_us * 4096 / PWM_PERIOD_US))

    # 安全限制
    SAFE_MIN = 102  # ~500μs
    SAFE_MAX = 512  # ~2500μs
    pulse_steps = max(SAFE_MIN, min(SAFE_MAX, pulse_steps))

    logger.debug(f"角度转换: {angle}° → {pulse_us:.1f}μs → {pulse_steps}步 (安全范围: {SAFE_MIN}-{SAFE_MAX})")
    return pulse_steps

# 主测试程序
def main():
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )

    # 测试参数
    TEST_CHANNEL = 14
    TEST_CYCLES = 3
    ANGLE_SEQUENCE = [0, 90, 180, 90, 0]
    DELAY_SECONDS = 2

    pca = None
    try:
        # 创建PCA9685实例
        pca = PCA9685(debug=True)

        # 显示初始状态
        pca.check_status()
        pca.scan_all_channels()

        # 运行测试循环
        logger.info(f"开始舵机测试 (通道: {TEST_CHANNEL}, 循环: {TEST_CYCLES})")
        for cycle in range(TEST_CYCLES):
            logger.info(f"\n=== 测试循环 {cycle+1}/{TEST_CYCLES} ===")
            for angle in ANGLE_SEQUENCE:
                pulse = angle_to_pulse(angle)
                logger.info(f"设置舵机角度: {angle}° (脉冲: {pulse})")
                success = pca.set_pwm_with_retry(TEST_CHANNEL, 0, pulse)
                if not success:
                    logger.error(f"无法设置角度 {angle}°")
                    # 尝试恢复
                    pca.scan_all_channels()
                time.sleep(DELAY_SECONDS)

        logger.info("\n所有测试循环完成")
        pca.scan_all_channels()

    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}", exc_info=True)
    finally:
        if pca:
            pca.close()

    def run_diagnostic_test(self) -> None:
        """运行全面诊断测试"""
        logger.info("\n=== PCA9685全面诊断测试 ===")
    
        # 1. 测试AI模式
        self.bus.write_byte_data(self.address, PCA9685_MODE1_REG, MODE1_ALLCALL | MODE1_AI)
        time.sleep(0.005)
        mode1 = self.bus.read_byte_data(self.address, PCA9685_MODE1_REG)
        if not (mode1 & MODE1_AI):
            logger.error("❌ AI模式启用失败")
        else:
            logger.info("✅ AI模式已启用")
    
        # 2. 测试PWM通道0直接写入
        test_data = [0x00, 0x00, 0xFF, 0x00]  # ON=0, OFF=255
        self.bus.write_i2c_block_data(self.address, 0x06, test_data)
        time.sleep(0.01)
        read_data = self.bus.read_i2c_block_data(self.address, 0x06, 4)
        if read_data == test_data:
            logger.info("✅ PWM通道0直接写入测试成功")
        else:
            logger.error(f"❌ PWM通道0直接写入测试失败: 预期{test_data}, 实际{read_data}")
    
        # 3. 测试多通道连续写入
        self.bus.write_i2c_block_data(self.address, 0x06, [0x00,0x00,0x01,0x00])  # 通道0
        self.bus.write_i2c_block_data(self.address, 0x0A, [0x00,0x00,0x02,0x00])  # 通道1
        self.bus.write_i2c_block_data(self.address, 0x0E, [0x00,0x00,0x03,0x00])  # 通道2
        time.sleep(0.01)
        c0 = self.bus.read_i2c_block_data(self.address, 0x06, 4)
        c1 = self.bus.read_i2c_block_data(self.address, 0x0A, 4)
        c2 = self.bus.read_i2c_block_data(self.address, 0x0E, 4)
        if c0 == [0x00,0x00,0x01,0x00] and c1 == [0x00,0x00,0x02,0x00] and c2 == [0x00,0x00,0x03,0x00]:
            logger.info("✅ 多通道连续写入测试成功")
        else:
            logger.error(f"❌ 多通道连续写入测试失败: c0={c0}, c1={c1}, c2={c2}")
    
        logger.info("=== 诊断测试完成 ===\n")

        logger.info("=== 状态检查完成 ===\n")

if __name__ == "__main__":
    main()