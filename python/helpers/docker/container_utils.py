import os
import time
import uuid

def load_validated_paths(env_file):
    if not os.path.exists(env_file):
        return set()
    with open(env_file, 'r') as file:
        lines = file.readlines()
        return {line.split('=')[1].strip() for line in lines if line.startswith("VALIDATED_DOCKER_PATH=")}

def is_path_validated(host_path, validated_paths):
    return host_path in validated_paths

def create_unique_filename():
    return f"docker_test_{uuid.uuid4()}.txt"

def create_file_in_container(container, container_path, filename):
    full_container_path = os.path.join(container_path, filename)
    exec_result = container.exec_run(f"sh -c 'echo validation > {full_container_path}'")
    if exec_result.exit_code != 0:
        print(f"Failed to write file inside container. Command output: {exec_result.output.decode('utf-8')}")
        return False
    return True

def check_file_on_host(host_path, filename):
    time.sleep(1)  # Wait a moment to ensure file system sync
    if os.path.exists(os.path.join(host_path, filename)):
        print(f"Volume validation successful. Docker can access '{host_path}'.")
        return True
    else:
        print(f"Volume validation failed. Docker cannot access '{host_path}'.")
        return False

def store_validated_path(env_file, host_path):
    with open(env_file, 'a') as file:
        file.write(f"VALIDATED_DOCKER_PATH={host_path}\n")
    print(f"Path '{host_path}' added to '{env_file}' for future use.")
