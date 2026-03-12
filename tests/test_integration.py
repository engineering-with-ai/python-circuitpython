"""
Hardware-in-Loop test for MQTT integration.

Tests full MQTT flow by:
- Starting MQTT broker in testcontainer
- Deploying code to Raspberry Pi via SSH
- Running application on Pi with dynamic MQTT port from testcontainer
- Verifying temperature message received on MQTT topic
"""

import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import paramiko
import paho.mqtt.client as mqtt_client
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

# Topic where temperature readings are published
MQTT_TOPIC = "test/temp/F"


@contextmanager
def mqtt_broker() -> Generator[tuple[DockerContainer, int]]:
    """
    Start MQTT broker in testcontainer and wait for it to be ready.

    Yields:
        Tuple of (container, broker_port)
    """
    with (
        DockerContainer("eclipse-mosquitto:2")
        .with_exposed_ports(1883)
        .with_command("mosquitto -c /mosquitto-no-auth.conf")
        .waiting_for(LogMessageWaitStrategy("mosquitto version .* running"))
    ) as broker:
        port = broker.get_exposed_port(1883)
        yield broker, port


def test_hil_mqtt_integration() -> None:
    """
    Test HIL MQTT integration.

    This test requires a Raspberry Pi with DHT22 sensor connected.
    It will fail if hardware is not available.
    """
    start_time = time.time()

    # Get Pi connection details from environment
    pi_host = os.environ.get("PI_HOST", "pi@raspberrypi.local")
    if "@" in pi_host:
        pi_user, pi_hostname = pi_host.split("@")
    else:
        pi_user = "pi"
        pi_hostname = pi_host

    # Arrange - Start MQTT broker
    with mqtt_broker() as (_, broker_port):
        print(
            f"[{time.time() - start_time:.1f}s] MQTT broker started on port {broker_port}"
        )

        # Get host IP that Pi can reach (not localhost)
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        host_ip = s.getsockname()[0]
        s.close()

        print(f"[{time.time() - start_time:.1f}s] Host IP for Pi to connect: {host_ip}")

        # Setup subscriber to capture published messages
        received_messages: list[str] = []

        def on_message(
            _client: mqtt_client.Client,
            _userdata: object,
            message: mqtt_client.MQTTMessage,
        ) -> None:
            received_messages.append(message.payload.decode())

        subscriber = mqtt_client.Client(
            client_id="hil_test_client",
            protocol=mqtt_client.MQTTv5,
        )
        subscriber.on_message = on_message
        subscriber.connect("localhost", broker_port)
        subscriber.subscribe(MQTT_TOPIC)
        subscriber.loop_start()

        # Deploy and run code on Pi using paramiko
        print(f"[{time.time() - start_time:.1f}s] Deploying code to Pi via SSH...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

        try:
            ssh.connect(pi_hostname, username=pi_user)

            # Create remote directory
            ssh.exec_command("mkdir -p /tmp/circuitpython-test")

            # Upload src directory
            sftp = ssh.open_sftp()
            project_root = Path(__file__).parent.parent

            # Upload src files
            for src_file in (project_root / "src").rglob("*.py"):
                relative_path = src_file.relative_to(project_root)
                remote_path = f"/tmp/circuitpython-test/{relative_path}"  # noqa: S108

                # Create remote directory if needed
                remote_dir = str(Path(remote_path).parent)
                ssh.exec_command(f"mkdir -p {remote_dir}")

                sftp.put(str(src_file), remote_path)

            # Upload build.py and cfg.yml
            sftp.put(
                str(project_root / "build.py"),
                "/tmp/circuitpython-test/build.py",  # noqa: S108
            )
            sftp.put(
                str(project_root / "cfg.yml"),
                "/tmp/circuitpython-test/cfg.yml",  # noqa: S108
            )

            sftp.close()

            print(f"[{time.time() - start_time:.1f}s] Running application on Pi...")

            # Run application on Pi with environment variables
            _stdin, stdout, stderr = ssh.exec_command(
                f"cd /tmp/circuitpython-test && "
                f"MQTT_PORT={broker_port} MODE=development "
                f"python3 -m src.main",
                get_pty=True,
                timeout=30,
            )

            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()

            stdout_text = stdout.read().decode()
            stderr_text = stderr.read().decode()

            print(f"[{time.time() - start_time:.1f}s] Application completed")
            print(f"Exit status: {exit_status}")
            if stdout_text:
                print(f"STDOUT: {stdout_text}")
            if stderr_text:
                print(f"STDERR: {stderr_text}")

            # Assert - Application ran successfully
            assert (
                exit_status == 0
            ), f"Application failed with exit status {exit_status}"

        finally:
            ssh.close()

        # Wait for message to be received
        time.sleep(1)

        # Assert - Temperature message received
        assert len(received_messages) >= 1, "No MQTT message received"

        # Assert - Validate temperature is in reasonable range (50-104°F)
        temp_str = received_messages[0]
        temp_f = float(temp_str)

        assert (
            50.0 <= temp_f <= 104.0
        ), f"Temperature {temp_f}°F is outside reasonable range"

        print(
            f"[{time.time() - start_time:.1f}s] ✓ Test passed! "
            f"Received valid temperature: {temp_f}°F"
        )

        # Cleanup
        subscriber.loop_stop()
        subscriber.disconnect()
