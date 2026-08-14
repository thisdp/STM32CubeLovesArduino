# STM32CubeLovesArduino 🔄

**STM32 CubeMX 工程一键转换为 Arduino 工程**

One-click conversion from STM32CubeMX project to Arduino project.

---

## 简介 / Introduction

STM32CubeLovesArduino 是一个带 GUI 的 Python 工具，可以将 STM32CubeMX 生成的工程代码自动转换为 Arduino 工程，让你在 Arduino IDE 中直接使用 HAL 库驱动 STM32 外设，而无需手写中断处理函数、HAL 配置等样板代码。

This is a GUI-based Python tool that converts STM32CubeMX-generated projects into Arduino projects, letting you drive STM32 peripherals with the HAL library directly in the Arduino IDE — without hand-writing interrupt handlers or HAL configuration boilerplate.

## 功能特性 / Features

- 🎨 **Win10 风格图形界面** / Native Windows 10 themed GUI
- 🌍 **中英文双语支持**（切换后写入配置文件保存）/ Bilingual UI (zh/en), persisted across restarts
- 📁 **一键选择工程目录** / One-click project directory selection
- 🔌 **自动检测外设**，生成对应的 `HAL_XXX_MODULE_ONLY` / `HAL_XXX_MODULE_ENABLED` 配置 / Auto-detect peripherals and generate HAL module config
- ⚡ **自动提取 `stm32*_it.c` 中的中断处理函数**，写入独立的 `ArduinoIT.h` / Auto-extract interrupt handlers into a separate `ArduinoIT.h`
- 🧩 **增量合并**：中断函数只增不删，用户手动修改保留 / Add-only merge: user modifications preserved
- ♻️ **幂等处理**：重复运行不会重复注入代码 / Idempotent: re-running never double-injects
- 🕐 **保留用户修改**：`.ino` 文件不覆盖，`HSE_VALUE` 数值保留 / Preserve user edits: `.ino` never overwritten, `HSE_VALUE` value kept

## 运行要求 / Requirements

- **Python 3.7+**（Windows / Linux / macOS）
- 仅标准库，无需第三方依赖 / Standard library only, no third-party dependencies
- 可选：将文件改名为 `.pyw` 扩展名以在 Windows 上隐藏控制台窗口

```bash
# 使用 python 运行
python STM32CubeLovesArduino.py

# 或双击运行（Windows）
STM32CubeLovesArduino.pyw
```

## 使用方法 / Usage

1. **用 STM32CubeMX 生成工程**（确保已配置好外设） / Generate a project with STM32CubeMX
2. **运行本工具**，点击「选择文件夹并处理」/ Run the tool and click "Select Folder and Process"
3. **选择 CubeMX 工程根目录** / Select the CubeMX project root folder
4. 工具自动完成以下操作 / The tool automatically:
   - 修改 `main.c` 和 `stm32*_hal_msp.c`，用 `#ifndef USE_ARDUINO` 包裹 STM32 特有的代码 / Wrap STM32-specific code with `#ifndef USE_ARDUINO`
   - 生成 `.ino` 文件（首次运行）/ Generate the `.ino` file (first run only)
   - 生成 `ArduinoIT.h`（提取中断处理函数）/ Generate `ArduinoIT.h` (extracted interrupt handlers)
   - 生成 `hal_conf_extra.h`（外设 HAL 配置）/ Generate `hal_conf_extra.h` (peripheral HAL config)
5. **用 Arduino IDE 打开 `.ino` 文件**，选择对应的 STM32 开发板即可编译上传 / Open the `.ino` in Arduino IDE, select the STM32 board, compile and upload

## 生成文件说明 / Generated Files

| 文件 / File | 说明 / Description | 是否保留用户修改 / Preserves user edits |
|---|---|---|
| `<工程名>.ino` | Arduino 主文件，包含 main.c 和 msp.c / Main Arduino sketch | ✅ 不覆盖 / never overwritten |
| `ArduinoIT.h` | 自动提取的中断处理函数 / Extracted interrupt handlers | ✅ 只增不删 / add-only |
| `hal_conf_extra.h` | HAL 模块配置（外设禁用/启用）/ HAL module configuration | ⚠️ 每次重写，仅保留 `HSE_VALUE` 数值 / rewritten each run, keeps only the `HSE_VALUE` value |
| `main.c` / `*_hal_msp.c` | 注入 `#ifndef USE_ARDUINO` 包裹 / injected `#ifndef USE_ARDUINO` guards | ✅ 幂等 / idempotent |

