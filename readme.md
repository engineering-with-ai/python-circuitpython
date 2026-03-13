# [circuitpython] 📟

![](https://img.shields.io/gitlab/pipeline-status/engineering-with-ai/software-python-circuitpython?branch=main&logo=gitlab)
![](https://gitlab.com/engineering-with-ai/software-python-circuitpython/badges/main/coverage.svg)
![](https://img.shields.io/badge/3.13.2-gray?logo=python)
![](https://img.shields.io/badge/0.10.9-gray?logo=uv)
![](https://img.shields.io/badge/pi_compatible-gray?logo=raspberrypi)
![](https://img.shields.io/badge/mqtt-gray?logo=mqtt)

## Diagrams

### Pinout/Block

#### DHT22 Temperature Sensor
```mermaid
flowchart LR
    classDef default fill:transparent,stroke:#333

    subgraph dht22["DHT22 Sensor"]
        dht_vcc["VCC (pin 1)"]
        dht_data["DATA (pin 2)"]
        dht_nc["NC (pin 3)"]
        dht_gnd["GND (pin 4)"]
    end

    subgraph raspberry_pi["Raspberry Pi"]
        pi_3v3["Pin 1 (3.3V)"]
        pi_gpio4["Pin 7 (GPIO 4)"]
        pi_gnd["Pin 6 (GND)"]
    end

    dht_vcc --> pi_3v3
    dht_data --> pi_gpio4
    dht_gnd --> pi_gnd
```
> Default GPIO pin configured in `src/temperature/temperature_driver.py:31`

## Running Integration Tests

Integration tests require real hardware and run on a remote Raspberry Pi via SSH using pytest-xdist.

### Setup Remote Device

1. Ensure your Raspberry Pi has Python 3 and pytest-xdist installed
2. Configure SSH access to your Pi (test with `ssh pi@raspberrypi.local`)
3. Set the `PI_HOST` environment variable:

```bash
export PI_HOST=pi@raspberrypi.local
# or use a specific IP
export PI_HOST=pi@192.168.1.100
```