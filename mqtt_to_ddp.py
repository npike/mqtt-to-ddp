
import configparser
import json
import paho.mqtt.client as mqtt
import socket
import time
import threading

# Read configuration
config = configparser.ConfigParser()
config.read('config.ini')

# MQTT settings
MQTT_BROKER = config['mqtt']['broker']
MQTT_PORT = int(config['mqtt']['port'])
MQTT_USER = config['mqtt']['user']
MQTT_PASSWORD = config['mqtt']['password']
MQTT_BASE_TOPIC = config['mqtt']['base_topic']

# DDP settings
DDP_IP = config['ddp']['device_ip']
DDP_PORT = int(config['ddp']['device_port'])

# Light settings
LIGHT_NAME = config['light']['name']
LIGHT_UNIQUE_ID = config['light']['unique_id']
PIXEL_COUNT = int(config['light']['pixel_count'])

STATE_TOPIC = f"{MQTT_BASE_TOPIC}/light/{LIGHT_UNIQUE_ID}/state"
COMMAND_TOPIC = f"{MQTT_BASE_TOPIC}/light/{LIGHT_UNIQUE_ID}/set"
DISCOVERY_TOPIC = f"{MQTT_BASE_TOPIC}/light/{LIGHT_UNIQUE_ID}/config"

# Global state
light_state = {
    'state': 'OFF',
    'color': {'r': 255, 'g': 255, 'b': 255},
    'brightness': 255
}
sequence_number = 1

def create_ddp_packet(r, g, b, brightness, seq_num):
    """Creates a DDP packet."""
    data_length = PIXEL_COUNT * 3
    # DDP header v1
    header = bytearray([
        0x60,  # Flags: Version 1, Push, No other flags
        seq_num,  # Sequence Number
        0x01,  # Data Type: Pixel
        0x01,  # Device ID
        0x00, 0x00, 0x00, 0x00,  # Offset
    ]) + data_length.to_bytes(2, 'big')

    # Scale color by brightness
    r = int(r * (brightness / 255.0))
    g = int(g * (brightness / 255.0))
    b = int(b * (brightness / 255.0))

    pixel_data = bytearray([r, g, b]) * PIXEL_COUNT
    return header + pixel_data


def send_ddp_packet(packet):
    """Sends a DDP packet to the specified device."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (DDP_IP, DDP_PORT))


def ddp_loop():
    """Continuously sends DDP packets to keep the light alive."""
    global sequence_number
    while True:
        if light_state['state'] == 'ON':
            r = light_state['color']['r']
            g = light_state['color']['g']
            b = light_state['color']['b']
            brightness = light_state['brightness']
            ddp_packet = create_ddp_packet(r, g, b, brightness, sequence_number)
            send_ddp_packet(ddp_packet)
            sequence_number = (sequence_number % 15) + 1
        time.sleep(0.02)  # Send a packet every 20ms

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(COMMAND_TOPIC)
        publish_discovery()
    else:
        print(f"Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the MQTT broker."""
    global light_state, sequence_number
    print(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        light_state['state'] = payload.get('state', 'OFF')

        if light_state['state'] == 'ON':
            light_state['color'] = payload.get('color', {'r': 255, 'g': 255, 'b': 255})
            light_state['brightness'] = payload.get('brightness', 255)

            # Send a packet immediately
            r = light_state['color']['r']
            g = light_state['color']['g']
            b = light_state['color']['b']
            brightness = light_state['brightness']
            ddp_packet = create_ddp_packet(r, g, b, brightness, sequence_number)
            send_ddp_packet(ddp_packet)
            sequence_number = (sequence_number % 15) + 1

            # Publish back the state
            client.publish(STATE_TOPIC, json.dumps(light_state), retain=True)
        else:
            # Turn off the light by sending a black packet
            ddp_packet = create_ddp_packet(0, 0, 0, 0, sequence_number)
            send_ddp_packet(ddp_packet)
            sequence_number = (sequence_number % 15) + 1
            # Publish back the state
            client.publish(STATE_TOPIC, json.dumps({"state": "OFF"}), retain=True)

    except json.JSONDecodeError:
        print("Error decoding JSON payload")
    except Exception as e:
        print(f"An error occurred: {e}")

def publish_discovery():
    """Publishes the Home Assistant discovery topic."""
    discovery_payload = {
        "name": LIGHT_NAME,
        "unique_id": LIGHT_UNIQUE_ID,
        "schema": "json",
        "state_topic": STATE_TOPIC,
        "command_topic": COMMAND_TOPIC,
        "brightness": True,
        "color_mode": True,
        "supported_color_modes": ["rgb"],
        "optimistic": False,
        "qos": 0,
        "retain": True
    }
    client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
    print(f"Published Home Assistant discovery topic to {DISCOVERY_TOPIC}")

# Set up MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)



try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"Error connecting to MQTT broker: {e}")
    exit(1)


# Start the MQTT loop
client.loop_forever()
