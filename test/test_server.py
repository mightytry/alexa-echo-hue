
import asyncio, pytest
import socket
import time
import threading


def test_imports():
    from src.echohue import Hub, Device
    assert Hub
    assert Device

# Path: test\test_server.py
def test_hub():
    global hub
    from src.echohue import Hub
    hub = Hub(True)
    assert hub

# Path: test\test_server.py
def test_device():
    global device
    from src.echohue import Device
    device = Device("test")
    assert device

def test_add_device():
    global hub, device
    hub.add(device)
    assert len(hub.devices) == 1

def test_run_hub():
    try:
        threading.Thread(target=lambda: asyncio.run(hub.run()), daemon=True).start()
        for i in range(50):
            time.sleep(0.1)
            if hub.config["IP"]:
                return
        raise Exception("Hub did not start")
    except asyncio.TimeoutError:
        pass

def test_ip():
    assert hub.config["IP"]

def test_connection():
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((hub.config["IP"], hub.config["HTTP_PORT"]))
    assert result == 0

def test_Httpd():
    sock.send(b"test\r\n\r\n")
    try:
        r = sock.recv(1024)
    except socket.timeout:
        r = b""
    assert r == b"ok"


def test_stop_hub():
    asyncio.run(asyncio.wait_for(hub.stop(), timeout=2))