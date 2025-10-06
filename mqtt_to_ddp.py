
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

# Global state for all lights
all_lights = {}

# Read light configurations
for section in config.sections():
    if section.startswith('light_'):
        light_id = section.replace('light_', '')
        display_name = light_id.replace('_', ' ').title()
        all_lights[light_id] = {
            'name': display_name,
            'unique_id': light_id,
            'device_ip': config[section]['device_ip'],
            'device_port': int(config[section]['device_port']),
            'pixel_count': int(config[section]['pixel_count']),
            'state': 'OFF',
            'color': {'r': 255, 'g': 255, 'b': 255},
            'brightness': 255,
            'sequence_number': 1
        }

def create_ddp_packet(r, g, b, brightness, seq_num, pixel_count):
    """Creates a DDP packet."""
    data_length = pixel_count * 3
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

    pixel_data = bytearray([r, g, b]) * pixel_count
    return header + pixel_data


def send_ddp_packet(packet, device_ip, device_port):
    """Sends a DDP packet to the specified device."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (device_ip, device_port))


def ddp_loop():
    """Continuously sends DDP packets to keep the light alive."""
    while True:
        for light_id, light_data in all_lights.items():
            if light_data['state'] == 'ON':
                r = light_data['color']['r']
                g = light_data['color']['g']
                b = light_data['color']['b']
                brightness = light_data['brightness']
                seq_num = light_data['sequence_number']
                pixel_count = light_data['pixel_count']
                device_ip = light_data['device_ip']
                device_port = light_data['device_port']

                ddp_packet = create_ddp_packet(r, g, b, brightness, seq_num, pixel_count)
                send_ddp_packet(ddp_packet, device_ip, device_port)
                light_data['sequence_number'] = (seq_num % 15) + 1
        time.sleep(0.02)  # Send a packet every 20ms

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the MQTT broker."""
    if rc == 0:
        print("Connected to MQTT Broker!")
        for light_id, light_data in all_lights.items():
            command_topic = f"{MQTT_BASE_TOPIC}/light/{light_data['unique_id']}/set"
            client.subscribe(command_topic)
            print(f"Subscribed to {command_topic}")
            publish_discovery(client, light_data)
    else:
        print(f"Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the MQTT broker."""
    global all_lights
    print(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
    try:
        payload = json.loads(msg.payload.decode())
        
        # Extract unique_id from topic
        topic_parts = msg.topic.split('/')
        unique_id_index = topic_parts.index('light') + 1
        light_unique_id = topic_parts[unique_id_index]

        # Find the light in all_lights
        current_light = None
        for light_id, light_data in all_lights.items():
            if light_data['unique_id'] == light_unique_id:
                current_light = light_data
                break

        if not current_light:
            print(f"Error: Light with unique_id {light_unique_id} not found.")
            return

        current_light['state'] = payload.get('state', 'OFF')

        if current_light['state'] == 'ON':
            if 'brightness' in payload:
                current_light['brightness'] = payload['brightness']
            if 'color' in payload:
                current_light['color'] = payload['color']

            # Send a packet immediately
            r = current_light['color']['r']
            g = current_light['color']['g']
            b = current_light['color']['b']
            brightness = current_light['brightness']
            seq_num = current_light['sequence_number']
            pixel_count = current_light['pixel_count']
            device_ip = current_light['device_ip']
            device_port = current_light['device_port']

            ddp_packet = create_ddp_packet(r, g, b, brightness, seq_num, pixel_count)
            send_ddp_packet(ddp_packet, device_ip, device_port)
            current_light['sequence_number'] = (seq_num % 15) + 1

            # Publish back the state
            client.publish(msg.topic.replace('/set', '/state'), json.dumps(current_light), retain=True)
        else:
            # Turn off the light by sending a black packet
            r, g, b, brightness = 0, 0, 0, 0
            seq_num = current_light['sequence_number']
            pixel_count = current_light['pixel_count']
            device_ip = current_light['device_ip']
            device_port = current_light['device_port']

            ddp_packet = create_ddp_packet(r, g, b, brightness, seq_num, pixel_count)
            send_ddp_packet(ddp_packet, device_ip, device_port)
            current_light['sequence_number'] = (seq_num % 15) + 1
            # Publish back the state
            client.publish(msg.topic.replace('/set', '/state'), json.dumps({"state": "OFF"}), retain=True)

    except json.JSONDecodeError:
        print("Error decoding JSON payload")
    except Exception as e:
        print(f"An error occurred: {e}")

def publish_discovery(client, light_data):
    """Publishes the Home Assistant discovery topic."""
    state_topic = f"{MQTT_BASE_TOPIC}/light/{light_data['unique_id']}/state"
    command_topic = f"{MQTT_BASE_TOPIC}/light/{light_data['unique_id']}/set"
    discovery_topic = f"{MQTT_BASE_TOPIC}/light/{light_data['unique_id']}/config"

    discovery_payload = {
        "name": light_data['name'],
        "unique_id": light_data['unique_id'],
        "schema": "json",
        "state_topic": state_topic,
        "command_topic": command_topic,
        "brightness": True,
        "color_mode": True,
        "supported_color_modes": ["rgb"],
        "optimistic": False,
        "qos": 0,
        "retain": True
    }
    client.publish(discovery_topic, json.dumps(discovery_payload), retain=True)
    print(f"Published Home Assistant discovery topic for {light_data['name']} to {discovery_topic}")

# Set up MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

# Start the DDP loop in a separate thread
ddp_thread = threading.Thread(target=ddp_loop)
ddp_thread.daemon = True
ddp_thread.start()

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    print(f"Error connecting to MQTT broker: {e}")
    exit(1)

# Start the MQTT loop
client.loop_forever()