### 中断处理函数管理 / Interrupt Handler Management

从 `stm32*_it.c` 自动提取**外设中断处理函数**（自动排除 Arduino 核心已提供的标准 Cortex-M 异常处理函数，如 `NMI_Handler`、`SysTick_Handler` 等）。

The tool auto-extracts **peripheral interrupt handlers** from `stm32*_it.c` (excluding standard Cortex-M exception handlers already provided by the Arduino core, such as `NMI_Handler`, `SysTick_Handler`, etc.).

`ArduinoIT.h` 采用**只增不删**策略：

`ArduinoIT.h` uses an **add-only** strategy:

- **新增函数** → 追加到文件末尾 / **New handler** → appended at the end
- **it.c 中移除的函数** → 用 `//` 注释保留，标记 `// --deprecated` / **Handler removed from it.c** → kept as `//` comments, marked `// --deprecated`
- **重新加入的函数** → 自动恢复，保留用户手动修改 / **Re-added handler** → auto-restored, user modifications kept

```cpp
// 示例：it.c 移除 SPI1 中断后的状态
// extern "C" void SPI1_IRQHandler(void)  // --deprecated
// {
//   HAL_SPI_IRQHandler(&hspi1);
// }
```

## HAL 配置 / HAL Configuration

工具自动扫描 `main.c` 中的外设句柄，生成 `hal_conf_extra.h` 中的模块配置：

The tool scans `main.c` for peripheral handles and generates HAL module config in `hal_conf_extra.h`:

| 外设 / Peripheral | 句柄前缀 / Handle prefix | 生成的宏 / Generated macro |
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

> 默认启用的模块（ADC/I2C/SPI/TIM/UART 等）使用 `MODULE_ONLY` 禁用 Arduino 封装，仅保留 HAL 驱动；
> 默认禁用的模块（CAN/DAC/FDCAN 等）需要使用 `MODULE_ENABLED` 先启用 HAL 驱动。
>
> Default-enabled modules (ADC/I2C/SPI/TIM/UART...) use `MODULE_ONLY` to disable the Arduino wrapper and keep only the HAL driver; default-disabled modules (CAN/DAC/FDCAN...) need `MODULE_ENABLED` to enable the HAL driver first.

## 多语言支持 / i18n

界面右下角有语言切换按钮，支持 **中文 / English** 一键切换。语言设置保存在脚本同目录下的 `.stm32_conv_config` 文件中，下次启动自动恢复。

A language toggle button sits at the bottom-right corner. Switch between **中文 / English** anytime. The preference is saved to `.stm32_conv_config` next to the script and restored on next launch.

## 工作原理 / How It Works

1. **`#ifndef USE_ARDUINO` 包裹**：在 `main.c` / `msp.c` 中，将 STM32CubeMX 特有的代码用条件编译包裹。Arduino 编译时定义 `USE_ARDUINO`，走 HAL 侧；STM32CubeIDE 编译时不定义，行为不变。
   **`#ifndef USE_ARDUINO` guards**: STM32CubeMX-specific code is wrapped in conditional compilation. Arduino builds define `USE_ARDUINO` (HAL path); STM32CubeIDE builds don't (unchanged behavior).

2. **`.ino` 引入 C 文件**：通过 `#include` 将 `main.c` 和 `msp.c` 拉入同一编译单元，变量和函数直接可见。
   **`.ino` includes the C files**: `#include` pulls `main.c` and `msp.c` into the same translation unit, so variables and functions are directly visible.

3. **`ArduinoIT.h` 作为头文件**：避免 `.cpp` 文件被 Arduino 独立编译导致变量不可见。
   **`ArduinoIT.h` as a header**: avoids the Arduino builder compiling `.cpp` files independently (which would break variable visibility).

## 依赖 / Dependencies

无第三方 Python 依赖。仅使用标准库：`tkinter`、`re`、`json`、`pathlib`。

No third-party Python dependencies. Uses only the standard library: `tkinter`, `re`, `json`, `pathlib`.

## 许可 / License

[MIT](LICENSE)

## 相关链接 / Related Links

- [STM32 Arduino Core HAL 配置文档 / STM32duino HAL configuration](https://github.com/stm32duino/Arduino_Core_STM32/wiki/HAL-configuration)
