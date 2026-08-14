# STM32CubeLovesArduino 🔄

STM32 CubeMX 工程 → Arduino 工程 一键转换工具
One-click converter from STM32CubeMX project to Arduino project.

**中文** · [English](#english)

---

## 中文

### 简介

带 GUI 的 Python 工具，将 STM32CubeMX 生成的工程代码自动转换为 Arduino 工程，让你在 Arduino IDE 中直接使用 HAL 库驱动 STM32 外设，无需手写中断处理函数和 HAL 配置样板代码。

### 功能特性

- Win10 风格图形界面
- 中英文切换（配置持久化保存）
- 一键选择工程目录
- 自动检测外设并生成 `HAL_XXX_MODULE_ONLY` / `HAL_XXX_MODULE_ENABLED`
- 自动从 `stm32*_it.c` 提取中断处理函数到 `ArduinoIT.h`
- 增量合并：中断函数只增不删，用户修改保留
- 幂等处理：重复运行不会重复注入代码
- 保留用户修改：`.ino` 不覆盖，`HSE_VALUE` 数值保留

### 运行要求

- Python 3.7+（Windows / Linux / macOS）
- 仅标准库，无第三方依赖

```bash
python STM32CubeLovesArduino.py
```

> Windows 下将扩展名改为 `.pyw` 可隐藏控制台窗口。

### 使用方法

1. 用 STM32CubeMX 生成工程（配置好外设）
2. 运行本工具，点击「选择文件夹并处理」
3. 选择 CubeMX 工程根目录
4. 工具自动完成：修改 `main.c` / `msp.c`、生成 `.ino`、`ArduinoIT.h`、`hal_conf_extra.h`
5. 用 Arduino IDE 打开 `.ino`，选择对应 STM32 开发板编译上传

### 生成文件

| 文件 | 说明 | 保留用户修改 |
|---|---|---|
| `<工程名>.ino` | Arduino 主文件，包含 main.c 和 msp.c | ✅ 不覆盖 |
| `ArduinoIT.h` | 自动提取的中断处理函数 | ✅ 只增不删 |
| `hal_conf_extra.h` | HAL 模块配置 | ⚠️ 每次重写，仅保留 `HSE_VALUE` 数值 |
| `main.c` / `*_hal_msp.c` | 注入 `#ifndef USE_ARDUINO` 包裹 | ✅ 幂等 |

#### 中断处理函数管理

从 `stm32*_it.c` 自动提取外设中断处理函数，自动排除 Arduino 核心已提供的标准 Cortex-M 异常处理函数（`NMI_Handler`、`SysTick_Handler` 等）。

`ArduinoIT.h` 采用只增不删策略：

- **新增函数** → 追加到文件末尾
- **it.c 中移除的函数** → 用 `//` 注释保留，标记 `// --deprecated`
- **重新加入的函数** → 自动恢复，保留用户手动修改

```cpp
// 示例：it.c 移除 SPI1 中断后的状态
// extern "C" void SPI1_IRQHandler(void)  // --deprecated
// {
//   HAL_SPI_IRQHandler(&hspi1);
// }
```

### HAL 外设配置

自动扫描 `main.c` 中的外设句柄，生成模块配置：

| 外设 | 句柄前缀 | 生成的宏 |
|---|---|---|
| ADC | `hadc` | `HAL_ADC_MODULE_ONLY` |
| SPI | `hspi` | `HAL_SPI_MODULE_ONLY` |
| I2C | `hi2c` | `HAL_I2C_MODULE_ONLY` |
| UART | `huart` / `husart` | `HAL_UART_MODULE_ONLY` |
| TIM | `htim` | `HAL_TIM_MODULE_ONLY` |
| RTC | `hrtc` | `HAL_RTC_MODULE_ONLY` |
| PWR | `hpwr` | `HAL_PWR_MODULE_ONLY` |
| FDCAN | `hfdcan` | `HAL_FDCAN_MODULE_ENABLED` |
| CAN | `hcan` | `HAL_CAN_MODULE_ENABLED` |
| DAC | `hdac` | `HAL_DAC_MODULE_ENABLED` |

> 默认启用的模块（ADC/I2C/SPI/TIM/UART 等）用 `MODULE_ONLY` 禁用 Arduino 封装；默认禁用的模块（CAN/DAC/FDCAN 等）需用 `MODULE_ENABLED` 先启用 HAL 驱动。

### 工作原理

1. **`#ifndef USE_ARDUINO` 包裹**：Arduino 编译时定义 `USE_ARDUINO` 走 HAL 侧；STM32CubeIDE 编译时不定义，行为不变。
2. **`.ino` 引入 C 文件**：通过 `#include` 将 `main.c` / `msp.c` 拉入同一编译单元，变量直接可见。
3. **`ArduinoIT.h` 作为头文件**：避免 `.cpp` 被 Arduino 独立编译导致变量不可见。

### 许可

[MIT](LICENSE)

---

<a id="english"></a>

## English

### Introduction

A GUI-based Python tool that converts STM32CubeMX-generated projects into Arduino projects, letting you drive STM32 peripherals with the HAL library directly in the Arduino IDE — no hand-written interrupt handlers or HAL configuration boilerplate.

### Features

- Native Windows 10 themed GUI
- Chinese / English switch (preference persisted)
- One-click project directory selection
- Auto-detect peripherals and generate `HAL_XXX_MODULE_ONLY` / `HAL_XXX_MODULE_ENABLED`
- Auto-extract interrupt handlers from `stm32*_it.c` into `ArduinoIT.h`
- Add-only merge: handlers never removed, user edits preserved
- Idempotent: re-running never double-injects code
- User edits preserved: `.ino` never overwritten, `HSE_VALUE` value kept

### Requirements

- Python 3.7+ (Windows / Linux / macOS)
- Standard library only, no third-party dependencies

```bash
python STM32CubeLovesArduino.py
```

> On Windows, rename to `.pyw` to hide the console window.

### Usage

1. Generate a project with STM32CubeMX (peripherals configured)
2. Run the tool and click "Select Folder and Process"
3. Select the CubeMX project root folder
4. The tool automatically modifies `main.c` / `msp.c`, generates `.ino`, `ArduinoIT.h`, `hal_conf_extra.h`
5. Open the `.ino` in Arduino IDE, select the matching STM32 board, compile and upload

### Generated Files

| File | Description | Preserves user edits |
|---|---|---|
| `<project>.ino` | Main Arduino sketch, includes main.c and msp.c | ✅ never overwritten |
| `ArduinoIT.h` | Auto-extracted interrupt handlers | ✅ add-only |
| `hal_conf_extra.h` | HAL module configuration | ⚠️ rewritten each run, keeps only `HSE_VALUE` value |
| `main.c` / `*_hal_msp.c` | Injected `#ifndef USE_ARDUINO` guards | ✅ idempotent |

#### Interrupt Handler Management

Auto-extracts peripheral interrupt handlers from `stm32*_it.c`, excluding the standard Cortex-M exception handlers already provided by the Arduino core (e.g. `NMI_Handler`, `SysTick_Handler`).

`ArduinoIT.h` uses an add-only strategy:

- **New handler** → appended at the end
- **Handler removed from it.c** → kept as `//` comments, marked `// --deprecated`
- **Re-added handler** → auto-restored, user modifications kept

```cpp
// Example: SPI1 handler after it was removed from it.c
// extern "C" void SPI1_IRQHandler(void)  // --deprecated
// {
//   HAL_SPI_IRQHandler(&hspi1);
// }
```

### HAL Peripheral Configuration

Scans `main.c` for peripheral handles and generates module config:

| Peripheral | Handle prefix | Generated macro |
|---|---|---|
| ADC | `hadc` | `HAL_ADC_MODULE_ONLY` |
| SPI | `hspi` | `HAL_SPI_MODULE_ONLY` |
| I2C | `hi2c` | `HAL_I2C_MODULE_ONLY` |
| UART | `huart` / `husart` | `HAL_UART_MODULE_ONLY` |
| TIM | `htim` | `HAL_TIM_MODULE_ONLY` |
| RTC | `hrtc` | `HAL_RTC_MODULE_ONLY` |
| PWR | `hpwr` | `HAL_PWR_MODULE_ONLY` |
| FDCAN | `hfdcan` | `HAL_FDCAN_MODULE_ENABLED` |
| CAN | `hcan` | `HAL_CAN_MODULE_ENABLED` |
| DAC | `hdac` | `HAL_DAC_MODULE_ENABLED` |

> Default-enabled modules (ADC/I2C/SPI/TIM/UART...) use `MODULE_ONLY` to disable the Arduino wrapper. Default-disabled modules (CAN/DAC/FDCAN...) need `MODULE_ENABLED` to enable the HAL driver first.

### How It Works

1. **`#ifndef USE_ARDUINO` guards**: Arduino builds define `USE_ARDUINO` (HAL path); STM32CubeIDE builds don't (unchanged behavior).
2. **`.ino` includes the C files**: `#include` pulls `main.c` / `msp.c` into the same translation unit, so variables are directly visible.
3. **`ArduinoIT.h` as a header**: avoids the Arduino builder compiling `.cpp` files independently (which would break variable visibility).

### License

[MIT](LICENSE)

---

## Related Links

- [STM32duino HAL configuration](https://github.com/stm32duino/Arduino_Core_STM32/wiki/HAL-configuration)
