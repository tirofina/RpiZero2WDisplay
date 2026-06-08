# RpiZero2WDisplay

Raspberry Pi Zero 2 W에서 Waveshare 2.8inch RPi LCD (A)를 DietPi CLI 환경으로 유지하면서, 필요한 Python/카메라 코드만 LCD에 띄우기 위한 스크립트 모음입니다.

검증된 현재 구성:

- Board: Raspberry Pi Zero 2 W
- OS: DietPi / Debian Trixie
- LCD: Waveshare 2.8inch RPi LCD (A), `waveshare28a-v2`
- Framebuffer: `/dev/fb1`
- X11 detected size: `320x240`
- Touch: `ADS7846 Touchscreen`
- GUI policy: Desktop/LightDM 상시 실행 없음, 필요할 때만 임시 X11 실행

## Files

- `setup_waveshare28a_display.sh`: boot overlay, SPI, ADS7846, tty1 to fb1, autologin setup.
- `install_lcd_x11_on_demand.sh`: temporary X11 framebuffer runtime setup.
- `install_touch_calibration.sh`: ADS7846 touch calibration setup for X11.
- `lcd-run.sh`: run a command on the LCD through direct framebuffer or temporary X11.
- `run_heart_waveshare28a.sh`: run the pygame heart demo on the LCD.
- `heart_display.py`: pygame heart demo.
- `touch_test.py`: pygame touch coordinate test.
- `heart_preview.png`: rendered preview image.

## Install Display Setup

Use this only when preparing a fresh DietPi image for the Waveshare LCD.

```bash
cd /home/dietpi/RpiZero2WDisplay
sudo bash setup_waveshare28a_display.sh
```

Useful options:

```bash
sudo bash setup_waveshare28a_display.sh --rotate 90
sudo bash setup_waveshare28a_display.sh --no-reboot
sudo bash setup_waveshare28a_display.sh --user dietpi
```

The setup keeps DietPi in CLI mode. It does not enable LightDM or a full desktop.

## Install On-Demand X11

Run this once after the display setup:

```bash
cd /home/dietpi/RpiZero2WDisplay
sudo ./install_lcd_x11_on_demand.sh
sudo ./install_touch_calibration.sh
```

This installs the X11 framebuffer driver, `xinput`, `evdev`, and the ADS7846 calibration file.

## Run The Heart Demo

Recommended command:

```bash
cd /home/dietpi/RpiZero2WDisplay
./run_heart_waveshare28a.sh
```

For a short test:

```bash
DURATION=10 ./run_heart_waveshare28a.sh
```

If size must be forced, use the current framebuffer size:

```bash
SIZE=320x240 DURATION=10 ./run_heart_waveshare28a.sh
```

## Run Any Python GUI Only When Needed

Use `x` mode for apps that require X11, such as `cv2.imshow`, tkinter, Qt, matplotlib, or normal pygame on this SDL build:

```bash
./lcd-run.sh x python3 camera_gui.py
```

The X11 session starts for that command only. When the command exits, the device returns to CLI.

## Touch Test

List X11 input devices:

```bash
./lcd-run.sh x xinput list
```

Run the touch coordinate tester:

```bash
./lcd-run.sh x python3 touch_test.py --size 320x240
```

Expected device:

```text
ADS7846 Touchscreen
```

Expected applied properties:

```text
Evdev Axis Calibration: 3821, 182, 300, 3786
Evdev Axes Swap: 0
```

If the axis is swapped:

```bash
sudo SWAP_AXES=1 ./install_touch_calibration.sh
```

If left/right or top/bottom is reversed, reinstall with adjusted calibration values:

```bash
sudo CALIBRATION="182 3821 300 3786" ./install_touch_calibration.sh
sudo CALIBRATION="3821 182 3786 300" ./install_touch_calibration.sh
```

## Direct Framebuffer Mode

Many current pygame/SDL2 builds do not include `fbcon`; in that case `fbcon not available` is expected. Use the default `x` mode above.

Direct framebuffer mode can still be tested if the SDL build supports it:

```bash
sudo RUN_MODE=fb SDL_DRIVER=kmsdrm DURATION=10 ./run_heart_waveshare28a.sh
```

## Preview Without LCD

```bash
python3 heart_display.py --sdl-driver=offscreen --size 240x320 --duration 0.1 --save heart_preview.png
```

## License

MIT
