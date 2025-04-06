import pkg_resources
import re

def get_installed_version(package_name):
    try:
        return pkg_resources.get_distribution(package_name).version
    except pkg_resources.DistributionNotFound:
        return None

def update_requirements():
    with open('requirements.txt', 'r') as f:
        requirements = f.readlines()

    updated_requirements = []
    for req in requirements:
        req = req.strip()
        if not req or req.startswith('#'):
            updated_requirements.append(req)
            continue
            
        # Extract package name
        match = re.match(r'^([^=<>]+)==', req)
        if match:
            package_name = match.group(1)
            current_version = get_installed_version(package_name)
            if current_version:
                updated_requirements.append(f'{package_name}=={current_version}')
            else:
                updated_requirements.append(req)  # Keep original if package not found
        else:
            updated_requirements.append(req)  # Keep original if pattern doesn't match

    # Write updated requirements
    with open('requirements.txt', 'w') as f:
        f.write('\n'.join(updated_requirements) + '\n')

if __name__ == '__main__':
    update_requirements()
