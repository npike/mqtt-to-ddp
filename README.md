# MQTT to DDP Bridge

This script acts as a bridge between MQTT and DDP, allowing you to control a DDP-enabled device as an RGB light in Home Assistant.

## Features

*   Connects to an MQTT broker.
*   Registers itself as an RGB light with brightness control in Home Assistant using MQTT discovery.
*   Translates MQTT commands to DDP packets.
*   Sends DDP packets to a specified IP address and port.
*   Configuration via an external `config.ini` file.

## Installation

1.  **Clone the repository or download the files.**

2.  **Create and activate a Python virtual environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

    _Note: On Windows, the activation command is `venv\Scripts\activate`_

3.  **Install the required Python libraries:**

    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Rename `config.ini.example` to `config.ini`** (or create a new `config.ini` file).

2.  **Edit `config.ini` with your settings:**

    *   **[mqtt]**
        *   `broker`: The IP address or hostname of your MQTT broker.
        *   `port`: The port of your MQTT broker (usually 1883).
        *   `user`: The username for your MQTT broker (if any).
        *   `password`: The password for your MQTT broker (if any).
        *   `base_topic`: The base topic for Home Assistant discovery (usually `homeassistant`).

    *   **[ddp]**
        *   `device_ip`: The IP address of your DDP device.
        *   `device_port`: The port of your DDP device (usually 4048).

    *   **[light]**
        *   `name`: The name of the light as it will appear in Home Assistant.
        *   `unique_id`: A unique ID for the light.

## Usage

Run the script from your terminal:

```bash
python mqtt_to_ddp.py
```

The script will connect to the MQTT broker, publish the discovery topic, and wait for commands. You should see the new light appear in your Home Assistant interface.
