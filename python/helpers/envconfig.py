import os

class EnvConfigManager:
    def __init__(self, env_file):
        self.env_file = env_file
        self.env_data = self.load_env_file()

    def load_env_file(self):
        """Load the contents of the .env file into a dictionary."""
        env_data = {}
        if os.path.exists(self.env_file):
            with open(self.env_file, 'r') as file:
                for line in file:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        env_data[key] = value
        return env_data

    def get_value(self, key):
        """Get the value for a given key from the env data."""
        return self.env_data.get(key)

    def append_to_value(self, key, value):
        """Append a value to a key in the env data, ensuring no duplicates."""
        current_value = self.get_value(key)
        if current_value:
            values = set(current_value.split(','))
            if value not in values:
                values.add(value)
                self.env_data[key] = ','.join(sorted(values))
        else:
            self.env_data[key] = value

    def save_env_file(self):
        """Write the updated env data back to the .env file."""
        with open(self.env_file, 'w') as file:
            for key, value in self.env_data.items():
                file.write(f"{key}={value}\n")
        print(f"Updated '{self.env_file}' with current settings.")

    def add_validated_path(self, host_path):
        """Add a validated Docker path to the .env file."""
        self.append_to_value("VALIDATED_DOCKER_PATH", host_path)
        self.save_env_file()

